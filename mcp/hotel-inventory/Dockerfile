FROM python:3.12-slim AS deps
WORKDIR /app
RUN pip install uv --no-cache-dir
COPY pyproject.toml .
RUN uv sync --no-install-project --no-dev

FROM python:3.12-slim
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY src/ ./src/
ENV PYTHONPATH="/app/src"
EXPOSE 8100
CMD ["python", "src/server.py"]
