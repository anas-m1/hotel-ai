# Phase 4 — Agentic AI: Autonomous Booking Assistant

## What was built

A LangGraph ReAct agent for hotel search, availability checks, and room reservations.

### Architecture

```
User → FastAPI (/v1/chat) → LangGraph StateGraph → LLM (via LiteLLM gateway)
                                                         ↓
                                              Tool calls → Go service HTTP APIs
                                                         ↓
                                              hotel-inventory (port 8080)
                                              booking-ops (port 8081)
```

### Agent Flow

```
planner → executor → tools → (errors? → reflect → executor)
                           → (book_room? → human_approval → tools/advance)
                           → (done? → advance_check → executor / end)
```

### Key Components

| Module | Purpose |
|--------|---------|
| `src/agent/graph.py` | LangGraph `StateGraph` with 6 nodes: planner, executor, tools, reflect, human_approval, advance_check |
| `src/agent/nodes.py` | Node functions: `executor` (LLM with step context), `execute_tools`, `advance_check`, routing edges |
| `src/agent/planner.py` | Plan-and-Execute planner: generates step-by-step plan from user request |
| `src/agent/tools.py` | 8 async tools wrapping Go service HTTP APIs |
| `src/agent/state.py` | `AgentState` with messages, plan, current_step, tool_errors, retry_count |
| `src/agent/prompts.py` | Executor prompt, planner prompt, reflection prompt |
| `src/agent/hitl.py` | Human-in-the-loop via `interrupt()` for booking approval |
| `src/agent/reflection.py` | Self-correction node that reflects on tool errors |
| `src/router/chat.py` | `POST /v1/chat` and `POST /v1/chat/resume` endpoints |
| `src/memory/store.py` | In-memory conversation store (Redis replacement planned) |

### Plan-and-Execute Pattern

Unlike the simple ReAct loop (which decides tool calls on-the-fly), this agent uses a Plan-and-Execute architecture:

1. **Planner** (`create_plan`): Analyzes the user's request and generates a structured step-by-step plan via `with_structured_output(Plan)`.
2. **Executor** (`executor`): Executes one step at a time, deciding which tools to call to satisfy the current step.
3. **Advance Check** (`advance_check`): After each step is completed, increments `current_step` and routes to the next step or END.

### Tools

1. `search_hotels` — `GET /v1/hotels?city=&q=&rating=`
2. `get_hotel` — `GET /v1/hotels/{code}`
3. `list_rooms` — `GET /v1/hotels/{code}/rooms?type=`
4. `check_availability` — `GET /v1/availability?room_id=&check_in=&check_out=`
5. `get_guest` — Get guest by email
6. `create_guest` — Create/update guest profile
7. `book_room` — `POST /v1/bookings`
8. `get_booking` — `GET /v1/bookings/{id}`

### Human-in-the-Loop

When the agent decides to call `book_room`, execution pauses at the `human_approval` node and returns an interrupt to the user. The user reviews the booking details and calls `POST /v1/chat/resume` with `{"approved": true/false}` to continue or cancel.

### Self-Correction

If tool calls fail, the agent routes to the `reflect` node which analyzes the errors and generates a corrected plan (up to 2 retries).

## AI Concepts Covered

- ReAct reasoning trace: thought → action → observation loop
- Tool use and function calling via LangChain `@tool` decorator
- Human-in-the-loop with LangGraph `interrupt()` / `Command(resume=...)`
- Self-correction via reflection on tool errors
- LangGraph: stateful graph construction, conditional edges, interrupt-and-resume

## Running

```bash
cd ai/booking-assistant
uv sync
cp .env.example .env  # configure URLs
uv run python -m src.main
```

## Eval Harness

See `eval/test_booking_agent.py` for scenario-based tests.
