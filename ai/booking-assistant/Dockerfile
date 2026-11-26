# ── Stage 1: install dependencies ────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ ./src/

ENV PYTHONPATH="/app/src:$PATH"

EXPOSE 8092

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8092"]
