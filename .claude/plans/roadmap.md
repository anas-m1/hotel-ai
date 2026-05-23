# Hotel Booking System — Advanced AI Engineering Roadmap

## Context

The user is a senior software engineer (5 years: backend, AWS/cloud, DevOps, K8s, 1.5 yrs at travel startup) transitioning into AI engineering. The goal is to build a production-grade Hotel Booking System as a learning vehicle that simultaneously teaches:

1. **Advanced AI Engineering** — LLMs, RAG, Vector DBs, Agentic AI, Multi-Agent Systems, MCP
2. **Agentic Development with Claude Code** — Skills, Plugins, Workflows, Connectors, Subagents, Schedulers
3. **Production Software Engineering** — Clean architecture, DDD, observability, cloud-native deployment
4. **Interview readiness** — Principal/staff AI engineer level

This plan IS the project roadmap. Implementation will be executed phase by phase, each phase independently deliverable.

---

## Tech Stack Summary

| Layer | Technology | Why |
|---|---|---|
| Primary Language | Python 3.12 | Dominant AI/ML ecosystem; async-native |
| API Framework | FastAPI | Async, OpenAPI-native, production-proven |
| Agent Framework | LangGraph | Stateful graphs, cycle support, production-grade vs. LangChain linear chains |
| LLM Gateway | LiteLLM | Unified interface, cost tracking, fallback routing |
| Vector DB | Qdrant | Self-hostable, hybrid search (dense+sparse), production ops story |
| Embedding Model | text-embedding-3-large (OpenAI) | Best retrieval quality; swap-ready via LiteLLM |
| Relational DB | PostgreSQL 16 | pgvector fallback, JSONB, event sourcing support |
| Message Broker | Apache Kafka | Event-driven multi-agent coordination at scale |
| Cache | Redis | Session state, agent memory, rate limiting |
| Search | Elasticsearch | Sparse BM25 for hybrid RAG |
| Observability | OpenTelemetry + Langfuse | AI-native tracing + LLM evaluation dashboard |
| Infrastructure | AWS EKS + Terraform | Leverage existing K8s/AWS expertise |
| MCP | Custom MCP servers (Python SDK) | Native Claude Code integration |
| Claude Code | Skills, Plugins, Workflows, Subagents, Schedulers | Agentic development practice |

---

## Phase 1 — Foundation: Production-Grade Booking Domain

**What to build:**
- Domain model: Hotels, Rooms, Bookings, Guests, Pricing using DDD aggregates
- PostgreSQL schema with event sourcing (bookings table + booking_events table)
- FastAPI REST API with full OpenAPI spec
- CQRS split: write model (commands) vs. read model (queries/projections)
- Docker Compose local stack; Terraform skeleton for AWS

**AI concepts covered:** None yet — this is the substrate every AI feature will plug into.

**Claude Code agentic practice:**
- **Subagents:** Use Claude Code's Agent tool to spawn parallel subagents for: (1) domain model design, (2) DB schema, (3) API layer — learn how to decompose work across subagents
- **Skills (`/init`):** Run `/init` to generate CLAUDE.md capturing codebase conventions; create a project-specific skill for generating DDD aggregates

**System design focus:** Aggregate boundaries, optimistic locking, event sourcing vs. CRUD trade-offs, read/write model separation

**Interview alignment:** DDD/aggregate design, CQRS, event sourcing, API design, PostgreSQL schema evolution

---

## Phase 2 — LLM Integration: Intelligent Search & Content

**What to build:**
- LiteLLM gateway with cost tracking, rate limiting, and model fallback
- Structured output extraction: parse unstructured hotel descriptions → typed schemas
- Natural language hotel search (intent → SQL/filter translation)
- Prompt versioning system: store, version, and A/B test prompts
- Evaluation harness: automated prompt regression tests (RAGAS-style)

**AI concepts covered:**
- Prompting: system prompt engineering, few-shot examples, chain-of-thought for reasoning tasks
- Structured outputs: JSON mode, function calling for type-safe LLM responses
- Cost/latency optimization: token budgeting, caching identical prompts (Redis)
- Evaluation: precision/recall for search quality, exact-match vs. LLM-as-judge

**Claude Code agentic practice:**
- **Workflows:** Define a multi-step workflow: (1) generate prompt variant → (2) run evaluation suite → (3) report results; trigger via Claude Code workflow
- **Skills:** Build a `/eval-prompt` skill that runs the evaluation harness against a prompt change
- **Schedulers:** Schedule nightly prompt regression runs using Claude Code scheduler

**System design focus:** LLM gateway pattern, prompt as artifact (versioned, tested), evaluation-driven development

**Interview alignment:** LLM cost optimization, structured extraction, evaluation frameworks, prompt engineering depth

---

## Phase 3 — Vector Database & RAG Pipeline

**What to build:**
- Qdrant cluster (self-hosted on K8s) with hotel content collections
- Ingestion pipeline: hotel descriptions → chunking → embedding → Qdrant upsert
- Hybrid search: dense (semantic) + sparse (BM25 via Elasticsearch) with RRF fusion
- Re-ranking layer: cross-encoder re-ranker (Cohere or local)
- Multi-stage RAG: retrieve → filter → re-rank → generate with citations
- RAG evaluation dashboard (Langfuse): faithfulness, context relevance, answer relevance

**AI concepts covered:**
- Chunking strategies: fixed-size vs. semantic vs. hierarchical; chunk overlap trade-offs
- Embedding models: dimensionality, domain adaptation, MTEB benchmarks
- Index types: HNSW vs. IVF, ef_construction, m parameters
- Hybrid search: why neither dense nor sparse alone is sufficient for hotel search
- Re-ranking: bi-encoder vs. cross-encoder, latency vs. quality trade-off
- RAG evaluation: RAGAS metrics, LLM-as-judge, human eval correlation

**Claude Code agentic practice:**
- **Connectors (MCP):** Build an MCP server exposing Qdrant search as a tool — Claude Code can then use it directly during development to query the vector store
- **Subagents:** Spawn parallel subagents to (1) build ingestion pipeline, (2) build hybrid search, (3) write RAG evaluation suite
- **Plugins:** Develop a plugin that surfaces RAG evaluation metrics in Claude Code context

**System design focus:** Vector index operations (HNSW graph mechanics), multi-stage pipeline design, evaluation as a CI gate

**Interview alignment:** RAG architecture, hybrid search, embedding trade-offs, evaluation-driven AI systems

---

## Phase 4 — Agentic AI: Autonomous Booking Assistant

**What to build:**
- ReAct agent with tools: search_hotels, check_availability, get_pricing, book_room, send_confirmation
- Agent memory: episodic (Redis conversation history), semantic (Qdrant user preferences), procedural (booking workflow steps)
- Plan-and-Execute pattern: planner LLM generates a step list; executor LLM runs each step with tools
- Self-correction loop: agent detects failure, reflects, retries with adjusted plan
- Human-in-the-loop: agent pauses at high-stakes actions (payment), requests approval

**AI concepts covered:**
- ReAct reasoning trace: thought → action → observation loop
- Tool use and function calling: schema design, error handling, tool output parsing
- Agent memory architectures: episodic vs. semantic vs. procedural; when to use each
- Plan-and-Execute vs. ReAct: latency trade-off, failure modes
- Self-correction: detecting hallucination/failure in tool output, reflection prompting
- LangGraph: stateful graph construction, conditional edges, interrupt-and-resume nodes

**Claude Code agentic practice:**
- **Connectors (MCP):** Build MCP servers for each booking tool (search, availability, pricing, booking) — the agent itself consumes these MCP servers
- **Agent/Subagents:** Use Claude Code subagents to build individual tools in parallel; use the Agent tool to have Claude Code run the booking agent and test it interactively
- **Workflows:** Define a "test-the-agent" workflow that runs a set of user scenario scripts against the booking agent and reports pass/fail

**System design focus:** Agent state machine design, tool interface contracts, interrupt-and-resume for human-in-the-loop, idempotency for tool calls

**Interview alignment:** Agent architecture, ReAct vs. Plan-and-Execute, memory design, tool use patterns, failure modes and mitigations

---

## Phase 5 — Multi-Agent System: Orchestrated Hotel Operations

**What to build:**
- Supervisor agent: decomposes complex user requests into subtasks, routes to specialist agents
- Specialist agents: SearchAgent, PricingAgent, BookingAgent, CustomerServiceAgent, FraudDetectionAgent
- Kafka-based agent message bus: agents communicate via typed events, not direct calls
- Shared working memory: Redis-backed blackboard pattern for inter-agent state
- Agent monitoring dashboard: per-agent latency, tool call counts, failure rates (Langfuse + Grafana)
- Conflict resolution: when two agents reach contradictory conclusions

**AI concepts covered:**
- Supervisor/worker pattern vs. peer-to-peer collaboration
- Message passing vs. shared memory: consistency trade-offs
- Blackboard pattern: coordination without tight coupling
- Agent failure isolation: one agent failing must not cascade
- Emergent behavior: debugging multi-agent systems that fail non-deterministically
- Evaluation at the system level: end-to-end scenario testing across all agents

**Claude Code agentic practice:**
- **Subagents:** Each specialist agent is developed by a dedicated Claude Code subagent working in parallel — mirrors the multi-agent system being built
- **Schedulers:** Schedule the FraudDetectionAgent to run daily batch analysis using Claude Code scheduler
- **Workflows:** "Integration test" workflow: spin up all agents, run 20 end-to-end booking scenarios, report failures to Langfuse
- **Skills:** Build a `/agent-status` skill that queries the monitoring dashboard and surfaces agent health inline

**System design focus:** Event-driven architecture, Kafka topic design, agent isolation, distributed debugging, CAP theorem applied to agent coordination

**Interview alignment:** Multi-agent orchestration, event-driven design, distributed debugging, system-level evaluation

---

## Phase 6 — MCP: Building a Hotel Data Ecosystem

**What to build:**
- MCP server: `hotel-inventory` — exposes hotel CRUD, room availability, media assets
- MCP server: `booking-ops` — exposes reservation management, cancellations, modifications
- MCP server: `pricing-engine` — exposes dynamic pricing, competitor rate scraping, yield management
- MCP server: `analytics` — exposes booking trends, occupancy forecasts, revenue reports
- MCP server: `external-integrations` — wraps third-party APIs (Stripe, SendGrid, Google Maps)
- All servers consumed by agents AND directly by Claude Code for development tooling

**AI concepts covered:**
- MCP protocol: transport (stdio/HTTP), tool definitions, resource URIs, prompt templates
- Tool schema design: how to write tool descriptions that models use effectively
- Context injection via MCP resources vs. tools vs. prompts
- Security: MCP server authentication, input sanitization, preventing tool misuse

**Claude Code agentic practice:**
- **Connectors (MCP):** All five MCP servers are registered as Claude Code connectors — Claude Code itself uses them during development (query pricing, check availability, pull analytics inline)
- **Plugins:** Package the MCP server suite as a Claude Code plugin installable via plugin registry
- **Skills:** Build `/query-hotel-data` and `/run-pricing-report` skills that invoke MCP servers directly from Claude Code prompt

**System design focus:** API gateway vs. MCP, protocol design, server composition, tool taxonomy

**Interview alignment:** API design, protocol design, security for AI tools, tool ecosystem architecture

---

## Phase 7 — Production AI Operations (MLOps + AIOps)

**What to build:**
- LLM observability pipeline: every LLM call traced end-to-end (OpenTelemetry → Langfuse)
- Drift detection: monitor embedding distribution shift in hotel content over time
- A/B testing framework: route % of traffic to new prompt/model variants, measure business metrics
- Cost attribution: per-feature, per-agent LLM cost breakdown in real time
- Prompt injection defense: adversarial input detection, output sanitization, guardrails
- Automated evaluation CI/CD: every PR runs RAG eval + agent scenario tests; blocks merge on regression
- Kubernetes HPA for inference workloads: scale Qdrant and LiteLLM pods on queue depth

**AI concepts covered:**
- AI observability: what to trace (tokens, latency, cost, tool calls, retrieval quality)
- Distribution shift in production: embedding drift, query pattern changes
- Guardrails: NeMo Guardrails or custom classifiers for prompt injection, PII, off-topic
- A/B testing for AI: why standard statistical tests are harder with LLM outputs
- MLOps for LLM systems: no model training here, but prompt/config management as MLOps

**Claude Code agentic practice:**
- **Schedulers:** Nightly drift detection report; weekly cost attribution report — both scheduled via Claude Code scheduler and push results to Slack/email
- **Workflows:** "Deploy-and-eval" workflow: deploy new prompt → run evaluation suite → if passing metrics, promote; else rollback
- **Subagents:** Security subagent that runs adversarial prompt tests against every new agent tool registered
- **Skills:** `/cost-report` skill and `/eval-status` skill for on-demand observability from Claude Code

**System design focus:** Observability architecture, A/B testing infrastructure for non-deterministic systems, defense-in-depth for AI security

**Interview alignment:** AI observability, production LLM operations, security, A/B testing, cost optimization

---

## Phase 8 — Advanced Retrieval & Knowledge Graphs

**What to build:**
- Knowledge graph: hotels, locations, amenities, reviews as a graph (Neo4j or Amazon Neptune)
- GraphRAG: retrieve subgraphs relevant to query; combine with vector retrieval
- Agentic RAG: agent decides retrieval strategy (vector vs. graph vs. SQL) per query type
- Multi-hop reasoning: answer questions requiring traversal across multiple graph nodes
- Self-RAG: model generates retrieval queries, evaluates retrieved context, decides if sufficient

**AI concepts covered:**
- Knowledge graphs vs. vector stores: when to use each, how to combine
- GraphRAG: community detection, entity linking, graph traversal as retrieval
- Agentic RAG: retrieval as a tool the agent calls iteratively vs. one-shot pipeline
- Self-RAG: ISREL (is retrieved context relevant?), ISSUP (is answer supported?), ISUSE (is answer useful?)
- Multi-hop retrieval: decompose complex questions into retrieval sub-steps

**Claude Code agentic practice:**
- **Subagents:** One subagent builds the knowledge graph ingestion pipeline; another builds the GraphRAG retrieval layer; third builds the Self-RAG evaluation loop — all run in parallel
- **Connectors (MCP):** Add `knowledge-graph` MCP server; Claude Code can traverse the hotel graph during development

**System design focus:** Graph data modeling for hotel domain, query routing architecture, RAG pipeline composition

**Interview alignment:** GraphRAG, knowledge graphs, advanced retrieval strategies, Self-RAG patterns

---

## Phase 9 — Capstone: Autonomous Hotel Management AI

**What to build:**
- Long-horizon autonomous agent: given a goal ("maximize next month's revenue"), plans and executes multi-day tasks autonomously
- Scheduled agent runs: nightly yield optimization, weekly competitive analysis, monthly demand forecasting
- Human oversight dashboard: review agent decisions, approve/reject action plans, audit logs
- Agent-to-agent delegation: top-level agent spawns specialist agents via MCP, collects results
- Full end-to-end demo: hotel manager persona asks complex questions, system responds with multi-agent coordination, retrieval, reasoning, and autonomous action

**AI concepts covered:**
- Long-horizon planning: how agents decompose goals spanning multiple days/steps
- Autonomous scheduling: agents that self-schedule follow-up tasks
- Oversight and control: audit trails, approval gates, rollback mechanisms
- Emergent capability: what the system can do as a whole that no single agent can do alone

**Claude Code agentic practice:**
- **Full stack:** Every Claude Code feature used: Skills for common dev tasks, Plugins for the MCP server suite, Workflows for CI/CD and evaluation, Connectors for all MCP servers, Subagents for parallel development, Schedulers for autonomous agent runs
- **Meta-skill:** Document the agentic development workflow itself — this becomes a reusable template for future AI projects

**System design focus:** Full architecture walkthrough — can explain every component, every trade-off, every failure mode at principal engineer level

**Interview alignment:** Full system design interview, AI engineering depth, autonomous systems, oversight and safety

---

## Claude Code Agentic Workflow Map

| Feature | Phases Used | What's Practiced |
|---|---|---|
| **Subagents** | 1, 3, 4, 5, 8, 9 | Parallel workstream decomposition, agent orchestration |
| **Skills** | 1, 2, 5, 7, 9 | Custom slash commands for project-specific tasks |
| **Workflows** | 2, 4, 5, 7, 9 | Multi-step automated dev pipelines |
| **Connectors (MCP)** | 3, 4, 6, 8, 9 | Registering and consuming MCP servers from Claude Code |
| **Plugins** | 3, 6, 9 | Packaging and distributing Claude Code extensions |
| **Schedulers** | 2, 5, 7, 9 | Recurring automated Claude Code tasks |

---

## Interview Prep Matrix

| Phase | System Design | AI/ML Depth | Coding | Behavioral |
|---|---|---|---|---|
| 1 | DDD, CQRS, event sourcing | — | Aggregate design, schema migration | Building from scratch, domain modeling |
| 2 | LLM gateway pattern, prompt lifecycle | Prompting, structured output, eval | Evaluation harness, A/B test infra | Data-driven decision making |
| 3 | RAG pipeline, hybrid search | Embeddings, chunking, re-ranking | Ingestion pipeline, RAGAS metrics | Ambiguous problem scoping |
| 4 | Agent state machine, human-in-loop | ReAct, Plan-Execute, memory | LangGraph graph construction | Autonomy vs. control trade-offs |
| 5 | Multi-agent, Kafka, blackboard | Agent coordination, conflict resolution | Event-driven agent bus | Cross-team collaboration analogy |
| 6 | MCP protocol, API taxonomy | Tool schema design, context injection | MCP server implementation | API product ownership |
| 7 | Observability architecture, A/B infra | Drift detection, guardrails, MLOps | CI/CD for AI, cost attribution | Incident response, production ownership |
| 8 | GraphRAG, query routing | Knowledge graphs, Self-RAG, multi-hop | Graph traversal, agentic retrieval | Novel problem solving |
| 9 | Full system walkthrough | Long-horizon planning, oversight | Full integration | Leadership, technical vision |

---

## Verification Plan

Each phase will be verified by:
1. Running the relevant services locally via Docker Compose
2. Executing the phase's evaluation suite (automated tests + AI eval metrics)
3. Demonstrating the Claude Code agentic feature for that phase end-to-end
4. Running a mock interview question against the completed phase's design

The project repository will be a single monorepo with per-phase directories and a shared `core/` library.
