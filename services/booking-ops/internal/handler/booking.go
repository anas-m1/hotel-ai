package handler

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"github.com/hotel-ai/booking-ops/internal/domain"
	"github.com/hotel-ai/booking-ops/internal/repository"
)

func mountBookingRoutes(r chi.Router, bookings repository.BookingRepository, events repository.BookingEventRepository) {
	r.Post("/bookings", createBooking(bookings, events))
	r.Get("/bookings/{id}", getBooking(bookings, events))
	r.Post("/bookings/{id}/status", updateBookingStatus(bookings, events))
	r.Get("/guests/{id}/bookings", listBookingsByGuest(bookings))
	r.Get("/hotels/{code}/bookings", listBookingsByHotel(bookings))
	r.Get("/availability", checkAvailability(bookings))
}

// --- request types ---

type createBookingRequest struct {
	GuestID         uuid.UUID `json:"guest_id"`
	HotelCode       string    `json:"hotel_code"`
	RoomID          uuid.UUID `json:"room_id"`
	CheckInDate     string    `json:"check_in_date"`
	CheckOutDate    string    `json:"check_out_date"`
	TotalPrice      string    `json:"total_price"`
	Currency        string    `json:"currency"`
	SpecialRequests string    `json:"special_requests"`
}

type updateStatusRequest struct {
	Status  domain.BookingStatus `json:"status"`
	Version int32                `json:"version"`
}

type bookingWithEvents struct {
	domain.Booking
	Events []domain.BookingEvent `json:"events"`
}

// --- handlers ---

func createBooking(bookings repository.BookingRepository, events repository.BookingEventRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var body createBookingRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		if body.HotelCode == "" || body.TotalPrice == "" {
			writeError(w, http.StatusBadRequest, "hotel_code and total_price are required")
			return
		}

		checkIn, err := time.Parse("2006-01-02", body.CheckInDate)
		if err != nil {
			writeError(w, http.StatusBadRequest, "check_in_date must be YYYY-MM-DD")
			return
		}
		checkOut, err := time.Parse("2006-01-02", body.CheckOutDate)
		if err != nil {
			writeError(w, http.StatusBadRequest, "check_out_date must be YYYY-MM-DD")
			return
		}
		if !checkOut.After(checkIn) {
			writeError(w, http.StatusBadRequest, "check_out_date must be after check_in_date")
			return
		}
		if body.Currency == "" {
			body.Currency = "USD"
		}

		// Check room availability before creating.
		// Note: TOCTOU race is possible here; a serializable transaction would eliminate it.
		// Acceptable for Phase 1 — revisit when adding payment flow in Phase 4.
		count, err := bookings.CheckAvailability(r.Context(), body.RoomID, checkIn, checkOut)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		if count > 0 {
			writeError(w, http.StatusConflict, "room is not available for the requested dates")
			return
		}

		booking, err := bookings.Create(r.Context(), domain.Booking{
			GuestID:         body.GuestID,
			HotelCode:       body.HotelCode,
			RoomID:          body.RoomID,
			CheckInDate:     checkIn,
			CheckOutDate:    checkOut,
			TotalPrice:      body.TotalPrice,
			Currency:        body.Currency,
			SpecialRequests: body.SpecialRequests,
		})
		if err != nil {
			mapDomainError(w, err)
			return
		}

		_, _ = events.Insert(r.Context(), booking.ID, "BookingCreated", booking, "guest")

		writeJSON(w, http.StatusCreated, booking)
	}
}

func getBooking(bookings repository.BookingRepository, events repository.BookingEventRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := uuid.Parse(chi.URLParam(r, "id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid booking id")
			return
		}
		booking, err := bookings.GetByID(r.Context(), id)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		evts, err := events.ListByBooking(r.Context(), id)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, bookingWithEvents{Booking: booking, Events: evts})
	}
}

func updateBookingStatus(bookings repository.BookingRepository, events repository.BookingEventRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := uuid.Parse(chi.URLParam(r, "id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid booking id")
			return
		}
		var body updateStatusRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		if body.Status == "" {
			writeError(w, http.StatusBadRequest, "status is required")
			return
		}

		updated, err := bookings.UpdateStatus(r.Context(), id, body.Version, body.Status)
		if err != nil {
			mapDomainError(w, err)
			return
		}

		_, _ = events.Insert(r.Context(), updated.ID, "BookingStatusUpdated",
			map[string]any{"status": updated.Status, "version": updated.Version}, "guest")

		writeJSON(w, http.StatusOK, updated)
	}
}

func listBookingsByGuest(bookings repository.BookingRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := uuid.Parse(chi.URLParam(r, "id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid guest id")
			return
		}
		limit, offset := parsePagination(r)
		list, err := bookings.ListByGuest(r.Context(), id, limit, offset)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, list)
	}
}

func listBookingsByHotel(bookings repository.BookingRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		list, err := bookings.ListByHotel(r.Context(), chi.URLParam(r, "code"))
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, list)
	}
}

func checkAvailability(bookings repository.BookingRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()

		roomID, err := uuid.Parse(q.Get("room_id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "room_id must be a valid UUID")
			return
		}
		checkIn, err := time.Parse("2006-01-02", q.Get("check_in"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "check_in must be YYYY-MM-DD")
			return
		}
		checkOut, err := time.Parse("2006-01-02", q.Get("check_out"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "check_out must be YYYY-MM-DD")
			return
		}

		count, err := bookings.CheckAvailability(r.Context(), roomID, checkIn, checkOut)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{
			"available":     count == 0,
			"overlap_count": count,
		})
	}
}
