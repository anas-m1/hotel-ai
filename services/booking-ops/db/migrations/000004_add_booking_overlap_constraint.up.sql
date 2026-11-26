-- Atomically prevents double-booking the same room for overlapping dates.
-- The exclusion constraint makes the DB the enforcement point, eliminating
-- the TOCTOU race between CheckAvailability and CreateBooking.
--
-- daterange '[)' = inclusive check_in, exclusive check_out (standard convention:
-- check out at noon means the night of check_out_date - 1 is the last paid night).

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE bookings ADD CONSTRAINT no_double_booking
    EXCLUDE USING gist (
        room_id                                          WITH =,
        daterange(check_in_date, check_out_date, '[)')   WITH &&
    )
    WHERE (status NOT IN ('cancelled', 'no_show'));
