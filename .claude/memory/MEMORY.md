# Project Memory Index

Project-scoped memory for hotel-ai. Loaded automatically via CLAUDE.md.

## Entries

- [Phase 1 Progress](phase1-progress.md) — what's built, what's pending, exact next steps to resume Phase 1
- [Architecture Decisions](architecture-decisions.md) — tool choices, tradeoffs, and the discussions behind them (language split, sqlc, Chi, Qdrant, LangGraph, MCP design, event sourcing, optimistic locking)
- [Architecture Decisions (detailed)](arch-decisions.md) — every major call with rationale: repo structure, DB layer, search stack, locking, migration numbering
- [Concepts Learned](concepts-learned.md) — gaps filled: sparse/dense vectors, TEXT vs VARCHAR, migrations, RETURNING *, optimistic locking, monorepo vs polyrepo
- [GitOps Repo Decision](project-gitops-repo.md) — separate hotel-ai-gitops repo planned for Phase 7
- [Feedback: Explain before proceeding](feedback-explain-before-proceeding.md) — user pauses implementation to ask why; explain non-obvious decisions proactively
- [Phase 2 Progress](phase2-progress.md) — LLM gateway built (llm-gateway service, prompts, cost tracking); pending commit + smoke test
- [Phase 4 Progress](phase4-progress.md) — LangGraph ReAct agent with HITL, self-correction, and eval harness
