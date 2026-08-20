import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib import error, request

from bot.config import config


GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeminiModerationResult:
    checked: bool
    verdict: str | None = None
    reason: str | None = None
    skipped_reason: str | None = None


@dataclass(slots=True)
class GeminiQuotaState:
    day: str
    used_requests: int = 0


async def classify_message_with_gemini(
    *,
    text: str,
    content_type: str,
    is_verified: bool,
    local_score: int,
    matched_rules: list[str],
) -> GeminiModerationResult:
    if not config.gemini_api_key:
        return GeminiModerationResult(
            checked=False,
            skipped_reason="missing_api_key",
        )

    reserved = await _reserve_quota_slot()

    if not reserved:
        return GeminiModerationResult(
            checked=False,
            skipped_reason="daily_limit_reached",
        )

    try:
        response_payload = await _request_gemini(
            text=text,
            content_type=content_type,
            is_verified=is_verified,
            local_score=local_score,
            matched_rules=matched_rules,
        )
        output_text = _extract_model_output_text(response_payload)
        parsed_output = _parse_model_output(output_text)
    except Exception:
        await _release_quota_slot()
        logger.exception("Gemini moderation request failed")
        return GeminiModerationResult(
            checked=False,
            skipped_reason="request_failed",
        )

    return GeminiModerationResult(
        checked=True,
        verdict=parsed_output["verdict"],
        reason=parsed_output["reason"],
    )


async def _request_gemini(
    *,
    text: str,
    content_type: str,
    is_verified: bool,
    local_score: int,
    matched_rules: list[str],
) -> dict[str, Any]:
    payload = {
        "model": config.gemini_model,
        "store": False,
        "input": _build_prompt(
            text=text,
            content_type=content_type,
            is_verified=is_verified,
            local_score=local_score,
            matched_rules=matched_rules,
        ),
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": {
                "type": "object",
                "properties": {
                    "verdict": {
                        "type": "string",
                        "enum": ["spam", "not_spam"],
                    },
                    "reason": {
                        "type": "string",
                    },
                },
                "required": ["verdict", "reason"],
                "additionalProperties": False,
            },
        },
        "generation_config": {
            "max_output_tokens": 120,
        },
    }

    return await asyncio.to_thread(_post_request, payload)


def _build_prompt(
    *,
    text: str,
    content_type: str,
    is_verified: bool,
    local_score: int,
    matched_rules: list[str],
) -> str:
    return (
        "You are a strict Telegram group anti-spam classifier.\n"
        "Return JSON only.\n"
        "Classify the message as spam if it contains unsolicited ads, fake jobs, "
        "money-making promises, requests to contact a username privately, scam, "
        "crypto/gambling promotion, phishing, or obvious bulk promotion.\n"
        "Classify as not_spam for normal discussion, greetings, reactions, jokes, "
        "questions, or harmless conversation.\n\n"
        f"verified_user={is_verified}\n"
        f"content_type={content_type}\n"
        f"local_score={local_score}\n"
        f"matched_rules={', '.join(matched_rules) or '<none>'}\n"
        f"message_text={text!r}\n"
    )


def _extract_model_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")

    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for step in payload.get("steps", []):
        if step.get("type") != "model_output":
            continue

        extracted = _extract_text_from_node(step)

        if extracted:
            return extracted

    raise RuntimeError("Gemini moderation response did not contain model output text")


def _extract_text_from_node(node: Any) -> str:
    if isinstance(node, dict):
        parts: list[str] = []

        if isinstance(node.get("text"), str):
            parts.append(node["text"])

        for value in node.values():
            nested_text = _extract_text_from_node(value)
            if nested_text:
                parts.append(nested_text)

        return "\n".join(part for part in parts if part).strip()

    if isinstance(node, list):
        parts = [_extract_text_from_node(item) for item in node]
        return "\n".join(part for part in parts if part).strip()

    return ""


def _parse_model_output(output_text: str) -> dict[str, str]:
    stripped = _strip_code_fences(output_text)
    normalized = stripped.strip().lower()

    if normalized in {"spam", "not_spam"}:
        return {
            "verdict": normalized,
            "reason": "plain_text_verdict",
        }

    parsed = json.loads(stripped)
    verdict = parsed.get("verdict")
    reason = parsed.get("reason")

    if verdict not in {"spam", "not_spam"}:
        raise RuntimeError(f"Unexpected Gemini verdict: {verdict!r}")

    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeError("Gemini moderation response did not contain a reason")

    return {
        "verdict": verdict,
        "reason": reason.strip(),
    }


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()

    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()

    return stripped


async def _reserve_quota_slot() -> bool:
    async with quota_lock:
        _reset_quota_if_needed()

        if quota_state.used_requests >= config.gemini_daily_request_limit:
            return False

        quota_state.used_requests += 1
        logger.info(
            "Reserved Gemini moderation request day=%s used=%s limit=%s",
            quota_state.day,
            quota_state.used_requests,
            config.gemini_daily_request_limit,
        )
        return True


async def _release_quota_slot() -> None:
    async with quota_lock:
        _reset_quota_if_needed()

        if quota_state.used_requests == 0:
            return

        quota_state.used_requests -= 1
        logger.info(
            "Released Gemini moderation request day=%s used=%s limit=%s",
            quota_state.day,
            quota_state.used_requests,
            config.gemini_daily_request_limit,
        )


def _reset_quota_if_needed() -> None:
    today = _utc_today()

    if quota_state.day == today:
        return

    quota_state.day = today
    quota_state.used_requests = 0


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _post_request(payload: dict[str, Any]) -> dict[str, Any]:
    raw_payload = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        GEMINI_INTERACTIONS_URL,
        data=raw_payload,
        headers={
            "x-goog-api-key": config.gemini_api_key or "",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(
            http_request,
            timeout=config.gemini_request_timeout_seconds,
        ) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini moderation HTTP {exc.code}: {error_body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Gemini moderation request failed: {exc}") from exc

    return json.loads(response_body)


quota_state = GeminiQuotaState(day=_utc_today())
quota_lock = asyncio.Lock()
