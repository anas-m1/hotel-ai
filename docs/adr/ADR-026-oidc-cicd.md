# ADR-026: OIDC for GitHub Actions AWS authentication

**Status:** Accepted  
**Date:** 2026-06-17  
**Phase:** 9 — Capstone

## Context

The CD pipeline (`.github/workflows/cd.yml`) needs to push images to ECR and run `kubectl apply` against the EKS cluster. That requires AWS credentials. Two standard approaches exist:

1. **Long-lived IAM access keys** stored as GitHub secrets (`AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`)
2. **OIDC federation** — GitHub Actions exchanges a short-lived JWT for a temporary AWS role session via `sts:AssumeRoleWithWebIdentity`

Long-lived keys are the default pattern in most tutorials but carry a well-known supply-chain risk: if the secret is leaked (e.g., via a log statement, a compromised runner, or a repo fork), the key can be used indefinitely until manually rotated.

## Decision

Use **OIDC (OpenID Connect) federation** between GitHub Actions and AWS IAM.

How it works:
1. Terraform creates an IAM OIDC provider for `token.actions.githubusercontent.com` in `infra/terraform/eks.tf`
2. An IAM role (`AWS_DEPLOY_ROLE_ARN`) trusts that provider with a condition scoped to this repository and `ref:refs/heads/main`
3. The CD workflow requests `id-token: write` permission and uses `aws-actions/configure-aws-credentials@v4` with `role-to-assume`
4. GitHub mints a short-lived OIDC token; AWS validates it, checks the condition, and returns a 1-hour session

The only secret stored in GitHub is `AWS_DEPLOY_ROLE_ARN` (an ARN, not a credential) and `AWS_ACCOUNT_ID` (needed for ECR registry URL). No `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` are stored anywhere.

Workflow permission block:
```yaml
permissions:
  id-token: write   # required for OIDC token request
  contents: read
```

## Consequences

**Good:**
- No long-lived credentials to rotate, audit, or accidentally commit
- Credentials are scoped to a 1-hour window and automatically expire — a leaked token is useless after the session ends
- The trust policy condition (`repo:org/hotel-ai:ref:refs/heads/main`) ensures only merges to `main` can assume the deploy role — PRs from forks cannot
- Complies with AWS security best practice: prefer temporary credentials over permanent ones

**Bad:**
- Initial Terraform setup is more involved than `aws iam create-access-key` — requires the OIDC provider, trust policy, and the `token.actions.githubusercontent.com` thumbprint
- Debugging failures is less obvious than "wrong key" — common errors are trust policy condition mismatches (wrong repo name, wrong branch ref) which surface as `AccessDenied` without a clear message

## Trust policy condition

The role trust policy condition in Terraform:
```hcl
condition {
  test     = "StringLike"
  variable = "token.actions.githubusercontent.com:sub"
  values   = ["repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"]
}
```

`StringLike` (not `StringEquals`) allows extending to `ref:refs/heads/release/*` later without changing the condition operator.

## Alternatives considered

**Long-lived IAM access keys** — eliminated. No rotation schedule, single secret leakage = full ECR + EKS access until manually discovered and revoked.

**IAM user per environment** — same problem as above; just adds key-management overhead.

**AWS CodePipeline** — would remove the GitHub Actions dependency but add another service to manage and breaks the PR-centric workflow the team uses.
