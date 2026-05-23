-- name: GetHotelByCode :one
SELECT * FROM hotels
WHERE hotel_code = $1;

-- name: ListHotelsByCity :many
SELECT * FROM hotels
WHERE city_code = $1
ORDER BY name
LIMIT $2 OFFSET $3;

-- name: ListHotelsByRating :many
SELECT * FROM hotels
WHERE rating = $1
ORDER BY name
LIMIT $2 OFFSET $3;

-- name: SearchHotelsFTS :many
SELECT * FROM hotels
WHERE to_tsvector('english',
        coalesce(name, '')        || ' ' ||
        coalesce(description, '') || ' ' ||
        coalesce(attractions, '') || ' ' ||
        coalesce(facilities, '')
      ) @@ plainto_tsquery('english', $1)
ORDER BY ts_rank(
    to_tsvector('english',
        coalesce(name, '')        || ' ' ||
        coalesce(description, '') || ' ' ||
        coalesce(attractions, '') || ' ' ||
        coalesce(facilities, '')
    ),
    plainto_tsquery('english', $1)
) DESC
LIMIT $2 OFFSET $3;

-- name: UpsertHotel :exec
INSERT INTO hotels (
    hotel_code, name, rating, address, pin_code,
    lat, lng, phone, fax, website_url,
    facilities, description, attractions, city_code
) VALUES (
    $1, $2, $3, $4, $5,
    $6, $7, $8, $9, $10,
    $11, $12, $13, $14
)
ON CONFLICT (hotel_code) DO UPDATE SET
    name        = EXCLUDED.name,
    rating      = EXCLUDED.rating,
    address     = EXCLUDED.address,
    pin_code    = EXCLUDED.pin_code,
    lat         = EXCLUDED.lat,
    lng         = EXCLUDED.lng,
    phone       = EXCLUDED.phone,
    fax         = EXCLUDED.fax,
    website_url = EXCLUDED.website_url,
    facilities  = EXCLUDED.facilities,
    description = EXCLUDED.description,
    attractions = EXCLUDED.attractions,
    city_code   = EXCLUDED.city_code,
    updated_at  = NOW();

-- name: ListHotelsForEmbedding :many
-- Used by the RAG pipeline to batch-fetch hotels for Qdrant ingestion.
SELECT hotel_code, name, rating, city_code, lat, lng,
       description, attractions, facilities
FROM hotels
ORDER BY hotel_code
LIMIT $1 OFFSET $2;

-- name: CountHotels :one
SELECT COUNT(*) FROM hotels;

-- name: CountHotelsByCity :one
SELECT COUNT(*) FROM hotels WHERE city_code = $1;
