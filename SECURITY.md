# Security and data handling

This project is a local prototype. Do not expose its domain APIs or development
databases directly to customer traffic. Compose contains deliberately simple
local-only credentials; production deployment requires a separate security design.

Provider keys, Telegram tokens and Langfuse API keys belong only in ignored local
env files. Copy the example templates and fill them in using a local editor.
Never include credentials in screenshots, commands, logs, issues or commits.
If a credential is exposed, revoke/replace it before further use.

Use fictional guest data in demos and evals. Traces may contain full prompts,
conversation history and tool outputs. Review/redact exported evidence before
sharing it. Raw eval runs and caches are ignored by Git.

The Telegram allowlist is a demo access restriction, not a complete customer
authorization system. Approval buttons do not replace database constraints or
idempotency. The local Langfuse TypeScript dispatcher executes trusted evaluator
code in its worker process; do not accept untrusted evaluator source.

When reporting a security issue, describe the affected component and a safe
reproduction. Do not publish live credentials or real guest records.
