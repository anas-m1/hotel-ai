"""Small Telegram polling adapter for the hotel booking assistant."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("telegram_bot")
# Telegram API URLs contain the bot token in their path. Keep HTTP request
# logging disabled so tokens can never appear in ordinary container logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ASSISTANT_URL = os.environ.get("BOOKING_ASSISTANT_URL", "http://booking-assistant:8092").rstrip("/")
ALLOWED_USER_IDS = {
    item.strip()
    for item in os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
    if item.strip()
}
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"
UPDATE_OFFSET = 0
PENDING_APPROVALS: set[str] = set()


class TelegramAPIError(Exception):
    pass


async def telegram_call(client: httpx.AsyncClient, method: str, payload: dict[str, Any]) -> Any:
    try:
        response = await client.post(f"{TELEGRAM_API}/{method}", json=payload)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        # Do not log the exception string: it may contain the token-bearing URL.
        raise TelegramAPIError(type(exc).__name__) from None
    if not body.get("ok"):
        raise TelegramAPIError("Telegram rejected the request")
    return body.get("result")


async def send_message(client: httpx.AsyncClient, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4000]}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await telegram_call(client, "sendMessage", payload)


def session_id(chat_id: int, user_id: int) -> str:
    return f"telegram-{chat_id}-{user_id}"


def is_allowed(user_id: int) -> bool:
    return str(user_id) in ALLOWED_USER_IDS


def approval_prompt(interrupt: dict[str, Any]) -> str:
    tool_call = interrupt.get("tool_call") or {}
    args = tool_call.get("args") or {}
    details = "\n".join(f"{key}: {value}" for key, value in args.items())
    message = interrupt.get("message") or "The assistant is waiting for booking approval."
    if details:
        return f"{message}\n\nBooking details:\n{details}"[:3500]
    return str(message)


async def ask_assistant(client: httpx.AsyncClient, chat_id: int, user_id: int, text: str) -> None:
    sid = session_id(chat_id, user_id)
    if sid in PENDING_APPROVALS:
        await send_message(client, chat_id, "Please approve or cancel the pending booking before sending another request.")
        return
    try:
        response = await client.post(
            f"{ASSISTANT_URL}/v1/chat",
            json={"message": text, "session_id": sid, "user_id": str(user_id)},
        )
        response.raise_for_status()
        result = response.json()
    except Exception as exc:
        log.warning("assistant_request_failed error_type=%s", type(exc).__name__)
        await send_message(client, chat_id, "The hotel assistant is temporarily unavailable. Please try again shortly.")
        return

    reply = str(result.get("reply") or "I couldn't complete that request.")
    interrupt = result.get("interrupt")
    if interrupt and interrupt.get("type") == "booking_approval":
        PENDING_APPROVALS.add(sid)
        keyboard = {
            "inline_keyboard": [[
                {"text": "Approve booking", "callback_data": "booking:approve"},
                {"text": "Cancel booking", "callback_data": "booking:cancel"},
            ]]
        }
        await send_message(client, chat_id, f"{reply}\n\n{approval_prompt(interrupt)}", keyboard)
        return
    await send_message(client, chat_id, reply)


async def handle_callback(
    telegram: httpx.AsyncClient,
    assistant: httpx.AsyncClient,
    callback: dict[str, Any],
) -> None:
    query_id = callback.get("id", "")
    actor = callback.get("from") or {}
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    user_id = actor.get("id")
    decision = callback.get("data", "")
    if not chat_id or not user_id or not is_allowed(user_id) or decision not in {"booking:approve", "booking:cancel"}:
        await telegram_call(telegram, "answerCallbackQuery", {"callback_query_id": query_id, "text": "Not authorized."})
        return

    sid = session_id(chat_id, user_id)
    if sid not in PENDING_APPROVALS:
        await telegram_call(telegram, "answerCallbackQuery", {"callback_query_id": query_id, "text": "This approval has expired."})
        return

    approved = decision == "booking:approve"
    PENDING_APPROVALS.discard(sid)
    await telegram_call(telegram, "answerCallbackQuery", {"callback_query_id": query_id, "text": "Processing approval…"})
    try:
        response = await assistant.post(
            f"{ASSISTANT_URL}/v1/chat/resume",
            json={"session_id": sid, "approved": approved},
        )
        response.raise_for_status()
        result = response.json()
        await send_message(telegram, chat_id, str(result.get("reply") or "The booking workflow finished."))
    except Exception as exc:
        log.warning("approval_resume_failed error_type=%s", type(exc).__name__)
        await send_message(telegram, chat_id, "I couldn't resume that booking workflow. Please contact support before retrying.")


async def handle_update(telegram: httpx.AsyncClient, assistant: httpx.AsyncClient, update: dict[str, Any]) -> None:
    callback = update.get("callback_query")
    if callback:
        await handle_callback(telegram, assistant, callback)
        return

    message = update.get("message") or {}
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id, user_id = chat.get("id"), user.get("id")
    text = str(message.get("text") or "").strip()
    if not chat_id or not user_id or not text:
        return

    if text.split(maxsplit=1)[0].split("@", 1)[0] == "/whoami":
        await send_message(telegram, chat_id, f"Your Telegram user ID is {user_id}.\nChat ID: {chat_id}")
        return
    if chat.get("type") != "private":
        await send_message(telegram, chat_id, "For privacy, message this bot in a private chat.")
        return
    if not is_allowed(user_id):
        await send_message(telegram, chat_id, "Access is not enabled for your account yet. Use /whoami and ask the bot owner to add your user ID to the local allowlist.")
        return
    if text.startswith("/start"):
        await send_message(telegram, chat_id, "Hotel assistant ready. Ask me to find a hotel or start a booking. Booking actions require your approval.")
        return
    if text.startswith("/"):
        await send_message(telegram, chat_id, "Available commands: /start and /whoami. You can also send a hotel request.")
        return
    await ask_assistant(assistant, chat_id, user_id, text)


async def main() -> None:
    global UPDATE_OFFSET
    if not TOKEN:
        log.error("telegram_bot_not_started: TELEGRAM_BOT_TOKEN is empty")
        raise SystemExit(2)
    if not ALLOWED_USER_IDS:
        log.warning("telegram_allowlist_empty: Only /whoami is available until a user ID is configured")

    timeout = httpx.Timeout(240.0, connect=10.0)
    async with httpx.AsyncClient(timeout=45.0) as telegram, httpx.AsyncClient(timeout=timeout) as assistant:
        log.info("telegram_bot_polling_started")
        while True:
            try:
                updates = await telegram_call(
                    telegram,
                    "getUpdates",
                    {"offset": UPDATE_OFFSET, "timeout": 30, "allowed_updates": ["message", "callback_query"]},
                )
                for update in updates or []:
                    UPDATE_OFFSET = update["update_id"] + 1
                    try:
                        await handle_update(telegram, assistant, update)
                    except Exception as exc:
                        # Do not include update payloads, exception text, or Telegram URLs in logs.
                        log.warning("telegram_update_failed error_type=%s", type(exc).__name__)
            except TelegramAPIError as exc:
                log.warning("telegram_poll_failed error_type=%s", str(exc))
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
