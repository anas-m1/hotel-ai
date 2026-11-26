package handler_test

// Hand-written stubs implementing the repository interfaces.
// Each stub field is a function so individual tests can override just the
// method they care about — unset fields panic, making accidental calls obvious.

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/hotel-ai/booking-ops/internal/domain"
)

// --- GuestRepository stub ---

type stubGuests struct {
	getByID    func(ctx context.Context, id uuid.UUID) (domain.Guest, error)
	getByEmail func(ctx context.Context, email string) (domain.Guest, error)
	upsert     func(ctx context.Context, g domain.Guest) (domain.Guest, error)
}

func (s *stubGuests) GetByID(ctx context.Context, id uuid.UUID) (domain.Guest, error) {
	return s.getByID(ctx, id)
}
func (s *stubGuests) GetByEmail(ctx context.Context, email string) (domain.Guest, error) {
	return s.getByEmail(ctx, email)
}
func (s *stubGuests) Upsert(ctx context.Context, g domain.Guest) (domain.Guest, error) {
	return s.upsert(ctx, g)
}

// --- BookingRepository stub ---

type stubBookings struct {
	getByID           func(ctx context.Context, id uuid.UUID) (domain.Booking, error)
	listByGuest       func(ctx context.Context, guestID uuid.UUID, limit, offset int32) ([]domain.Booking, error)
	listByHotel       func(ctx context.Context, hotelCode string) ([]domain.Booking, error)
	create            func(ctx context.Context, b domain.Booking) (domain.Booking, error)
	updateStatus      func(ctx context.Context, id uuid.UUID, version int32, status domain.BookingStatus) (domain.Booking, error)
	checkAvailability func(ctx context.Context, roomID uuid.UUID, checkIn, checkOut time.Time) (int64, error)
}

func (s *stubBookings) GetByID(ctx context.Context, id uuid.UUID) (domain.Booking, error) {
	return s.getByID(ctx, id)
}
func (s *stubBookings) ListByGuest(ctx context.Context, guestID uuid.UUID, limit, offset int32) ([]domain.Booking, error) {
	return s.listByGuest(ctx, guestID, limit, offset)
}
func (s *stubBookings) ListByHotel(ctx context.Context, hotelCode string) ([]domain.Booking, error) {
	return s.listByHotel(ctx, hotelCode)
}
func (s *stubBookings) Create(ctx context.Context, b domain.Booking) (domain.Booking, error) {
	return s.create(ctx, b)
}
func (s *stubBookings) UpdateStatus(ctx context.Context, id uuid.UUID, version int32, status domain.BookingStatus) (domain.Booking, error) {
	return s.updateStatus(ctx, id, version, status)
}
func (s *stubBookings) CheckAvailability(ctx context.Context, roomID uuid.UUID, checkIn, checkOut time.Time) (int64, error) {
	return s.checkAvailability(ctx, roomID, checkIn, checkOut)
}

// --- BookingEventRepository stub ---

type stubEvents struct {
	insert        func(ctx context.Context, bookingID uuid.UUID, eventType string, payload any, triggeredBy string) (domain.BookingEvent, error)
	listByBooking func(ctx context.Context, bookingID uuid.UUID) ([]domain.BookingEvent, error)
}

func (s *stubEvents) Insert(ctx context.Context, bookingID uuid.UUID, eventType string, payload any, triggeredBy string) (domain.BookingEvent, error) {
	return s.insert(ctx, bookingID, eventType, payload, triggeredBy)
}
func (s *stubEvents) ListByBooking(ctx context.Context, bookingID uuid.UUID) ([]domain.BookingEvent, error) {
	return s.listByBooking(ctx, bookingID)
}
