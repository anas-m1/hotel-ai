package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

type BookingStatus string

const (
	StatusPending    BookingStatus = "pending"
	StatusConfirmed  BookingStatus = "confirmed"
	StatusCheckedIn  BookingStatus = "checked_in"
	StatusCheckedOut BookingStatus = "checked_out"
	StatusCancelled  BookingStatus = "cancelled"
	StatusNoShow     BookingStatus = "no_show"
)

type Guest struct {
	ID          uuid.UUID `json:"id"`
	Email       string    `json:"email"`
	FirstName   string    `json:"first_name"`
	LastName    string    `json:"last_name"`
	Phone       string    `json:"phone,omitempty"`
	Nationality string    `json:"nationality,omitempty"`
	PassportNo  string    `json:"passport_no,omitempty"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

type Booking struct {
	ID              uuid.UUID     `json:"id"`
	GuestID         uuid.UUID     `json:"guest_id"`
	HotelCode       string        `json:"hotel_code"`
	RoomID          uuid.UUID     `json:"room_id"`
	Status          BookingStatus `json:"status"`
	CheckInDate     time.Time     `json:"check_in_date"`
	CheckOutDate    time.Time     `json:"check_out_date"`
	TotalPrice      string        `json:"total_price"`
	Currency        string        `json:"currency"`
	SpecialRequests string        `json:"special_requests,omitempty"`
	Version         int32         `json:"version"`
	CreatedAt       time.Time     `json:"created_at"`
	UpdatedAt       time.Time     `json:"updated_at"`
}

type BookingEvent struct {
	ID          int64           `json:"id"`
	BookingID   uuid.UUID       `json:"booking_id"`
	EventType   string          `json:"event_type"`
	Payload     json.RawMessage `json:"payload"`
	TriggeredBy string          `json:"triggered_by"`
	CreatedAt   time.Time       `json:"created_at"`
}
