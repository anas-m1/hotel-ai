# Local Langfuse tracing walkthrough

Open http://localhost:3000, create your own account/project, and add its API keys
to the ignored gateway and assistant env files. Never paste keys
or passwords into chat, terminal commands, screenshots, or a video.

## Start the observability stack

From the repository root:

```sh
docker compose -p docker \
  -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local-ports.yml \
  --profile observability \
  up -d clickhouse minio langfuse-redis langfuse-worker langfuse-web
```

This reuses PostgreSQL and starts Langfuse's own Redis queue/cache, ClickHouse
trace storage, MinIO event storage, worker, and web UI. Application conversation
checkpoints remain in the separate `redis` service. No public tunnel is needed.

The browser uses http://localhost:3000; application containers use
http://langfuse-web:3000. Langfuse credentials belong in ignored local env files.
If those files change, recreate the affected application containers; a plain
restart does not reread Compose env files.

## Generate and locate a trace

In Telegram, ask `Find hotels in LHR. Do not book anything.` Wait for the reply.
In Langfuse, select your project, open Tracing/Traces, refresh, and select the
recent `hotel-booking-agent` trace. Widen the time range if necessary.

The agent config attaches:

- Trace name: `hotel-booking-agent`.
- Session: the conversation ID, such as `telegram-<chat-id>-<user-id>`.
- User: the Telegram numeric user ID on ordinary chat requests.
- Tags: `hotel-ai` and `booking-assistant`.

Find your conversation under Sessions, or filter traces by its session ID.
Approval resumes use the same session ID; the resume endpoint does not currently
receive a user ID. Session labels group turns; each invocation still has its own
trace ID. Historical traces created before these labels may not be grouped.

## Read an execution

Expand the trace tree or timeline. A search should resemble:

```text
hotel-booking-agent
  agent
    ChatOpenAI: model proposes search_hotels
  tools
    search_hotels: inventory result
  agent
    ChatOpenAI: model writes final answer
```

Actual names and nesting depend on the SDK. Select a model generation to inspect
its input messages, tool schemas, proposed arguments, output, model name, and
usage if provided. Select a tool observation to inspect its arguments, returned
hotel data, and duration. Compare the final answer against the tool result.

Use the timeline to locate latency: slow model calls, repeated agent/tool loops,
or slow tools. The local CPU model may take tens of seconds. Trace duration can
include child durations, so do not add a parent duration to its children's times.

Common investigations:

| Symptom | Inspect |
| --- | --- |
| Wrong tool or city | Model tool call and its arguments |
| Correct tool, wrong hotels | Tool output; then retrieval/catalog data |
| Correct data, invented price | Final generation input and output |
| Long response | Timeline and repeated calls |
| Failed request | Error observations and the last completed span |

For booking, inspect the initial request and approval resume within the same
session. Interrupting for approval is expected workflow behavior. Use fictional
guest data for a filmed demo; captured prompts and tool outputs can contain guest
information. Do not film account/API-key settings.

## Limits and troubleshooting

- The assistant's LangChain callback records the agent tree. The gateway's
  LiteLLM callback may produce separate traces; distributed HTTP trace context
  is not explicitly propagated between them.
- A tool span covers its HTTP call, not automatically the Go service internals.
- Local model costs may be zero or unknown; this does not measure CPU/electricity
  cost. Missing usage fields mean unavailable accounting, not no work.
- SDK export and worker ingestion are asynchronous. Refresh after a short delay.
  This stack has a legacy ingestion migration bridge that may delay older-format
  gateway records further; use fresh agent traces to verify the main workflow.
- Health checks alone do not prove ingestion. Verify that a fresh request appears
  with the expected session and child observations.
- If nothing appears, check the selected project/time range, credential presence,
  the internal host, and all five observability service states. Diagnose with
  sanitized status/error categories rather than dumping env files or raw logs.
- A trace explains a run; evals judge it. Use failed traces to add reproducible
  cases to `evals/agent/agent_cases.json`.

Official references:
- https://langfuse.com/integrations/frameworks/langchain
- https://langfuse.com/docs/observability/features/sessions
- https://langfuse.com/self-hosting/deployment/docker-compose
