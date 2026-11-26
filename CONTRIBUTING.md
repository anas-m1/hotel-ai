# Contributing

Read the architecture and relevant ADRs before changing service boundaries.
Keep a change focused and explain the user-visible behavior plus validation.

- Run `make test` for deterministic checks. Tests do not require paid inference.
- Run `make test-backend-isolated` for booking SQL or lifecycle changes. It uses
  temporary PostgreSQL data, not the normal application database.
- Run live evals only against fictional data and a deliberately configured model.
  Provider calls may consume credits or rate limits. Compare matching datasets,
  workflows and evaluator versions; report operational failures separately.
- Keep Go tests beside their packages and Python tests within each service.
- Use `uv sync --locked`; regenerate SQL bindings with sqlc 1.31.1 after SQL edits.
- Keep real credentials, raw conversation exports and local env files out of Git.
- Use the companion hotel-ai-lab repository for learning notes and experiments.

No cloud deployment is triggered by this repository's CI. CI builds and tests
without publishing images. Do not use `make clean` for routine troubleshooting:
it removes local volumes.
