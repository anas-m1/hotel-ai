FROM python:3.12-slim AS deps
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

FROM python:3.12-slim
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY src/ ./src/
ENV PYTHONPATH="/app/src"
EXPOSE 8100
CMD ["python", "src/server.py"]
