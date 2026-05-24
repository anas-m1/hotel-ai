# Stage 1: install deps and pre-download embedding models
FROM python:3.12-slim AS deps

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /bin/uv

COPY pyproject.toml .
RUN uv sync --no-install-project --no-dev

# Pre-download both embedding models into the image so the container starts
# without fetching ~100 MB at runtime. Models land in ~/.cache/fastembed.
RUN .venv/bin/python -c "\
from fastembed import TextEmbedding; \
from fastembed.sparse import SparseTextEmbedding; \
TextEmbedding('BAAI/bge-small-en-v1.5'); \
SparseTextEmbedding('Qdrant/bm42-all-minilm-l6-v2-attentions')"

# Stage 2: lean runtime
FROM python:3.12-slim

WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
COPY --from=deps /root/.cache/fastembed /root/.cache/fastembed

ENV PATH="/app/.venv/bin:$PATH"

COPY src/ ./src/

EXPOSE 8091
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8091"]
