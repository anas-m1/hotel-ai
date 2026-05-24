---
name: feedback-explain-before-proceeding
description: User pauses mid-implementation to ask why — explain non-obvious decisions proactively rather than waiting to be asked
metadata:
  type: feedback
---

When writing non-obvious code or making a non-obvious architectural decision, pause and explain the "why" before or immediately after writing — don't assume the implementation speaks for itself.

**Why:** In this session the user interrupted tool use with "explain" and "why optimistic locking over pessimistic" mid-stream. They learn by understanding the tradeoff, not just accepting the output. They also asked why a design choice (INSERT vs UPDATE for bookings) was even necessary — a question that wouldn't occur to someone already fluent in the domain.

**How to apply:** For any design decision that involves a tradeoff (locking strategy, schema constraint, protocol choice, architectural boundary), surface the key non-obvious reasoning in the accompanying message. Don't wait to be asked. If writing several files back-to-back, call out the one or two decisions that would surprise a reader rather than narrating every file.
