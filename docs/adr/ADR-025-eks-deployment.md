# ADR-025: EKS as the production compute platform

**Status:** Accepted  
**Date:** 2026-06-17  
**Phase:** 9 — Capstone

## Context

Phase 9 needs a production-grade deployment target for all seven services (two Go microservices, five Python AI services). The core tension is between operational simplicity and the operational requirements of the AI workloads:

- AI services need dedicated nodes — they carry heavier memory footprints than the Go services and benefit from isolation to avoid starving each other during spikes
- The team already operates Kubernetes locally via docker-compose with the same service topology; a Kubernetes target keeps local and prod as close as possible
- Alternative was ECS (Fargate) — lower operational overhead but coarser scheduling control and a less portable skill set

## Decision

Deploy on **EKS (Elastic Kubernetes Service) 1.30** managed via the `terraform-aws-modules/eks` Terraform module.

Two node groups:

| Node group | Instance | Workloads | Scheduling |
|---|---|---|---|
| `general` | t3.medium × 2–4 | hotel-inventory, booking-ops, llm-gateway | default |
| `ai` | t3.large × 2–4 | booking-assistant, multi-agent, knowledge-graph, rag-pipeline | taint `workload=ai:NoSchedule` |

AI service deployments carry a matching toleration so they can land on `ai` nodes; Go services have no toleration so they cannot.

The **AWS Load Balancer Controller** (installed via Helm) handles ALB provisioning from `Ingress` objects. Path routing: `/v1/hotels*` → hotel-inventory, `/v1/bookings*` → booking-ops, `/v1/chat*` → booking-assistant, etc.

IRSA (IAM Roles for Service Accounts) is enabled so pods can assume AWS roles without instance-level IAM permissions.

## Consequences

**Good:**
- Node isolation prevents AI memory spikes from affecting Go service latency
- HPA on booking-assistant (2–8 replicas, 80% memory target) handles burst chat traffic without touching Go service nodes
- Local and production use the same Kubernetes primitives — `kubectl apply` works against both
- Terraform modules abstract EKS version upgrades to a single variable change

**Bad:**
- EKS control plane costs ~$72/month regardless of cluster size — ECS Fargate has no control-plane charge
- Initial cluster bootstrap is more complex than ECS: OIDC provider, IRSA, LBC installation, kubeconfig wiring
- Node group taint/toleration must be kept in sync across deployments — a missing toleration silently lands a service on the wrong node group

## Alternatives considered

**ECS Fargate** — eliminated because task placement constraints are coarser than Kubernetes taints, and the team has stronger Kubernetes familiarity from local development.

**App Runner** — eliminated; no support for WebSocket / SSE connections needed by MCP and booking-assistant.

**Single node group** — eliminated; without isolation an AI service memory spike can OOM-kill a Go service pod on the same node.
