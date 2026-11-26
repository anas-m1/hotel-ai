# ADR-005: Chi as HTTP Router

**Date:** Phase 1  
**Status:** Accepted

## Context
Go services expose REST APIs. Need an HTTP router.

## Decision
**Chi** (`github.com/go-chi/chi/v5`)

## Why
- Stdlib-compatible (`http.Handler`) — no framework lock-in; all middleware composes with anything
- Idiomatic Go: no magic, no reflection, no custom context
- Built-in middleware stack (RequestID, RealIP, Logger, Recoverer) covers standard needs
- Lighter than Gin/Echo; `chi.URLParam` for path params is clean

## Consequences
- Less built-in validation than Gin — validation is a domain concern handled explicitly
