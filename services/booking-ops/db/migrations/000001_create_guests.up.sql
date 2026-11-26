CREATE TABLE guests (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email        TEXT        NOT NULL UNIQUE,
    first_name   TEXT        NOT NULL,
    last_name    TEXT        NOT NULL,
    phone        TEXT,
    nationality  CHAR(2),    -- ISO 3166-1 alpha-2
    passport_no  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_guests_email ON guests(email);
