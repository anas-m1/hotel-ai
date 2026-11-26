-- name: GetGuestByID :one
SELECT * FROM guests WHERE id = $1;

-- name: GetGuestByEmail :one
SELECT * FROM guests WHERE email = $1;

-- name: CreateGuest :one
INSERT INTO guests (email, first_name, last_name, phone, nationality, passport_no)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING *;

-- name: UpdateGuest :one
UPDATE guests SET
    first_name   = $2,
    last_name    = $3,
    phone        = $4,
    nationality  = $5,
    passport_no  = $6,
    updated_at   = NOW()
WHERE id = $1
RETURNING *;

-- name: UpsertGuest :one
INSERT INTO guests (email, first_name, last_name, phone, nationality, passport_no)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (email) DO UPDATE SET
    first_name  = EXCLUDED.first_name,
    last_name   = EXCLUDED.last_name,
    phone       = EXCLUDED.phone,
    nationality = EXCLUDED.nationality,
    passport_no = EXCLUDED.passport_no,
    updated_at  = NOW()
RETURNING *;
