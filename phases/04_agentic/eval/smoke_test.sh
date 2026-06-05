#!/usr/bin/env bash
set -euo pipefail

# ─── Smoke test for the booking assistant ──────────────────────────────────
# Requires: docker compose services running (postgres, hotel-inventory,
#           booking-ops, llm-gateway, booking-assistant)
#
# Usage:
#   cd hotel-ai
#   docker compose -f infra/docker/docker-compose.yml up -d
#   bash phases/04_agentic/eval/smoke_test.sh

BASE_URL="${BASE_URL:-http://localhost:8092}"

echo "=== Booking Assistant Smoke Test ==="
echo "Base URL: $BASE_URL"
echo ""

# 1. Health check
echo "--- Health check ---"
HEALTH=$(curl -sf "$BASE_URL/healthz" || echo '{"status":"FAIL"}')
echo "Health: $HEALTH"
if [[ "$HEALTH" != *"ok"* ]]; then
  echo "FAIL: health check"
  exit 1
fi
echo ""

# 2. Simple chat (no booking)
echo "--- Simple chat ---"
RESP=$(curl -sf -X POST "$BASE_URL/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what hotels do you have in Paris?"}' || echo '{"reply":"FAIL"}')
echo "Response: $RESP"
if [[ "$RESP" == *"FAIL"* ]]; then
  echo "FAIL: chat request"
  exit 1
fi
echo ""

# 3. Chat with session (multi-turn)
echo "--- Multi-turn chat ---"
RESP=$(curl -sf -X POST "$BASE_URL/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me available rooms at hotel NYC001", "session_id": "test-session-1"}' || echo '{"reply":"FAIL"}')
echo "Response: $RESP"
if [[ "$RESP" == *"FAIL"* ]]; then
  echo "FAIL: multi-turn chat"
  exit 1
fi
echo ""

echo "=== All smoke tests passed ==="
