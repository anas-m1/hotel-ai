CREATE TYPE hotel_rating AS ENUM (
    'one_star',
    'two_star',
    'three_star',
    'four_star',
    'five_star',
    'unrated'
);

CREATE TABLE hotels (
    hotel_code  TEXT         PRIMARY KEY,
    name        TEXT         NOT NULL,
    rating      hotel_rating NOT NULL DEFAULT 'unrated',
    address     TEXT,
    pin_code    TEXT,
    lat         NUMERIC(9,6),
    lng         NUMERIC(9,6),
    phone       TEXT,
    fax         TEXT,
    website_url TEXT,
    facilities  TEXT,
    description TEXT,
    attractions TEXT,
    city_code   TEXT         NOT NULL REFERENCES locations(city_code),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- fast lookup by city/county
CREATE INDEX idx_hotels_city_code ON hotels(city_code);

-- filter by star rating
CREATE INDEX idx_hotels_rating ON hotels(rating);

-- geo bounding box queries (lat/lng range scans)
CREATE INDEX idx_hotels_lat ON hotels(lat);
CREATE INDEX idx_hotels_lng ON hotels(lng);

-- full-text search on name, description, facilities, attractions
CREATE INDEX idx_hotels_fts ON hotels
    USING gin(
        to_tsvector('english',
            coalesce(name, '')        || ' ' ||
            coalesce(description, '') || ' ' ||
            coalesce(attractions, '') || ' ' ||
            coalesce(facilities, '')
        )
    );
