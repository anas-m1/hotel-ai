# ADR-014: MCP Servers as Thin HTTP Facades

**Date:** Phase 6 (planned)  
**Status:** Accepted

## Context
Phase 6 introduces MCP (Model Context Protocol) servers so that Claude Desktop and other MCP clients can interact with hotel booking capabilities. MCP servers need to expose tools. They could contain business logic or delegate to existing services.

## Decision
Each MCP server is a thin facade over an existing Go service HTTP API. `mcp/booking-ops/` calls `booking-ops:8081`. `mcp/hotel-inventory/` calls `hotel-inventory:8080`. No business logic in MCP servers; no direct database access.

## Why
- Go services already enforce all business rules, validation, optimistic locking, and event logging. Duplicating this in MCP servers would create two implementations to keep in sync.
- MCP servers are ephemeral: they can be restarted, scaled, or replaced without affecting the booking data.
- Thin facade means the MCP layer adds only: protocol translation (MCP → HTTP), schema exposure (tool definitions), and authentication forwarding.
- This also means the same business logic is exercised whether a human uses the REST API, the LangGraph agent uses internal HTTP tools, or an MCP client uses the MCP server.

## Consequences
- MCP servers have no value without the Go services running. They are deployment dependencies, not standalone services.
- All latency-sensitive operations stay in Go. MCP servers add one extra HTTP hop, acceptable for interactive use.
