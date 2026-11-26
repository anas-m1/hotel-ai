# Stage 1: install deps and pre-download embedding models
FROM python:3.12-slim AS deps

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,id=hotel-ai-rag-uv,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --no-install-project --no-dev

# Pin the cache to a known path inside WORKDIR (avoids home-dir ambiguity
# and works correctly when the runtime container runs as a non-root user).
ENV FASTEMBED_CACHE_PATH=/app/models
RUN .venv/bin/python -c "\
from fastembed import TextEmbedding; \
from fastembed.sparse import SparseTextEmbedding; \
TextEmbedding('BAAI/bge-small-en-v1.5'); \
SparseTextEmbedding('Qdrant/bm42-all-minilm-l6-v2-attentions')"

# Stage 2: lean runtime
FROM python:3.12-slim

WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
COPY --from=deps /app/models /app/models

ENV PATH="/app/.venv/bin:$PATH"
ENV FASTEMBED_CACHE_PATH=/app/models

COPY src/ ./src/

EXPOSE 8091
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8091"]
