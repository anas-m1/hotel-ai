# Phase 4 Progress — Agentic AI: Autonomous Booking Assistant

## Status: In Progress

### What's built
- [x] LangGraph ReAct agent with 8 tools (search_hotels, get_hotel, list_rooms, check_availability, get_guest, create_guest, book_room, get_booking)
- [x] Human-in-the-loop via LangGraph `interrupt()` / `Command(resume=...)` for booking approval
- [x] Self-correction/reflection node for tool error recovery (up to 2 retries)
- [x] State graph with 4 nodes: agent, tools, reflect, human_approval
- [x] Conditional edges: agent→tools, agent→human_approval, agent→end; tools→reflect, tools→agent; human_approval→tools, human_approval→agent
- [x] FastAPI entry point: `POST /v1/chat` and `POST /v1/chat/resume`
- [x] In-memory conversation store (Redis replacement planned)
- [x] Dockerfile for container build
- [x] Phase 4 documentation (`phases/04_agentic/README.md`)
- [x] Eval harness (`phases/04_agentic/eval/test_booking_agent.py`)

### What's planned but not built
- [x] Plan-and-Execute pattern (planner LLM → executor LLM with step-by-step plan)
- [ ] Redis-backed episodic memory (conversation history)
- [ ] Semantic memory (Qdrant user preferences)
- [ ] Procedural memory (booking workflow state)
- [ ] MCP servers for each booking tool (could be built in Phase 6)
- [ ] Interactive eval scenarios (end-to-end tests with running services)

### Session: Testing & packaging fixes (June 5, 2026)

**What was done:**
- Created `.venv` virtual environment for dependency isolation
- Installed dev deps: pytest, mypy, ruff, pytest-asyncio, hatchling, editables
- Fixed `pyproject.toml`: `[dependency-groups]` → `[project.optional-dependencies]` so `pip install -e ".[dev]"` works (PEP 735 vs PEP 621)
- Added `dev-mode-dirs = ["src"]` to hatch config to fix editable install with src layout
- Changed `from ..config import settings` → `from config import settings` in 4 agent files (nodes.py, tools.py, planner.py, reflection.py)
- Added `from typing import Any` to reflection.py (was missing)
- Fixed test_booking_agent.py: removed sys.path hack, added pytest-asyncio marks, made advance_check tests async
- All 12 eval tests pass

**Decisions this session:**

1. **Virtual environment is required** — Without it, hatchling's editable install fails (editables library missing, .pth file points to wrong directory). Global Python should not be used for project development.

2. **Absolute over relative imports** — `from config import settings` instead of `from ..config import settings`. The `..` relative import fails when `agent` is a top-level package (as it is in venv's editable install). Since `dev-mode-dirs = ["src"]` adds `src/` to `sys.path`, `config` is directly importable.

3. **dev-mode-dirs = ["src"]** — Required in `[tool.hatch.build.targets.wheel]` for editable installs with a `src` layout. Without it, the `.pth` file adds the project root to `sys.path` but packages live under `src/`, making them invisible. With `dev-mode-dirs`, `src/` is added to `sys.path` and `import agent` resolves correctly.

4. **pytest-asyncio in STRICT mode** — async test functions need `@pytest.mark.asyncio` decorator when `asyncio_mode` is STRICT (default with pytest-asyncio >= 1.0).

### Design decisions

**State as Pydantic BaseModel**: Using Pydantic v2 for `AgentState` ensures type validation and clean serialization. LangGraph supports Pydantic models as state schemas via `StateGraph(AgentState)`.

**Single interrupt point**: Rather than interrupting on every tool call, we only interrupt on `book_room`. This keeps the UX simple — the user only approves at the final booking step, not during search/availability checks.

**MemorySaver checkpointer**: In-memory checkpointing is sufficient for development. Will migrate to PostgresSaver in Phase 7 (AIOps) for production persistence.

**Added missing Go endpoint**: `GET /v1/guests/by-email/{email}` was missing from booking-ops despite `GetByEmail` existing in the repository. Added handler + route.

**Semantic search tool**: Added `semantic_search_hotels` tool using the RAG pipeline's `POST /v1/search/hotels` endpoint for natural language hotel discovery.

**Self-correction via reflection**: A separate LLM call with error context produces a corrected plan. Simpler than implementing a full Plan-Execute loop but gives the agent a chance to recover from transient failures.
