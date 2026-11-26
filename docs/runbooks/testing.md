# Test layout and commands

Tests stay versioned with the product. Location follows their ownership rather
than a lesson number.

## Go package tests

Keep `booking_test.go` beside `booking.go`. `package handler` can access package
internals; `package handler_test` tests the exported API from an external view.
Both live in the same directory and are excluded from normal application builds.

A service integration test can also live there as `booking_integration_test.go`.
The name is descriptive only: Go runs it normally unless gated. Use
`//go:build integration` plus `go test -tags=integration ...`, or explicit runtime
opt-in for tests needing PostgreSQL. Put fixtures in `testdata/`.

```sh
make test-go
# Equivalent:
go test ./services/hotel-inventory/... ./services/booking-ops/...
```

sqlc-generated Go source is versioned so clean checkouts compile. After changing
SQL or migrations, regenerate with sqlc v1.31.1 and review the generated diff.

## Python service tests

Pytest supports both colocated and separate test directories. Here we use:

```text
ai/booking-assistant/
  src/agent/nodes.py
  tests/test_agent_regressions.py
  tests/test_booking_agent.py
  pyproject.toml
  uv.lock
```

This keeps tests next to the service they belong to without copying them into the
runtime image. Per-service configuration sets imports and dependency isolation.
Do not run all Python services in one interpreter: several currently use generic
module names such as `config`, `agent`, and `src`.

```sh
make test-agent
# Or from ai/booking-assistant:
uv run --locked pytest tests/ -v
```

These deterministic tests use scripted model responses and an in-memory
checkpointer; they make no model/backend calls. They cover graph routing, tool
budgets, retained conversation history, approval/cancellation and trace labels.

## Cross-service and model checks

`tests/e2e/` owns workflows crossing service boundaries. The current test verifies
inventory/booking HTTP contracts, availability conflict, retrieval and cancellation.
It creates a fictional guest (retained as test data) and cancels the reservation
in a finally block. Run only against disposable local data:

```sh
HOTEL_AI_E2E=1 uv run --locked --project ai/booking-assistant pytest tests/e2e/ -v
```

For an isolated run without Docker, if PostgreSQL 16 binaries and `btree_gist`
are installed locally:

```sh
python3 scripts/test-backend-isolated.py
```

The runner builds both Go APIs, starts a temporary local PostgreSQL cluster,
applies migrations/seed data, runs the E2E test, then stops and removes its own
test resources. It does not use the normal application databases. It also runs
`booking_integration_test.go` beside the Go repository code: date overlap and
adjacent-stay boundaries, cancellation, and the PostgreSQL exclusion constraint.
Named SQL parameters prevent sqlc from inferring reversed check-in/out bindings. An alternative
PostgreSQL binary directory can be supplied with `--pg-bin`.

Without opt-in, the test is skipped. It does not verify model inference, Telegram
transport, or a real approval button. The previous all-phase script claimed those
properties but used obsolete API fields; it was replaced rather than presented
as passing evidence.

`evals/agent/` checks live model tool selection and basic answer terms.
`evals/retrieval/` checks retrieval ranking. Run `make eval-agent` and
`make eval-retrieval`; reports go to `/tmp` so historical baselines are preserved.
A trace explains an execution; an eval judges it against expected behavior.

## CI

CI tests/vets each real Go module, runs the booking assistant tests from its locked
environment, checks Python source lint, verifies sqlc regeneration, runs the temporary-database
integration suite, and builds product and eval-webhook images. Node 22+ runs
the TypeScript evaluator parity checks. The eval tests use the assistant's locked environment. Remote CI results must be
checked after a push; local checks do not establish that remote CI has passed.

References:
- https://pkg.go.dev/testing
- https://docs.pytest.org/en/stable/explanation/goodpractices.html
