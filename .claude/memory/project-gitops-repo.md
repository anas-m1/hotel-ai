---
name: project-gitops-repo
description: Decision to use a separate GitOps repo for K8s/ArgoCD deployment configs, separate from the source monorepo
metadata:
  type: project
---

Separate GitOps repo (`hotel-ai-gitops`) will be created when EKS deployments are wired up in Phase 7.

**Why:** Clean separation between source code (devs) and deployment manifests (ops). ArgoCD watches the GitOps repo; CI in `hotel-ai` builds images and bumps image tags there.

**How to apply:** Do not add Helm charts or ArgoCD configs to the `hotel-ai` monorepo. The `infra/k8s/` directory is a placeholder only — actual manifests live in `hotel-ai-gitops` from Phase 7 onwards. Remind user of this split when touching deployment-related infra work.
