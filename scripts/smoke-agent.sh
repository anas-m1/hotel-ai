#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 evals/agent/evaluate_agent.py \
  --base-url "${BASE_URL:-http://localhost:8092}" \
  --output "${EVAL_OUTPUT:-/tmp/hotel-agent-eval.json}"
