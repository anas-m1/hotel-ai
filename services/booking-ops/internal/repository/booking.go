package repository

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/hotel-ai/booking-ops/internal/domain"
	db "github.com/hotel-ai/booking-ops/internal/repository/db"
)

// --- interfaces ---

type GuestRepository interface {
	GetByID(ctx context.Context, id uuid.UUID) (domain.Guest, error)
	GetByEmail(ctx context.Context, email string) (domain.Guest, error)
	Upsert(ctx context.Context, g domain.Guest) (domain.Guest, error)
}

type BookingRepository interface {
	GetByID(ctx context.Context, id uuid.UUID) (domain.Booking, error)
	ListByGuest(ctx context.Context, guestID uuid.UUID, limit, offset int32) ([]domain.Booking, error)
	ListByHotel(ctx context.Context, hotelCode string) ([]domain.Booking, error)
	Create(ctx context.Context, b domain.Booking) (domain.Booking, error)
	UpdateStatus(ctx context.Context, id uuid.UUID, version int32, status domain.BookingStatus) (domain.Booking, error)
	CheckAvailability(ctx context.Context, roomID uuid.UUID, checkIn, checkOut time.Time) (int64, error)
}

type BookingEventRepository interface {
	Insert(ctx context.Context, bookingID uuid.UUID, eventType string, payload any, triggeredBy string) (domain.BookingEvent, error)
	ListByBooking(ctx context.Context, bookingID uuid.UUID) ([]domain.BookingEvent, error)
}

// --- Guest ---

type postgresGuestRepo struct{ q *db.Queries }

func NewGuestRepository(q *db.Queries) GuestRepository { return &postgresGuestRepo{q: q} }

func (r *postgresGuestRepo) GetByID(ctx context.Context, id uuid.UUID) (domain.Guest, error) {
	row, err := r.q.GetGuestByID(ctx, id)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return domain.Guest{}, domain.ErrNotFound
		}
		return domain.Guest{}, err
	}
	return guestFromDB(row), nil
}

func (r *postgresGuestRepo) GetByEmail(ctx context.Context, email string) (domain.Guest, error) {
	row, err := r.q.GetGuestByEmail(ctx, email)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return domain.Guest{}, domain.ErrNotFound
		}
		return domain.Guest{}, err
	}
	return guestFromDB(row), nil
}

func (r *postgresGuestRepo) Upsert(ctx context.Context, g domain.Guest) (domain.Guest, error) {
	row, err := r.q.UpsertGuest(ctx, db.UpsertGuestParams{
		Email:       g.Email,
		FirstName:   g.FirstName,
		LastName:    g.LastName,
		Phone:       strToPtr(g.Phone),
		Nationality: strToPtr(g.Nationality),
		PassportNo:  strToPtr(g.PassportNo),
	})
	if err != nil {
		return domain.Guest{}, err
	}
	return guestFromDB(row), nil
}

// --- Booking ---

type postgresBookingRepo struct{ q *db.Queries }

func NewBookingRepository(q *db.Queries) BookingRepository { return &postgresBookingRepo{q: q} }

func (r *postgresBookingRepo) GetByID(ctx context.Context, id uuid.UUID) (domain.Booking, error) {
	row, err := r.q.GetBookingByID(ctx, id)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return domain.Booking{}, domain.ErrNotFound
		}
		return domain.Booking{}, err
	}
	return bookingFromDB(row), nil
}

func (r *postgresBookingRepo) ListByGuest(ctx context.Context, guestID uuid.UUID, limit, offset int32) ([]domain.Booking, error) {
	rows, err := r.q.ListBookingsByGuest(ctx, db.ListBookingsByGuestParams{
		GuestID: guestID,
		Limit:   limit,
		Offset:  offset,
	})
	if err != nil {
		return nil, err
	}
	return bookingsFromDB(rows), nil
}

func (r *postgresBookingRepo) ListByHotel(ctx context.Context, hotelCode string) ([]domain.Booking, error) {
	rows, err := r.q.ListBookingsByHotel(ctx, hotelCode)
	if err != nil {
		return nil, err
	}
	return bookingsFromDB(rows), nil
}

func (r *postgresBookingRepo) Create(ctx context.Context, b domain.Booking) (domain.Booking, error) {
	row, err := r.q.CreateBooking(ctx, db.CreateBookingParams{
		GuestID:         b.GuestID,
		HotelCode:       b.HotelCode,
		RoomID:          b.RoomID,
		CheckInDate:     b.CheckInDate,
		CheckOutDate:    b.CheckOutDate,
		TotalPrice:      b.TotalPrice,
		Currency:        b.Currency,
		SpecialRequests: strToPtr(b.SpecialRequests),
	})
	if err != nil {
		return domain.Booking{}, err
	}
	return bookingFromDB(row), nil
}

func (r *postgresBookingRepo) UpdateStatus(ctx context.Context, id uuid.UUID, version int32, status domain.BookingStatus) (domain.Booking, error) {
	row, err := r.q.UpdateBookingStatus(ctx, db.UpdateBookingStatusParams{
		ID:      id,
		Version: version,
		Status:  db.BookingStatus(status),
	})
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			// No row updated: either booking doesn't exist or version is stale.
			// Callers hold the booking already, so treat as optimistic lock failure.
			return domain.Booking{}, domain.ErrVersionConflict
		}
		return domain.Booking{}, err
	}
	return bookingFromDB(row), nil
}

func (r *postgresBookingRepo) CheckAvailability(ctx context.Context, roomID uuid.UUID, checkIn, checkOut time.Time) (int64, error) {
	return r.q.CheckRoomAvailability(ctx, db.CheckRoomAvailabilityParams{
		RoomID:       roomID,
		CheckInDate:  checkIn,
		CheckOutDate: checkOut,
	})
}

// --- BookingEvent ---

type postgresEventRepo struct{ q *db.Queries }

func NewBookingEventRepository(q *db.Queries) BookingEventRepository {
	return &postgresEventRepo{q: q}
}

func (r *postgresEventRepo) Insert(ctx context.Context, bookingID uuid.UUID, eventType string, payload any, triggeredBy string) (domain.BookingEvent, error) {
	raw, err := json.Marshal(payload)
	if err != nil {
		return domain.BookingEvent{}, err
	}
	row, err := r.q.InsertBookingEvent(ctx, db.InsertBookingEventParams{
		BookingID:   bookingID,
		EventType:   eventType,
		Payload:     raw,
		TriggeredBy: triggeredBy,
	})
	if err != nil {
		return domain.BookingEvent{}, err
	}
	return eventFromDB(row), nil
}

func (r *postgresEventRepo) ListByBooking(ctx context.Context, bookingID uuid.UUID) ([]domain.BookingEvent, error) {
	rows, err := r.q.ListEventsByBooking(ctx, bookingID)
	if err != nil {
		return nil, err
	}
	out := make([]domain.BookingEvent, len(rows))
	for i, row := range rows {
		out[i] = eventFromDB(row)
	}
	return out, nil
}

// --- mapping: db → domain ---

func guestFromDB(row db.Guest) domain.Guest {
	return domain.Guest{
		ID:          row.ID,
		Email:       row.Email,
		FirstName:   row.FirstName,
		LastName:    row.LastName,
		Phone:       ptrToStr(row.Phone),
		Nationality: ptrToStr(row.Nationality),
		PassportNo:  ptrToStr(row.PassportNo),
		CreatedAt:   row.CreatedAt,
		UpdatedAt:   row.UpdatedAt,
	}
}

func bookingFromDB(row db.Booking) domain.Booking {
	return domain.Booking{
		ID:              row.ID,
		GuestID:         row.GuestID,
		HotelCode:       row.HotelCode,
		RoomID:          row.RoomID,
		Status:          domain.BookingStatus(row.Status),
		CheckInDate:     row.CheckInDate,
		CheckOutDate:    row.CheckOutDate,
		TotalPrice:      row.TotalPrice,
		Currency:        row.Currency,
		SpecialRequests: ptrToStr(row.SpecialRequests),
		Version:         row.Version,
		CreatedAt:       row.CreatedAt,
		UpdatedAt:       row.UpdatedAt,
	}
}

func bookingsFromDB(rows []db.Booking) []domain.Booking {
	out := make([]domain.Booking, len(rows))
	for i, row := range rows {
		out[i] = bookingFromDB(row)
	}
	return out
}

func eventFromDB(row db.BookingEvent) domain.BookingEvent {
	return domain.BookingEvent{
		ID:          row.ID,
		BookingID:   row.BookingID,
		EventType:   row.EventType,
		Payload:     row.Payload,
		TriggeredBy: row.TriggeredBy,
		CreatedAt:   row.CreatedAt,
	}
}

// --- helpers ---

func strToPtr(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

func ptrToStr(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
