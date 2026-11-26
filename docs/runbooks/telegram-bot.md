# Telegram bot setup

The Telegram bot is an optional polling adapter for the hotel booking assistant. It calls the existing `booking-assistant` API over the private Docker network; it does not call the model provider directly. Telegram messages use a stable per-user conversation ID, so LangGraph state is restored from Redis between bot restarts.

## 1. Create a bot and token

In Telegram, open [@BotFather](https://t.me/BotFather), send `/newbot`, and follow
the prompts. Enter the token directly in the ignored local env file below.
If a token has been exposed, replace it using BotFather before continuing.
Never paste tokens into Git, screenshots, shell commands or logs.

## 2. Prepare local settings

Create local environment files if needed:

```sh
make env
```

Edit `infra/docker/telegram-bot.env` locally and set `TELEGRAM_BOT_TOKEN`. Leave `TELEGRAM_ALLOWED_USER_IDS` empty for the first startup; in that state the bot accepts only `/whoami` and does not forward messages to the assistant.

## 3. Start the local app and bot

Start the core app services first, then start only the optional bot service:

```sh
docker compose -p docker \
  -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local-ports.yml \
  --profile telegram \
  up -d --build hotel-ai-telegram-adapter
```

The bot runs in polling mode, so no public webhook or inbound port is needed. In a private Telegram chat, send `/whoami`. Copy the numeric user ID into `TELEGRAM_ALLOWED_USER_IDS` in `infra/docker/telegram-bot.env`, then restart the bot:

```sh
docker compose -p docker \
  -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local-ports.yml \
  --profile telegram \
  up -d --force-recreate hotel-ai-telegram-adapter
```

Only allowlisted users can send assistant requests or approve bookings. Group chats are not forwarded. Booking approval appears as inline Approve and Cancel buttons and resumes the same LangGraph conversation.

## Logs and troubleshooting

```sh
docker compose -p docker \
  -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local-ports.yml \
  --profile telegram \
  logs -f hotel-ai-telegram-adapter
```

The bot intentionally suppresses HTTP client request logs because Telegram API URLs contain the bot token. Do not enable verbose HTTP logging. If a token is ever printed or committed, revoke it with BotFather and replace it in the ignored local environment file.
