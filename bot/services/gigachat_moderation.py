import asyncio
import json
import logging
import ssl
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request

from bot.config import config


GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_CHAT_COMPLETIONS_URL = "https://api.giga.chat/v1/chat/completions"
GIGACHAT_USER_AGENT = "telegram_bot_for_ban_spamers/1.0"
TOKEN_EXPIRY_SAFETY_SECONDS = 30
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GigaChatModerationResult:
    checked: bool
    verdict: str | None = None
    reason: str | None = None
    skipped_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class GigaChatAccessTokenState:
    access_token: str | None = None
    expires_at: int = 0


class GigaChatHTTPError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"GigaChat HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body


async def classify_message_with_gigachat(
    *,
    text: str,
    content_type: str,
    is_verified: bool,
    local_score: int,
    matched_rules: list[str],
) -> GigaChatModerationResult:
    if not config.gigachat_auth_key:
        return GigaChatModerationResult(
            checked=False,
            skipped_reason="missing_auth_key",
        )

    async with request_lock:
        try:
            response_payload = await _request_gigachat(
                text=text,
                content_type=content_type,
                is_verified=is_verified,
                local_score=local_score,
                matched_rules=matched_rules,
            )
            output_text = _extract_model_output_text(response_payload)
            parsed_output = _parse_model_output(output_text)
        except GigaChatHTTPError as exc:
            logger.warning(
                "GigaChat moderation HTTP failure status=%s reason=%s body=%s",
                exc.status_code,
                _map_http_error_to_skip_reason(exc.status_code),
                exc.body,
            )
            return GigaChatModerationResult(
                checked=False,
                skipped_reason=_map_http_error_to_skip_reason(exc.status_code),
            )
        except Exception:
            logger.exception("GigaChat moderation request failed")
            return GigaChatModerationResult(
                checked=False,
                skipped_reason="request_failed",
            )

    usage = response_payload.get("usage") if isinstance(response_payload, dict) else None

    return GigaChatModerationResult(
        checked=True,
        verdict=parsed_output["verdict"],
        reason=parsed_output["reason"],
        prompt_tokens=_usage_value(usage, "prompt_tokens"),
        completion_tokens=_usage_value(usage, "completion_tokens"),
        total_tokens=_usage_value(usage, "total_tokens"),
    )


async def _request_gigachat(
    *,
    text: str,
    content_type: str,
    is_verified: bool,
    local_score: int,
    matched_rules: list[str],
) -> dict[str, Any]:
    payload = {
        "model": config.gigachat_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты — очень строгий модератор Telegram-чата, который "
                    "определяет, является ли сообщение спамом. "
                    "Верни только JSON, который строго соответствует "
                    "заданной схеме. "
                    "Твоя задача — защищать чат от нежелательных объявлений, "
                    "рекламы, сомнительных предложений, поиска исполнителей, "
                    "найма, подработки, коммерческих сообщений и перевода "
                    "общения в личные сообщения. "
                    "Считай сообщение spam, если есть хотя бы один из "
                    "признаков: предложение работы, подработки, вакансии, "
                    "заработка, оплаты за действие; поиск людей для услуги, "
                    "задания, помощи, переезда, доставки, сопровождения или "
                    "сделки; упоминание денег, оплаты, ставок, дохода, "
                    "вознаграждения или зарплаты; призыв писать в личку, в "
                    "ЛС, в директ, по контакту или в Telegram username; "
                    "реклама услуг, товаров, каналов, чатов, ботов, курсов, "
                    "инвестиций, крипты, ставок или казино; попытка увести "
                    "общение из чата в личные сообщения; массовое или "
                    "подозрительное объявление, даже если оно выглядит "
                    "обычным; сомнительное бытовое объявление от неизвестного "
                    "или неверифицированного пользователя. "
                    "Особенно строго оценивай сообщения от "
                    "неверифицированных пользователей. "
                    "Если в сообщении одновременно есть деньги или оплата и "
                    "призыв написать в личку, почти всегда считай это spam. "
                    "Если в сообщении есть поиск человека на задачу или "
                    "услугу за деньги, по умолчанию считай это spam. "
                    "Если сомневаешься между spam и not_spam, выбирай spam. "
                    "Считай сообщение not_spam только если это обычное живое "
                    "общение участников чата: обсуждение, вопрос, ответ, "
                    "шутка, реакция, благодарность или нейтральное сообщение "
                    "без коммерческого или призывного характера. "
                    "Поле reason пиши кратко и на русском языке."
                ),
            },
            {
                "role": "user",
                "content": _build_prompt(
                    text=text,
                    content_type=content_type,
                    is_verified=is_verified,
                    local_score=local_score,
                    matched_rules=matched_rules,
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
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
            "strict": True,
        },
    }

    access_token = await _get_access_token(force_refresh=False)

    try:
        return await asyncio.to_thread(_post_chat_completion_request, payload, access_token)
    except GigaChatHTTPError as exc:
        if exc.status_code != 401:
            raise

        logger.info("Refreshing GigaChat access token after 401 response")
        access_token = await _get_access_token(force_refresh=True)
        return await asyncio.to_thread(_post_chat_completion_request, payload, access_token)


def _build_prompt(
    *,
    text: str,
    content_type: str,
    is_verified: bool,
    local_score: int,
    matched_rules: list[str],
) -> str:
    return (
        f"Пользователь верифицирован: {is_verified}\n"
        f"Тип контента: {content_type}\n"
        f"Локальный score: {local_score}\n"
        f"Сработавшие правила: {', '.join(matched_rules) or '<none>'}\n"
        f"Текст сообщения: {text!r}\n"
    )


def _extract_model_output_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")

    if not isinstance(choices, list) or not choices:
        raise RuntimeError("GigaChat moderation response does not contain choices")

    message = choices[0].get("message")

    if not isinstance(message, dict):
        raise RuntimeError("GigaChat moderation response does not contain message")

    content = message.get("content")

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("GigaChat moderation response does not contain content")

    return content


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
        raise RuntimeError(f"Unexpected GigaChat verdict: {verdict!r}")

    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeError("GigaChat moderation response does not contain a reason")

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


async def _get_access_token(*, force_refresh: bool) -> str:
    async with token_lock:
        if not force_refresh and _has_valid_access_token():
            return token_state.access_token or ""

        response_payload = await asyncio.to_thread(_request_access_token)
        access_token = response_payload.get("access_token")
        expires_at = _normalize_expires_at(response_payload.get("expires_at"))

        if not isinstance(access_token, str) or not access_token.strip():
            raise RuntimeError("GigaChat auth response does not contain access_token")

        if expires_at <= 0:
            raise RuntimeError("GigaChat auth response does not contain expires_at")

        token_state.access_token = access_token
        token_state.expires_at = expires_at
        logger.info(
            "GigaChat access token refreshed expires_at=%s",
            _iso_datetime(expires_at),
        )
        return access_token


def _has_valid_access_token() -> bool:
    return (
        bool(token_state.access_token)
        and token_state.expires_at - TOKEN_EXPIRY_SAFETY_SECONDS > int(time.time())
    )


def _request_access_token() -> dict[str, Any]:
    form_data = parse.urlencode({"scope": config.gigachat_scope}).encode("utf-8")
    http_request = request.Request(
        GIGACHAT_AUTH_URL,
        data=form_data,
        headers={
            "Authorization": _build_basic_auth_header(config.gigachat_auth_key or ""),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "User-Agent": GIGACHAT_USER_AGENT,
        },
        method="POST",
    )

    return _perform_json_request(http_request)


def _post_chat_completion_request(
    payload: dict[str, Any],
    access_token: str,
) -> dict[str, Any]:
    raw_payload = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        GIGACHAT_CHAT_COMPLETIONS_URL,
        data=raw_payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": GIGACHAT_USER_AGENT,
        },
        method="POST",
    )

    return _perform_json_request(http_request)


def _perform_json_request(http_request: request.Request) -> dict[str, Any]:
    try:
        with request.urlopen(
            http_request,
            timeout=config.gigachat_request_timeout_seconds,
            context=_build_ssl_context(),
        ) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise GigaChatHTTPError(exc.code, error_body) from exc
    except error.URLError as exc:
        raise RuntimeError(f"GigaChat request failed: {exc}") from exc

    return json.loads(response_body)


def _build_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()

    if config.gigachat_verify_ssl:
        return context

    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _build_basic_auth_header(auth_key: str) -> str:
    stripped_key = auth_key.strip()

    if stripped_key.lower().startswith("basic "):
        return stripped_key

    return f"Basic {stripped_key}"


def _normalize_expires_at(value: Any) -> int:
    if value is None:
        return 0

    expires_at = int(value)

    if expires_at > 10_000_000_000:
        return expires_at // 1000

    return expires_at


def _iso_datetime(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _usage_value(usage: Any, field: str) -> int | None:
    if not isinstance(usage, dict):
        return None

    value = usage.get(field)

    if isinstance(value, int):
        return value

    return None


def _map_http_error_to_skip_reason(status_code: int) -> str:
    if status_code == 401:
        return "auth_failed"

    if status_code == 402:
        return "token_limit_reached"

    if status_code == 429:
        return "rate_limited"

    if status_code in {400, 413, 422}:
        return "invalid_request"

    if status_code == 403:
        return "forbidden"

    return "request_failed"


token_state = GigaChatAccessTokenState()
token_lock = asyncio.Lock()
request_lock = asyncio.Lock()
