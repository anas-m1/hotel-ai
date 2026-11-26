# Live evaluations

- `agent/agent_cases.json`: 20 development cases, including ordinary multi-turn context.
- `agent/heldout_cases.json`: five held-out prompts over the same tiny catalog.
- `agent/smoke_cases.json`: original three quick cases.
- `agent/catalog_fixture.json`: expected seeded facts, verified through inventory.
- `retrieval/`: relevant hotel codes, recall@k and reciprocal rank.

The agent runner uses enforced read-only tools, fresh sessions per scenario/repeat,
verified runtime/source identity, structured JSON facts where requested, and
separate operational/answer-quality metrics. Compare saved reports with
`agent/compare_runs.py`. Human review templates/rubric are in `agent/`.

Run `make eval-agent` or `make eval-retrieval` with live services. Defaults write to
`/tmp`; use an explicit output under `agent/runs/` for comparisons. Run artifacts
are ignored; historical versioned baselines are not current quality claims.

Read `docs/runbooks/model-evaluations.md` for setup and limitations. The offline
test command and dependencies are listed below.

Dashboard experiments use `agent/experiment_webhook.py` and the shared raw-turn
executor from `agent/evaluate_agent.py`. The canonical dashboard evaluator source
is `agent/evaluators/hotel_agent.ts`; publish it with
`agent/setup_langfuse_evaluator.py`. See the dashboard section of the runbook for
the Compose override, authentication, dataset snapshots and comparison steps.
No Lambda or public tunnel is needed for this local setup.

The expanded offline suite includes Node-based evaluator parity and FastAPI
webhook checks. Run it with the assistant's locked Python dependencies and Node
22+ available, for example:

```sh
uv run --project ai/booking-assistant python -m unittest discover -s evals/tests -v
```
