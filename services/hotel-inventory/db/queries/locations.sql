-- name: GetLocationByCityCode :one
SELECT * FROM locations
WHERE city_code = $1;

-- name: ListLocationsByCounty :many
SELECT * FROM locations
WHERE county_code = $1
ORDER BY city_name;

-- name: UpsertLocation :exec
INSERT INTO locations (city_code, city_name, county_code, county_name)
VALUES ($1, $2, $3, $4)
ON CONFLICT (city_code) DO UPDATE SET
    city_name   = EXCLUDED.city_name,
    county_name = EXCLUDED.county_name;
