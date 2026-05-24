---
name: phase2-progress
description: Phase 2 (LLM Integration) implementation status — what's built, what's pending, where to resume
metadata:
  type: project
---

## Phase 1 — COMPLETE

All Phase 1 code committed on branch `phase/01-foundation`. Last commit: `64640d5`.
Pending user-side steps (require Go + sqlc installed):
- `sqlc generate` for both services
- `go mod tidy` for both services
- Docker stack verification: `docker compose up`, run migrations, hit endpoints

---

## Phase 2 — LLM Integration (in progress)

Active branch: `phase/02-llm-integration`

### Done

**`ai/llm-gateway/`** — FastAPI service wrapping LiteLLM:
- `pyproject.toml` — dependencies: fastapi, uvicorn, litellm, pydantic-settings, structlog, pyyaml
- `src/config.py` — Settings via pydantic-settings; reads ANTHROPIC_API_KEY, OPENAI_API_KEY, DEFAULT_MODEL, PORT, PROMPTS_DIR
- `src/main.py` — FastAPI app; mounts `/v1/chat/completions`, `/v1/models`, `/v1/prompts`; structlog JSON logging
- `src/router/chat.py` — POST /v1/chat/completions; accepts optional `prompt_name`/`prompt_version` to inject a system prompt from the registry; maps litellm exceptions to HTTP codes
- `src/router/models.py` — GET /v1/models (curated list); GET /v1/prompts; GET /v1/prompts/{name}
- `src/prompts/registry.py` — Loads `*.yaml` from `prompts/` dir at startup; keyed as `name:version` and bare `name`
- `src/tracking/usage.py` — Calls `litellm.completion_cost()` after each response; appends JSONL to COST_LOG_PATH
- `prompts/booking-assistant-v1.yaml` — System prompt for the Phase 4 booking agent (temperature 0.3)
- `prompts/hotel-search-v1.yaml` — Structured JSON extraction prompt for NL → search filters (temperature 0.0)
- `Dockerfile` — Two-stage: uv deps install → lean python:3.12-slim runtime; exposes 8090
- `.env.example` — Documents all env vars
- Added `llm-gateway` service to `infra/docker/docker-compose.yml` (port 8090, llm_usage volume)
- Updated `.gitignore` with Python ignores (`__pycache__/`, `.venv/`, etc.)

### Pending

- Commit current Phase 2 work
- `uv sync` locally to generate `uv.lock` → commit the lock file
- Wire `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) into `infra/docker/llm-gateway.env`
- Smoke test: `curl localhost:8090/healthz` then `POST /v1/chat/completions`
- Phase 2 stretch: add `/v1/usage` endpoint to query the JSONL cost log

**Why:** All Python AI services call this gateway, never providers directly. Swapping providers is a gateway config change only.
**How to apply:** When resuming Phase 2, the gateway src is complete — next step is the env file and smoke test.
