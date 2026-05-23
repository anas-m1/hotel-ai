-- name: InsertBookingEvent :one
INSERT INTO booking_events (booking_id, event_type, payload, triggered_by)
VALUES ($1, $2, $3, $4)
RETURNING *;

-- name: ListEventsByBooking :many
SELECT * FROM booking_events
WHERE booking_id = $1
ORDER BY created_at ASC;

-- name: ListEventsByType :many
SELECT * FROM booking_events
WHERE event_type = $1
ORDER BY created_at DESC
LIMIT $2 OFFSET $3;
