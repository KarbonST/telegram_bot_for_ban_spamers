from aiogram.types import Chat, User


def chat_repr(chat: Chat) -> str:
    parts = [f"id={chat.id}", f"type={chat.type}"]

    if chat.title:
        parts.append(f"title={chat.title!r}")

    if chat.username:
        parts.append(f"username=@{chat.username}")

    return "chat(" + ", ".join(parts) + ")"


def user_repr(user: User) -> str:
    parts = [f"id={user.id}", f"name={user.full_name!r}"]

    if user.username:
        parts.append(f"username=@{user.username}")

    return "user(" + ", ".join(parts) + ")"


def text_preview(text: str | None, limit: int = 160) -> str:
    if text is None:
        return "<no-text>"

    sanitized = " ".join(text.split())

    if len(sanitized) <= limit:
        return sanitized

    return sanitized[: limit - 3] + "..."
