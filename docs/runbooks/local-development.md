# Local development

Run commands from the repository root. Requires Docker with Compose v2, GNU
Make, and sufficient RAM for the services you enable. The Makefile uses project
name `docker` and a local port overlay (PostgreSQL 55432, Redis 16379). If you
already use that project name, choose an isolated environment before starting.
Never use `make clean` to fix a startup problem: it deletes project data.

## First-time setup

```sh
make env
make setup
```

`make env` creates missing local env files without overwriting existing ones.
`make setup` starts PostgreSQL, Redis and Qdrant, creates the databases, runs
migrations, and seeds a tiny catalog. It does not install model weights.
Configure the ignored `infra/docker/*.env` files locally; never print them.

## Local model and core application

```sh
make start
# First use only; downloads model weights:
docker compose -p docker -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local-ports.yml --profile local-model \
  exec ollama ollama pull qwen3.5:4b-q4_K_M
```

Set `DEFAULT_MODEL` in `llm-gateway.env` and `AGENT_MODEL` in
`booking-assistant.env` to `ollama_chat/qwen3.5:4b-q4_K_M`. Recreate those
containers after changing env files. For a hosted provider, configure it in the
gateway, select the model in both files, and run `make MODEL_PROFILE= start`.

Build source changes with `make demo` for Telegram, or explicitly build/recreate
only affected services. A container restart does not load newly built images or
reread Compose env files.

## Telegram, retrieval, tracing

Follow [Telegram setup](telegram-bot.md), then `make demo`. It enables the
`local-model` and `telegram` profiles. Query `/whoami` privately and configure the
allowlist before assistant use. Do not start old adapter containers.

After catalog changes, explicitly rebuild the search index:

```sh
curl --fail --silent --show-error -X POST http://localhost:8091/v1/index/hotels
```

Start optional observability using `make observability`, then follow
[the tracing guide](langfuse-demo.md). Langfuse has its own authenticated Redis;
application checkpoints use the separate Redis Stack service. A small Docker VM
may not fit the model, RAG and full observability stack concurrently.

## Health and tests

Health endpoints: inventory `:8080/healthz`, booking operations `:8081/healthz`,
gateway `:8090/healthz`, RAG `:8091/healthz`, assistant `:8092/healthz`.
Health alone does not verify a working model or a complete booking workflow.
See [testing](testing.md) for deterministic checks, live evals and E2E opt-in.

`make stop` stops the core application without deleting volumes or stopping
optional modules. Stop optional services explicitly when desired; changing
profiles does not stop containers already running.

## Reproducible Python builds

Use uv 0.12.18, Python 3.12 and each service's `uv.lock`. Run `uv sync --locked`
inside a service. To intentionally update dependencies, edit `pyproject.toml`,
run `uv lock`, inspect the lock diff, and run the service's checks. Container
builds use `uv sync --locked --no-install-project --no-dev`.
