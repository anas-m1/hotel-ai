# ADR-020: MCP Servers Use SSE Transport, Not stdio

**Date:** Phase 6  
**Status:** Accepted

## Context

MCP servers can communicate with clients over two transports:
- **stdio**: the MCP client spawns the server as a child process and communicates
  over stdin/stdout. Used natively by Claude Desktop for local tools.
- **SSE (Server-Sent Events)**: the server runs as an HTTP service; the client
  connects to `GET /sse` for a persistent event stream and sends tool calls to
  `POST /messages`.

## Decision

Run both MCP servers (`mcp/hotel-inventory`, `mcp/booking-ops`) using the SSE
transport on dedicated HTTP ports (8100, 8101). Claude Desktop is configured to
connect via `url: http://localhost:{port}/sse`.

## Why

- **Containerised**: our MCP servers run in Docker alongside the Go services.
  stdio requires the client to spawn the process — impossible when the process
  lives in a container. SSE works over any network connection.
- **Testable without a desktop client**: SSE endpoints are plain HTTP. `curl`
  and `pytest` can call `POST /messages` directly, enabling integration tests
  without Claude Desktop in the loop.
- **Independently deployable**: SSE servers are stateless HTTP services. They
  can be scaled, health-checked, and load-balanced like any other service.
  A stdio process is tied to the client's lifetime.
- **Multi-client**: a single SSE server can serve multiple simultaneous MCP
  clients. stdio is 1:1 (one process per client session).

## Consequences

- Claude Desktop must be configured with `"url"` instead of `"command"` in its
  MCP server config. The example config is in `phases/06_mcp/claude_desktop_config.json.example`.
- SSE adds a network hop vs stdio. Negligible: MCP calls are interactive and
  tool execution latency (HTTP to Go service) dominates.
- The MCP servers must be running before Claude Desktop connects. Stdio would
  auto-start the process; SSE requires the Docker stack to be up.
