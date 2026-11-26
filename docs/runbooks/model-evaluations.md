# Comparing models, agent workflows, and inference servers

Treat each run as an experiment with a fixed dataset/scorer and an explicitly
identified runtime. Change one variable at a time. The default draft suite has
20 development scenarios; `heldout_cases.json` has five held-out prompts over the
same three seeded hotels. `smoke_cases.json` preserves the original quick checks.
These are learning datasets, not a broad production benchmark.

## What to compare

| Question | Hold fixed | Change |
| --- | --- | --- |
| Which model works better? | Workflow, tools, prompts, catalog, sampling settings | Model |
| Did a workflow change help? | Model, catalog, scorer, serving environment | Workflow/prompt/tool policy |
| Is self-hosting worthwhile? | Ideally same model weights/revision and prompts | Serving stack/hardware |

Use a four-cell experiment (model A/workflow 1, B/1, A/2, B/2) to investigate an
interaction after the individual comparisons. Do not change retrieval, model,
workflow and hardware together and attribute all differences to the model.

Run deterministic regressions first (`make test`). Use a disposable, consistently
seeded catalog and the same Qdrant index. Use fictional data. Eval requests explicitly set read-only mode: the assistant blocks every tool
outside a read-only allowlist, even if the model requests a mutation. Blocked
proposals still fail safety/tool-selection scoring. This mode does not exercise
actual booking creation or live approval/resume. Use fictional test data and
fresh sessions; each scenario/repeat gets a new session, while turns within a
scenario share it. Automatic HTTP retries are disabled because a failed response does
not prove its tools did not execute.

## Record a baseline

Deploy the current source first. The assistant exposes `/v1/eval-info` with model,
temperature, step budget and a SHA-256 of the deployed Python source. The runner
checks that source against this checkout and can enforce the expected model.
It also checks that runtime identity stays stable during the run.

```sh
python3 evals/agent/evaluate_agent.py \
  --variant baseline-model-a-workflow-1 \
  --expected-model 'ollama_chat/qwen3.5:4b-q4_K_M' \
  --fixture-label seeded-catalog-v1 \
  --repeats 3 \
  --output evals/agent/runs/baseline.json
```

An eval with failed cases writes its report and exits nonzero; keep the artifact.
Run artifacts under `runs/` are ignored by Git. Keep selected reviewed baselines
separately when intentionally versioning an experiment. Reports include answers,
tool names, errors, session IDs, repeat index, model/workflow identity, checkout
commit/dirty status, dataset hash and scoring version. They exclude env files and
provider keys. Suites declaring `catalog_fixture.json` verify catalog facts via
the inventory API before inference and save a fixture hash. A mismatch stops the
run. This does not verify Qdrant contents or all database state. Fixture labels
alone remain human assertions for custom suites without a fixture.

For a different remote checkout, deliberately use `--allow-different-source` and
inspect the recorded runtime hash. That flag should not hide a forgotten rebuild.
Historical reports lacking the new dataset/scorer identity cannot be compared by
the new tool; rerun the baseline instead of inventing missing provenance.

## Make one change and compare

For a model change, edit `AGENT_MODEL` in ignored `booking-assistant.env`.
`DEFAULT_MODEL` in `llm-gateway.env` should match for direct gateway calls; the
assistant explicitly sends its own model, so changing only DEFAULT_MODEL will not
switch the agent. Set provider credentials only in the gateway's local env file.
For a workflow change, edit source, run tests, and rebuild the assistant.

After code/env changes, recreate the affected services from the project root:

```sh
docker compose -p docker -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local-ports.yml --profile telegram \
  up -d --build --no-deps llm-gateway booking-assistant
```

This command requires existing backend dependencies. Start the configured model
host separately when using local inference. Run the same eval command with a new
variant label, the actual expected model, and `--output .../candidate.json`.
Then compare:

```sh
python3 evals/agent/compare_runs.py \
  evals/agent/runs/baseline.json evals/agent/runs/candidate.json \
  --output evals/agent/runs/comparison.json
```

The comparator requires the same dataset hash, scorer/evaluator hash, fixture
label and verification/hash status, cases and repeat count. It reports paired improvements/regressions, pass-rate delta, forbidden-tool
failures, request errors, and p50/p95 latency. Operational failures have a separate
count and are excluded from answer-quality rates and latency. Paired quality
comparisons use only cases evaluated successfully in both runs; recovering from
an outage is reported as an operational transition rather than a quality gain.

Use model/provider usage in Langfuse/OpenRouter for tokens and cost. The runner
currently does not collect reliable per-run costs or token totals. Join traces via
the session IDs saved in each case. Local zero-priced generations do not account
for GPU rental, hardware, memory or electricity.

## Interpret results

Start with per-case failures rather than the overall percentage. Inspect wrong
tool choice/arguments, repeated calls, unsupported answer claims, missing
clarifications and latency. Require no safety regressions even if average quality
improves. More repeats expose variability but are not a substitute for more cases.
A percentile over nine requests is descriptive, not a serving benchmark.

Current cases cover hotel/room facts, quote calculations, structured and semantic
search, missing records, clarification, unsafe requests, unsupported discounts,
and multi-turn context. Requested JSON facts check prices, currency, capacity,
names and addresses; array order and equivalent numeric formats are tolerated,
but extra invented fields fail. JSON format failures remain distinct from fact
mismatches. Natural-language cases still use limited term/alias checks.

Keep tuning cases separate from held-out cases. The live runner handles ordinary
multi-turn chat, not approval/resume or mutation scenarios. Deterministic graph
tests cover approval/cancellation; backend integration tests cover real writes.
Tool service failures are recorded rather than masquerading as empty catalogs.
Substring scoring remains weak evidence for full factual grounding. Use `evals/agent/export_review.py` and `evals/agent/review-rubric.md` to review
saved answers. Scores are blank until a human reviews them; operational failures
receive no answer-quality score. Do not rely on this small suite for customer readiness. LLM judges
can help scale review, but need a rubric and calibration against human judgments.

## OpenRouter now

In `infra/docker/llm-gateway.env`, enter the key locally as `OPENROUTER_API_KEY`.
Do not paste it into chat or shell commands. Choose a current model ID supporting
tools; configure `openrouter/<publisher>/<model-id>` as AGENT_MODEL and DEFAULT_MODEL.
The LiteLLM `openrouter/` prefix is in addition to the publisher/model identifier.
The gateway uses https://openrouter.ai/api/v1 and forwards the tools.

Use an explicit model ID for comparisons; avoid automatic model routing/aliases.
OpenRouter can route the same model through different upstream providers; record
that provider from its activity/traces when interpreting results. This gateway
does not currently pin OpenRouter's upstream provider. No live paid request is
made by the offline routing tests.

## Self-hosted inference later

The application path remains assistant → gateway → inference server. Ollama is
already one local serving option. For a later vLLM/OpenAI-compatible server:

```dotenv
# Gateway only: use a real endpoint reachable from the gateway container.
SELF_HOSTED_API_BASE=http://inference:8000/v1
SELF_HOSTED_API_KEY=
DEFAULT_MODEL=hosted_vllm/<served-model-name>
# Assistant env:
AGENT_MODEL=hosted_vllm/<served-model-name>
```

`inference` above is an illustrative DNS name; no server/container is provisioned
by this change. A remote server can use HTTPS. `localhost` inside the gateway is
the gateway itself. Docker Desktop can reach a host endpoint through
`host.docker.internal`; plain Linux Docker may require a host-gateway mapping.

Validate basic chat AND tool calling before a full agent eval. vLLM tool-call
parser/chat-template options depend on the model; an OpenAI-compatible HTTP API
alone does not guarantee correctly parsed tools. Record weight revision,
quantization, context length, sampling settings, serving version, hardware and
concurrency. Benchmark throughput/latency separately from task quality.

Self-hosting existing open weights is separate from training/fine-tuning. First
establish a hosted baseline, then choose hardware and a model that fit the memory
budget. The observed small Docker VM already struggled with the local model plus
Langfuse. This change does not rent a GPU, download new weights or deploy an
inference server.

References:
- https://docs.litellm.ai/docs/providers/openrouter
- https://openrouter.ai/docs/guides/features/tool-calling
- https://docs.litellm.ai/docs/providers/vllm

## Development and held-out runs

Run the default development suite first. For held-out measurement, repeat the
same command with `--cases evals/agent/heldout_cases.json` and a separate output.
Compare development runs only with development runs, and held-out with held-out.
Start with one repeat to estimate local cost/time; use at least three repeats for
subsequent model comparisons, and never treat a single pass as a stable ranking.

With a constrained Docker VM, optional observability competes with the local
model for RAM. Record whether tracing was enabled and the context length in
`--environment-label`. An observation stack being paused is an operational choice,
not an answer-quality improvement. Keep the setup consistent across comparisons.

## Dashboard-triggered full-agent experiments

The imported `hotel-agent-dev` (20 items) and `hotel-agent-heldout` (5 items)
retain their stable item IDs and multi-turn rules. The dashboard webhook runs the
same `execute_turns` transport as the CLI runner, with enforced read-only mode.
It does not calculate answer-quality scores. Langfuse executes the versioned
`evals/agent/evaluators/hotel_agent.ts` against the complete scenario evidence.
It accepts native objects or JSON-encoded context fields and uses the dedicated
per-turn metadata rules because 4.36 flattens nested `source_case` metadata.
The Python scorer remains for offline regressions and historical CLI reports;
parity tests check both implementations against the suites and failure modes.

Verified on Langfuse web/worker **4.36.0**, Python SDK **5.2.0**, and the installed
worker's `LocalCodeEvalDispatcher.dispatch()`: TypeScript returns a valid native
score. No Langfuse upgrade or AWS Lambda is needed. On this version, the local user
also needs `experimentsV4Enabled` and `observationEvals` feature flags, plus v4
beta UI enabled, to see native SDK experiments and evaluator screens. These
were enabled for the existing local user without changing account permissions. The `insecure-local`
dispatcher executes trusted evaluator code in the Langfuse process, not a secure
sandbox. Use only repository-reviewed code in this local learning deployment.

The Compose override `infra/docker/docker-compose.evals.yml` enables that
dispatcher on web/worker, enables its execution queue with concurrency one, and
allowlists only `hotel-agent-evals` for the local webhook. It adds a non-root,
read-only webhook container and a named volume holding its SQLite job queue.
Its host port is bound to `127.0.0.1:8096`; no public tunnel is required.

Create ignored `infra/docker/agent-evals.env` using its example: reuse the
project's Langfuse API keys, set the project ID, and generate a random webhook
token locally. Never paste these values into chat, terminal output, or Git.
Start from the project root, with core dependencies already running:

```sh
docker compose -p docker \
  -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local-ports.yml \
  -f infra/docker/docker-compose.evals.yml \
  --profile evals --profile observability \
  up -d --build --no-deps hotel-agent-evals booking-assistant langfuse-web langfuse-worker

docker exec docker-hotel-agent-evals-1 \
  python /app/evals/agent/setup_langfuse_evaluator.py
```

The setup publishes a content-addressed evaluator and creates its automatic rule.
The rule targets only experiment-item root observations named
`hotel-agent-scenario` with the matching evaluator hash. The full hash uses a `contains` filter because
4.36.0 stores string metadata as JSON text during in-memory rule matching. Do not attach a second
copy of the same evaluator manually. Re-running setup preserves the existing
version. Changing evaluator source creates a new version-specific evaluator;
old runs must be rescored with the same definition before comparing scores.

For each dataset, open **Experiments → More actions → Run Experiment → via
Webhook → Configure** (on wider screens the experiment button may be visible
without More actions). Set URL `http://hotel-agent-evals/experiments`. Under
Advanced Options add a **secret** `Authorization` header with value `Bearer `
followed by the local webhook token. The service authenticates this header;
Langfuse request signing is optional and is not used as the authentication check.
Never put the token in the URL or payload.

The existing local installation was provisioned using
`evals/agent/configure_dashboard.cjs` with Langfuse's own Prisma/encryption
helpers because 4.36.0's public dataset API does not expose webhook settings.
That installation-specific helper only updates these two datasets, refuses to
overwrite an unrelated webhook URL, and accepts secrets privately on stdin.
It is not part of runtime execution. The dashboard remains the normal editor.

Use this non-secret payload for the initial one-item check, substituting a fixed,
timezone-aware dataset snapshot timestamp taken after import and a unique run
name:

```json
{
  "run_name": "local-smoke-v1",
  "variant": "local-qwen-workflow-v1",
  "expected_model": "ollama_chat/qwen3.5:4b-q4_K_M",
  "dataset_version": "2026-11-22T05:33:51.332244+00:00",
  "case_ids": ["facts_HTL002"],
  "repeats": 1
}
```

Click **Run**. A success toast confirms webhook acceptance, not experiment or
scoring completion. The service queues the request and acknowledges immediately.
It fetches the pinned dataset, verifies the hosted inputs/answers/tool rules
against the repository, verifies the inventory fixture and deployed model/source,
and records source, prompt, fixture, dataset and evaluator hashes. Each scenario
gets a fresh session; its turns share that session. Cumulative tool results are
deduplicated by call ID. W3C context links assistant activity under the experiment
trace. Raw evidence includes replies, tool outcomes, interruptions and latency.

The queue persists across restarts. Duplicate deliveries with the same dataset
and run name return the original job; a different config using that name is
rejected. To intentionally retry a failed job, use a **new** run name. A running
job interrupted by process restart is marked failed rather than replayed.
Only one job executes at once, and at most two jobs may be queued/running.
Authenticated `GET /jobs/{job_id}` reports status; exception text and credentials
are not logged or returned. Read-only mode also blocks future unknown tools.

Confirm the one-item experiment has its expected output, linked agent/tool
activity, and native scores before running the full suite. Remove `case_ids` and
choose a new run name for a full run. `repeats` accepts 1–3 and creates separately
named repeat experiments. Held-out items use the same procedure in their own
dataset; do not use development-only case IDs there.

Scores are `operational_success`, `safety`, `task_success`, `tool_selection`,
`answer_terms`, `format`, and `facts`. Facts are omitted when the scenario has no
structured fact assertion. Operational failures omit inapplicable quality scores;
an observed unsafe tool proposal still fails safety, even if execution was
blocked. Missing scores mean N/A or unfinished scoring, never an automatic pass.
Invalid JSON fails format and the requested-facts check. Human usefulness and
broad semantic grounding are not graded by this deterministic evaluator.

For model comparisons, keep `dataset_version`, workflow source, prompt, fixture,
evaluator, selected case scope and repeat count fixed. Switch only the configured
model/provider in the local gateway/assistant env, recreate those affected
services, then set the actual `expected_model` and a unique run name in the
webhook payload. A payload label cannot switch providers or deploy a workflow.
After changing workflow or prompt source, rebuild both `booking-assistant` and
`hotel-agent-evals`: the webhook image contains the source identity it verifies.
A model-only env change does not require rebuilding that source copy.

The service rejects arbitrary endpoints, prompts, and generation settings in the
payload. This prevents the dashboard configuration from silently changing the
application under test. Record quantization/context/hardware separately when
comparing Ollama, OpenRouter and Runpod; identical prompts alone do not make
different serving stacks identical.

In **Experiments**, select the comparable runs and click **Compare**. Inspect
per-item regressions and linked traces as well as aggregate scores. Do not compare
a smoke subset's average to a full run. Check operational failures separately,
and include GPU uptime/idle charges when assessing Runpod cost. The fixture
preflight validates the inventory catalog, not a complete Qdrant index snapshot.

## Recorded comparison

See [the evaluation summary](../../evals/results/2026-11-22.md) for the small
recorded local/Groq/OpenRouter comparison and its limitations. Instance-specific
URLs, dated webhook payloads and deployment planning notes are archived in
hotel-ai-lab. Create fresh run names and a snapshot from your own dataset import;
the timestamp in this guide is an example, not a value to copy into a new project.
