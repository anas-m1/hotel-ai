CREATE TYPE booking_status AS ENUM (
    'pending',      -- created, awaiting payment confirmation
    'confirmed',    -- payment accepted, room reserved
    'checked_in',   -- guest has arrived
    'checked_out',  -- stay completed
    'cancelled',    -- cancelled before check-in
    'no_show'       -- guest did not arrive
);

CREATE TABLE bookings (
    id               UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id         UUID           NOT NULL REFERENCES guests(id),
    hotel_code       TEXT           NOT NULL,  -- ref to hotel-inventory (no FK — cross-service)
    room_id          UUID           NOT NULL,  -- ref to hotel-inventory (no FK — cross-service)
    status           booking_status NOT NULL DEFAULT 'pending',
    check_in_date    DATE           NOT NULL,
    check_out_date   DATE           NOT NULL,
    total_price      NUMERIC(10,2)  NOT NULL,
    currency         CHAR(3)        NOT NULL DEFAULT 'USD',
    special_requests TEXT,
    version          INT            NOT NULL DEFAULT 1,  -- optimistic locking
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_dates CHECK (check_out_date > check_in_date)
);

-- availability check: overlapping active bookings for a room
CREATE INDEX idx_bookings_room_dates ON bookings(room_id, check_in_date, check_out_date)
    WHERE status NOT IN ('cancelled', 'no_show');

CREATE INDEX idx_bookings_guest_id   ON bookings(guest_id);
CREATE INDEX idx_bookings_hotel_code ON bookings(hotel_code);
CREATE INDEX idx_bookings_status     ON bookings(status);
