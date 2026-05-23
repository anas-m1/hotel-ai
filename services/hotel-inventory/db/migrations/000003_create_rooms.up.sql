CREATE TYPE room_type AS ENUM (
    'single',
    'double',
    'twin',
    'suite',
    'deluxe',
    'penthouse'
);

CREATE TABLE rooms (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_code  TEXT          NOT NULL REFERENCES hotels(hotel_code) ON DELETE CASCADE,
    room_number TEXT          NOT NULL,
    room_type   room_type     NOT NULL,
    capacity    SMALLINT      NOT NULL DEFAULT 2,
    base_price  NUMERIC(10,2) NOT NULL,
    currency    CHAR(3)       NOT NULL DEFAULT 'USD',
    amenities   TEXT[],
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE(hotel_code, room_number)
);

CREATE INDEX idx_rooms_hotel_code ON rooms(hotel_code);
CREATE INDEX idx_rooms_type       ON rooms(room_type);
CREATE INDEX idx_rooms_price      ON rooms(base_price);
CREATE INDEX idx_rooms_active     ON rooms(hotel_code) WHERE is_active = TRUE;
