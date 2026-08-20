import re
from dataclasses import dataclass, field


URL_RE = re.compile(r"(https?://\S+|t\.me/\S+|telegram\.me/\S+)", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{4,32}\b")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
CURRENCY_RE = re.compile(r"(\$|usd\b|usdt\b|eur\b|€|₽|руб\b|рублей\b)", re.IGNORECASE)
REPEATED_PUNCTUATION_RE = re.compile(r"[!?]{3,}")

JOB_WORDS = (
    "работа",
    "подработка",
    "вакансия",
    "доход",
    "заработок",
    "зарабатывай",
    "job",
    "vacancy",
    "work",
    "income",
    "salary",
)
MONEY_WORDS = (
    "деньги",
    "прибыль",
    "оплата",
    "без вложений",
    "profit",
    "earn",
    "payment",
    "bonus",
)
CALL_TO_ACTION_WORDS = (
    "отпиши",
    "пиши",
    "в лс",
    "в личку",
    "напиши",
    "contact me",
    "dm me",
    "message me",
    "text me",
)
SCAM_WORDS = (
    "арбитраж",
    "казино",
    "ставки",
    "беттинг",
    "crypto",
    "крипта",
    "binance",
    "forex",
    "bet",
    "casino",
    "investment",
    "invest",
)


@dataclass(slots=True)
class SpamScoreResult:
    score: int
    matched_rules: list[str] = field(default_factory=list)


def score_message_text(text: str, content_type: str) -> SpamScoreResult:
    normalized = " ".join(text.split())
    lowered = normalized.lower()
    score = 0
    matched_rules: list[str] = []

    def add(points: int, rule: str) -> None:
        nonlocal score
        score += points
        matched_rules.append(f"{rule}:{points}")

    if URL_RE.search(normalized):
        add(2, "url")

    if MENTION_RE.search(normalized):
        add(2, "mention")

    if PHONE_RE.search(normalized):
        add(2, "phone")

    if CURRENCY_RE.search(normalized):
        add(2, "currency")

    if _contains_any(lowered, JOB_WORDS):
        add(2, "job_words")

    if _contains_any(lowered, MONEY_WORDS):
        add(1, "money_words")

    if _contains_any(lowered, CALL_TO_ACTION_WORDS):
        add(2, "call_to_action")

    if _contains_any(lowered, SCAM_WORDS):
        add(2, "scam_words")

    if content_type != "text":
        add(1, "media_or_caption")

    if _has_high_uppercase_ratio(normalized):
        add(1, "uppercase_ratio")

    if REPEATED_PUNCTUATION_RE.search(normalized):
        add(1, "repeated_punctuation")

    if len(normalized) >= 180:
        add(1, "long_message")

    return SpamScoreResult(score=score, matched_rules=matched_rules)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _has_high_uppercase_ratio(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]

    if len(letters) < 8:
        return False

    uppercase_letters = sum(1 for char in letters if char.isupper())
    return uppercase_letters / len(letters) >= 0.6
