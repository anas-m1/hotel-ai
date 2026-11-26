-- Local development seed data
-- Run once after migrations:
--   docker compose exec postgres psql -U hotel -d hotel_inventory -f /seed.sql
-- (mount this file first, or pipe it: cat seed.sql | docker compose exec -T postgres psql -U hotel -d hotel_inventory)

-- Locations
INSERT INTO locations (city_code, city_name, county_code, county_name) VALUES
    ('DXB', 'Dubai',    'AE', 'United Arab Emirates'),
    ('LHR', 'London',   'GB', 'United Kingdom'),
    ('JFK', 'New York', 'US', 'United States')
ON CONFLICT (city_code) DO NOTHING;

-- Hotels
INSERT INTO hotels (hotel_code, name, rating, address, city_code, description, facilities, attractions) VALUES
    ('HTL001', 'Grand Marina Hotel',
     'five_star',
     '1 Marina Boulevard, Dubai',
     'DXB',
     'Luxury five-star hotel overlooking the marina with world-class dining and spa.',
     'pool,spa,gym,restaurant,bar,concierge,valet',
     'Dubai Marina Walk, JBR Beach, Dubai Eye'),

    ('HTL002', 'City Centre Suites',
     'four_star',
     '42 Oxford Street, London',
     'LHR',
     'Modern four-star hotel in the heart of London, steps from Hyde Park.',
     'gym,restaurant,bar,concierge,business-centre',
     'Hyde Park, Oxford Street, Marble Arch'),

    ('HTL003', 'Manhattan Boutique Hotel',
     'three_star',
     '315 West 48th Street, New York',
     'JFK',
     'Charming boutique hotel in Midtown Manhattan, near Times Square.',
     'gym,restaurant,concierge',
     'Times Square, Central Park, Broadway')
ON CONFLICT (hotel_code) DO NOTHING;

-- Rooms
INSERT INTO rooms (hotel_code, room_number, room_type, capacity, base_price, currency, amenities) VALUES
    ('HTL001', '101', 'double',   2, 450.00, 'USD', ARRAY['wifi','minibar','sea-view','jacuzzi']),
    ('HTL001', '102', 'suite',    3, 950.00, 'USD', ARRAY['wifi','minibar','sea-view','jacuzzi','butler']),
    ('HTL001', '201', 'deluxe',   2, 650.00, 'USD', ARRAY['wifi','minibar','pool-view']),
    ('HTL002', '101', 'single',   1, 180.00, 'USD', ARRAY['wifi','city-view']),
    ('HTL002', '102', 'double',   2, 280.00, 'USD', ARRAY['wifi','minibar','city-view']),
    ('HTL002', '201', 'twin',     2, 260.00, 'USD', ARRAY['wifi','city-view']),
    ('HTL003', '101', 'single',   1,  99.00, 'USD', ARRAY['wifi']),
    ('HTL003', '102', 'double',   2, 149.00, 'USD', ARRAY['wifi','city-view']),
    ('HTL003', '103', 'twin',     2, 139.00, 'USD', ARRAY['wifi'])
ON CONFLICT (hotel_code, room_number) DO NOTHING;
