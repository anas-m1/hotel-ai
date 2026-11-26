-- name: GetBookingByID :one
SELECT * FROM bookings WHERE id = $1;

-- name: ListBookingsByGuest :many
SELECT * FROM bookings
WHERE guest_id = $1
ORDER BY created_at DESC
LIMIT $2 OFFSET $3;

-- name: ListBookingsByHotel :many
SELECT * FROM bookings
WHERE hotel_code = $1
  AND status NOT IN ('cancelled', 'no_show')
ORDER BY check_in_date;

-- name: CreateBooking :one
INSERT INTO bookings (
    guest_id, hotel_code, room_id,
    status, check_in_date, check_out_date,
    total_price, currency, special_requests
) VALUES (
    $1, $2, $3,
    'pending', $4, $5,
    $6, $7, $8
)
RETURNING *;

-- name: UpdateBookingStatus :one
-- Uses optimistic locking: increments version and checks current version matches.
UPDATE bookings SET
    status     = $3,
    version    = version + 1,
    updated_at = NOW()
WHERE id = $1
  AND version = $2
RETURNING *;

-- name: CheckRoomAvailability :one
-- Returns count of active bookings that overlap the requested dates.
-- Zero means the room is available.
SELECT COUNT(*) FROM bookings
WHERE room_id        = sqlc.arg(room_id)
  AND status        NOT IN ('cancelled', 'no_show')
  AND check_in_date  < sqlc.arg(check_out_date)
  AND check_out_date > sqlc.arg(check_in_date);
