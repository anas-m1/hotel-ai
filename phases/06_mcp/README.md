# Phase 6 — MCP Servers

## What this phase builds

Two MCP (Model Context Protocol) servers that expose hotel booking capabilities
to Claude Desktop and any other MCP-compatible client. Each server is a **thin
HTTP facade** over an existing Go service — no business logic, no DB access.

## Servers

| Server | Port | Facade over | Tools |
|---|---|---|---|
| `mcp/hotel-inventory` | 8100 | hotel-inventory:8080 | list_hotels, get_hotel, list_rooms, check_room_availability |
| `mcp/booking-ops` | 8101 | booking-ops:8081 | get_guest_by_email, create_guest, create_booking, get_booking, cancel_booking, list_guest_bookings |

## Architecture

```
Claude Desktop (MCP client)
        │
        │  MCP protocol over SSE
        ▼
┌──────────────────────┐    ┌──────────────────────┐
│ mcp/hotel-inventory  │    │  mcp/booking-ops     │
│  FastMCP (SSE :8100) │    │  FastMCP (SSE :8101) │
└──────────┬───────────┘    └──────────┬───────────┘
           │ HTTP                      │ HTTP
           ▼                           ▼
   hotel-inventory:8080         booking-ops:8081
     (Go service)                 (Go service)
```

The MCP servers add only:
1. Protocol translation: MCP tool call → HTTP request to Go service
2. Schema exposure: tool definitions with typed parameters
3. Response formatting: raw JSON → readable markdown strings

## Connecting Claude Desktop

Copy `claude_desktop_config.json.example` to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "hotel-inventory": {
      "url": "http://localhost:8100/sse"
    },
    "booking-ops": {
      "url": "http://localhost:8101/sse"
    }
  }
}
```

Then restart Claude Desktop. You'll see the hotel tools appear in the tool picker.

## Running locally

```bash
# Copy env files
cp infra/docker/mcp-hotel-inventory.env.example infra/docker/mcp-hotel-inventory.env
cp infra/docker/mcp-booking-ops.env.example infra/docker/mcp-booking-ops.env

# Start everything
docker compose -f infra/docker/docker-compose.yml up -d

# Verify MCP servers are up
curl http://localhost:8100/sse      # should return SSE stream headers
curl http://localhost:8101/sse

# Test a tool directly (MCP over HTTP)
curl -X POST http://localhost:8100/messages \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"list_hotels","arguments":{"city_code":"DXB"}}}'
```

## What's next (Phase 7)

AI Ops — observability, Langfuse tracing, OpenTelemetry, cost dashboards,
and Redis-backed cross-session agent memory.
