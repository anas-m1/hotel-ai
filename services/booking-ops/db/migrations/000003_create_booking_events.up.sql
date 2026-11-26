-- Immutable event log — rows are never updated or deleted.
-- Each row records one state transition on a booking aggregate.
-- The full history of a booking can be replayed from this table alone.
CREATE TABLE booking_events (
    id           BIGSERIAL   PRIMARY KEY,
    booking_id   UUID        NOT NULL REFERENCES bookings(id),
    event_type   TEXT        NOT NULL,  -- e.g. "BookingCreated", "BookingConfirmed", "BookingCancelled"
    payload      JSONB       NOT NULL,  -- complete snapshot of event data
    triggered_by TEXT        NOT NULL,  -- "guest", "agent", "system", "admin"
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_booking_events_booking_id  ON booking_events(booking_id);
CREATE INDEX idx_booking_events_type        ON booking_events(event_type);
CREATE INDEX idx_booking_events_created_at  ON booking_events(created_at);

-- partial index for agent-triggered events — useful for Phase 4 agent tracing
CREATE INDEX idx_booking_events_agent ON booking_events(booking_id, created_at)
    WHERE triggered_by = 'agent';
