FROM python:3.12-slim AS deps
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /bin/uv
COPY ai/booking-assistant/pyproject.toml ai/booking-assistant/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

FROM python:3.12-slim
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/evals/agent" EVAL_DATA_DIR="/data"
COPY evals/agent /app/evals/agent
COPY ai/booking-assistant/src /app/ai/booking-assistant/src
RUN useradd --uid 10001 --create-home evaluator && mkdir /data && chown evaluator /data
USER evaluator
EXPOSE 80
CMD ["python", "-m", "uvicorn", "experiment_webhook:app", "--host", "0.0.0.0", "--port", "80", "--no-access-log"]
