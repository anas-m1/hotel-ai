# ADR-024: Self-RAG for Retrieval Quality Scoring

**Date:** Phase 8  
**Status:** Accepted

## Context

GraphRAG returns a fused ranked list, but some candidates may be low-quality
matches: a hotel in the right city but missing the requested amenities, or a
result that scored high on vector similarity due to unrelated text in its
description. Downstream LLM responses that include irrelevant context produce
worse answers and more hallucinations.

## Decision

Add a **Self-RAG filtering pass** after GraphRAG fusion. For each candidate,
call the llm-gateway (claude-haiku) with the query and hotel description to ask:
"Is this hotel RELEVANT or NOT_RELEVANT to the query?" Drop candidates scored
NOT_RELEVANT before returning results.

The predicate implemented is **ISREL** from the Self-RAG paper
(Asai et al., 2023) — relevance of the retrieved document to the query.

Self-RAG is **opt-out** via `SELF_RAG_ENABLED=false`. When disabled,
the service returns GraphRAG results directly (useful for latency-sensitive
or cost-sensitive deployments).

## Why

- **Relevance guarantees**: the LLM judge catches mismatches that RRF scoring
  misses — e.g., a 5-star hotel in Dubai that matches "luxury" semantically but
  lacks the specific "beachfront" constraint.
- **Reduced hallucination**: downstream agents and MCP tools receive only
  relevant hotels, reducing the chance of the agent recommending an unsuitable
  property.
- **Fail open**: if the scoring call fails (timeout, gateway error), the
  candidate is kept — retrieval degrades gracefully to GraphRAG-only.

## Consequences

- Each search request makes N additional LLM calls (one per candidate, run in
  parallel). With `GRAPH_CANDIDATES=30` and `VECTOR_CANDIDATES=30`, up to 60
  haiku calls per search. Cost: ~$0.001 per search at haiku pricing. Acceptable
  for a booking assistant where search is user-initiated.
- Added latency: parallel haiku calls take ~500–1500ms. For Phase 8, total
  search latency target is <3s.
- Only ISREL is implemented. ISSUP (does the document support the answer?) is
  deferred to Phase 9 when we add answer generation to the search endpoint.
