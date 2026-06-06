# ADR-002: Separate GitOps Repo for Deployment Manifests

**Date:** Phase 0  
**Status:** Accepted (repo created at Phase 7)

## Context
Kubernetes deployment manifests (Helm charts, ArgoCD configs) need a home. Options: same repo as source code, or a dedicated repo.

## Decision
`hotel-ai-gitops` is a **separate repository**, created at Phase 7. `infra/k8s/` in the main repo is a placeholder only.

## Why
- Clean separation: source code is a dev concern; deployment manifests are an ops concern
- ArgoCD watches the GitOps repo; CI in `hotel-ai` builds images and bumps image tags there
- Separate audit trail and access control for production deployments

## Consequences
- Do not add Helm charts or ArgoCD Application manifests to `hotel-ai`
- Phase 1–6 use Docker Compose only; K8s manifests are Phase 7 work
