# ADR-016: phase/NN-name Git Branching Strategy

**Date:** Phase 0  
**Status:** Accepted

## Context
The project is built in 9 phases. Each phase introduces a significant new capability. Need a branching strategy that lets work progress phase by phase without polluting `main` with incomplete features.

## Decision
One long-lived branch per phase: `phase/01-foundation`, `phase/02-llm-integration`, etc. Work accumulates on the phase branch. When a phase is complete and verified, it is merged to `main`. No feature branches within a phase.

## Why
- Each phase is a self-contained milestone with a clear completion criteria. Treating each as a long-lived branch maps naturally to the learning structure.
- Keeps `main` always in a working, demo-able state.
- For a solo project, feature-branch overhead (PRs, code review gates) adds friction without benefit. The phase branch itself serves as the isolation boundary.

## Consequences
- Merging phases requires resolving any conflicts accumulated over the phase's lifetime. Mitigated by frequent commits within the phase branch.
- `go.work` and `docker-compose.yml` are modified by multiple phases — these files are likely merge conflict points. Resolve by taking the latest phase's version.
