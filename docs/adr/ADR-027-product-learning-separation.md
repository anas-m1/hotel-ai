# ADR-027: Product, experiments, learning and test ownership

**Status:** Accepted

## Context

The repository mixed a working Telegram booking path, empty service scaffolds,
experimental architectures, numbered lessons, and operational instructions.
Default startup could launch unrelated heavy services. Tests were attached to
lesson numbers and Python builds resolved new versions on each rebuild.

## Decision

Keep the Go APIs and Python assistant/gateway/RAG in the product tree. Keep
Telegram and MCP under `integrations/`. Move alternative architectures into
`experiments/`, teaching material into `learning/`, and current operational docs
into `docs/runbooks/`. Retain ADRs beside the code as versioned rationale.
Remove verified empty scaffolds and an unused conversation store.

Keep Go tests beside their packages. Put Python tests in each service's `tests/`
directory, cross-service tests under root `tests/e2e/`, live model/retrieval cases
under `evals/`. Gate tests needing live services/data with explicit opt-in.
Use per-service uv locks, locked builds, and versioned sqlc-generated Go source.

Keep Compose service names, project `docker`, and data-volume names stable.
Make observability, local inference, MCP, event experiments, and developer tools
explicit profiles. Profiles do not stop containers already running.

## Consequences

Repository moves require updated CI/build paths and imports, but do not require a
rewrite of booking logic. Historical lessons may retain examples of earlier
architectures; root docs describe current behavior. Deployment is a manual
blueprint, not an automatic claim that cloud behavior has been validated.

This change does not implement durable idempotency, atomic booking/audit writes,
price validation, or production authorization. Those are separate behavior
changes requiring explicit design and meaningful integration tests.

## Follow-up: separate repositories (26 November 2026)

Learning notes, assistant planning/memory, experimental implementations and
unverified AWS deployment blueprints now live in a sibling hotel-ai-lab
repository. Product code, tests, evals, operating docs and applicable ADRs remain
here. Experimental Compose services and their CI jobs move with their code.
Service names and active data volumes remain unchanged; no runtime services
are restarted by this documentation/repository split.
