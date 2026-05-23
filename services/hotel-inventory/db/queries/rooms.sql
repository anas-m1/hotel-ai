-- name: GetRoomByID :one
SELECT * FROM rooms
WHERE id = $1;

-- name: ListRoomsByHotel :many
SELECT * FROM rooms
WHERE hotel_code = $1
ORDER BY room_number;

-- name: ListActiveRoomsByHotel :many
SELECT * FROM rooms
WHERE hotel_code = $1
  AND is_active = TRUE
ORDER BY room_number;

-- name: ListRoomsByType :many
SELECT * FROM rooms
WHERE hotel_code = $1
  AND room_type = $2
  AND is_active = TRUE
ORDER BY base_price;

-- name: CreateRoom :one
INSERT INTO rooms (hotel_code, room_number, room_type, capacity, base_price, currency, amenities)
VALUES ($1, $2, $3, $4, $5, $6, $7)
RETURNING *;

-- name: UpdateRoom :one
UPDATE rooms SET
    room_type  = $2,
    capacity   = $3,
    base_price = $4,
    currency   = $5,
    amenities  = $6,
    updated_at = NOW()
WHERE id = $1
RETURNING *;

-- name: DeactivateRoom :exec
UPDATE rooms SET
    is_active  = FALSE,
    updated_at = NOW()
WHERE id = $1;

-- name: CountActiveRoomsByHotel :one
SELECT COUNT(*) FROM rooms
WHERE hotel_code = $1
  AND is_active = TRUE;
