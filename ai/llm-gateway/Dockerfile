# Stage 1: install Python dependencies
FROM python:3.12-slim AS deps

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /bin/uv

COPY pyproject.toml .
# Install deps only (not the project package itself) — keeps this layer cacheable
RUN uv sync --no-install-project --no-dev

# Stage 2: lean runtime image
FROM python:3.12-slim

WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ ./src/
COPY prompts/ ./prompts/

EXPOSE 8090
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8090"]
