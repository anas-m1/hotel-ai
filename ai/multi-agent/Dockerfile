# ── Stage 1: install dependencies ────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app
RUN pip install uv --no-cache-dir

COPY pyproject.toml .
RUN uv sync --no-install-project --no-dev

# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ ./src/

# shared/events/ is mounted at runtime via docker volume; also support build-time copy
# PYTHONPATH includes src/ (for absolute imports) and /app/shared (for booking_events)
ENV PYTHONPATH="/app/src:/app/shared"

EXPOSE 8093

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8093"]
