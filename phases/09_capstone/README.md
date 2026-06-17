# Phase 9 — Capstone: Production Infrastructure

Brings all seven services to production on AWS using Terraform-managed EKS, a GitHub Actions CI/CD pipeline, and end-to-end integration tests.

## What's built

| Layer | Technology | Files |
|---|---|---|
| IaC | Terraform (S3 backend + DynamoDB lock) | `infra/terraform/` |
| Compute | EKS 1.30, two node groups | `infra/terraform/eks.tf` |
| Data | RDS Postgres 16, ElastiCache Redis 7, MSK Kafka 3.6 | `infra/terraform/*.tf` |
| Registry | ECR (one repo per service, lifecycle: keep 10) | `infra/terraform/ecr.tf` |
| Networking | VPC, 3 AZs, private subnets, single NAT (non-prod) | `infra/terraform/vpc.tf` |
| K8s manifests | Namespace, Deployments, Services, HPAs, ALB Ingress | `infra/k8s/` |
| CI | Ruff lint, go vet/test, docker build | `.github/workflows/ci.yml` |
| CD | OIDC auth → ECR push → kubectl rollout | `.github/workflows/cd.yml` |
| E2E tests | pytest full golden-path across all 7 services | `phases/09_capstone/e2e/` |

## Architecture

```
GitHub Actions (CI/CD)
        │ OIDC (no long-lived keys)
        ▼
    AWS ECR  ──────────────────────────────────────────────────┐
                                                               │
    EKS Cluster (hotel-ai-prod)                                │
    ┌──────────────────────────────────────────────────────┐   │
    │  node group: general (t3.medium)                     │   │
    │    hotel-inventory  booking-ops  llm-gateway         │   │
    │                                                      │   │
    │  node group: ai (t3.large, taint workload=ai)        │   │  pull
    │    booking-assistant  multi-agent  knowledge-graph   │◄──┘
    │    rag-pipeline                                      │
    │                                                      │
    │  ALB Ingress Controller                              │
    └──────────────────────────────────────────────────────┘
            │            │             │
         RDS Postgres  Redis 7     MSK Kafka 3.6
         (multi-AZ     (2 nodes)   (3 brokers)
          in prod)
```

### Node group strategy

AI services (booking-assistant, multi-agent, knowledge-graph, rag-pipeline) carry larger memory footprints and benefit from node isolation. They run on a dedicated node group with a `workload=ai:NoSchedule` taint and matching toleration in every AI service deployment. Go microservices run on the general node group.

## Terraform layout

```
infra/terraform/
├── providers.tf        # AWS + kubernetes + helm; S3 backend
├── variables.tf        # environment, cluster config, sizing knobs
├── vpc.tf              # VPC module — 3 AZs, private + public subnets
├── eks.tf              # EKS module v20, IRSA, AWS LBC helm release
├── rds.tf              # PostgreSQL 16, encrypted, multi_az=true in prod
├── elasticache.tf      # Redis 7, 2 cache nodes
├── msk.tf              # Kafka 3.6, kafka.t3.small, auto topic creation
├── ecr.tf              # 9 ECR repos, lifecycle policy (keep 10 images)
└── outputs.tf          # endpoints + `configure_kubectl` helper command
```

Bootstrap order:
```bash
cd infra/terraform
terraform init          # pulls providers, connects S3 backend
terraform plan -var="environment=prod"
terraform apply -var="environment=prod"
# then configure kubectl:
$(terraform output -raw configure_kubectl)
# then seed K8s secrets and apply base manifests:
kubectl apply -f ../k8s/base/
```

## Kubernetes manifests

```
infra/k8s/
├── base/
│   ├── namespace.yaml   # hotel-ai namespace
│   └── ingress.yaml     # ALB ingress — path routing to all services
└── services/
    ├── hotel-inventory/deployment.yaml
    ├── booking-ops/deployment.yaml
    ├── llm-gateway/deployment.yaml
    ├── booking-assistant/deployment.yaml   # HPA: 2–8 replicas on memory
    └── multi-agent/deployment.yaml
```

Each deployment uses `secretRef` (`<service>-secrets`) for environment variables. Create secrets before first deploy:
```bash
kubectl create secret generic hotel-inventory-secrets \
  --from-literal=POSTGRES_DSN="..." \
  -n hotel-ai
# repeat for each service
```

## CI/CD

### CI (`.github/workflows/ci.yml`) — runs on every PR

1. `go vet ./...` + `go test ./...` for Go services
2. `ruff check` + `ruff format --check` for every Python service
3. `docker build` (no push) for all services to catch broken Dockerfiles

### CD (`.github/workflows/cd.yml`) — runs on merge to `main`

1. OIDC → AWS role (`AWS_DEPLOY_ROLE_ARN` secret) — no stored credentials
2. Build + push all images to ECR tagged with `${{ github.sha }}` and `:latest`
3. `kubectl apply` each service deployment (sed-replaces registry/tag/env placeholders)
4. `kubectl rollout status` — blocks until healthy (300 s timeout per service)
5. Apply ingress

Required GitHub secrets: `AWS_ACCOUNT_ID`, `AWS_DEPLOY_ROLE_ARN`.

## E2E tests

```
phases/09_capstone/e2e/
└── test_booking_flow.py
```

Run with all services up locally via docker compose:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
cd phases/09_capstone/e2e
pytest test_booking_flow.py -v -s
```

Test sequence:
1. Health-check all 7 services (`/healthz`)
2. List hotels, get hotel, list rooms
3. Semantic search via RAG pipeline
4. GraphRAG search via knowledge-graph
5. Check room availability
6. Create a guest
7. Create a booking via booking-ops
8. Retrieve and verify the booking
9. Verify booking-assistant chat returns a reply
10. Verify multi-agent routes to `search_agent`
11. Cancel the booking and confirm status = `cancelled`

## Key decisions

- ADR-025: EKS over ECS — Kubernetes for portability and ecosystem tooling
- ADR-026: OIDC for CI/CD — eliminates long-lived AWS credentials in GitHub secrets

## What's not included

- Observability stack (Prometheus / Grafana) — would extend from Phase 7 Langfuse setup
- Staging environment — add `environment=staging` Terraform workspace and a second CD job
- Canary / blue-green deploys — Argo Rollouts would slot in as a natural next step
- Automated E2E in CI — requires a live cluster; left as a manual gate
