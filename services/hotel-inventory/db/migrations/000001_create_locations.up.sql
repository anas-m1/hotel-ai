CREATE TABLE locations (
    city_code   TEXT PRIMARY KEY,
    city_name   TEXT NOT NULL,
    county_code TEXT NOT NULL,
    county_name TEXT NOT NULL
);

CREATE INDEX idx_locations_county_code ON locations(county_code);
