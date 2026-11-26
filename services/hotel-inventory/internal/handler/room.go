package handler

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"github.com/hotel-ai/hotel-inventory/internal/config"
	"github.com/hotel-ai/hotel-inventory/internal/domain"
	"github.com/hotel-ai/hotel-inventory/internal/repository"
)

func mountRoomRoutes(r chi.Router, repo repository.RoomRepository, cfg config.Config) {
	r.Get("/hotels/{code}/rooms", listRooms(repo))
	r.Post("/hotels/{code}/rooms", createRoom(repo))
	r.Get("/hotels/{code}/rooms/{roomID}/availability", checkRoomAvailability(repo, cfg))
	r.Get("/rooms/{id}", getRoom(repo))
	r.Put("/rooms/{id}", updateRoom(repo))
	r.Delete("/rooms/{id}", deactivateRoom(repo))
}

func getRoom(repo repository.RoomRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := uuid.Parse(chi.URLParam(r, "id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid room id")
			return
		}
		room, err := repo.GetByID(r.Context(), id)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, room)
	}
}

// listRooms returns active rooms by default; pass ?type=suite to filter by type.
func listRooms(repo repository.RoomRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hotelCode := chi.URLParam(r, "code")
		roomType := r.URL.Query().Get("type")

		var rooms []domain.Room
		var err error

		if roomType != "" {
			rooms, err = repo.ListByType(r.Context(), hotelCode, domain.RoomType(roomType))
		} else {
			rooms, err = repo.ListActiveByHotel(r.Context(), hotelCode)
		}

		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, rooms)
	}
}

func createRoom(repo repository.RoomRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hotelCode := chi.URLParam(r, "code")
		var body domain.Room
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		body.HotelCode = hotelCode
		if body.RoomNumber == "" || body.RoomType == "" || body.BasePrice == "" {
			writeError(w, http.StatusBadRequest, "room_number, room_type, and base_price are required")
			return
		}
		if body.Currency == "" {
			body.Currency = "USD"
		}
		if body.Capacity == 0 {
			body.Capacity = 2
		}
		created, err := repo.Create(r.Context(), body)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusCreated, created)
	}
}

func updateRoom(repo repository.RoomRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := uuid.Parse(chi.URLParam(r, "id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid room id")
			return
		}
		var body domain.Room
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		body.ID = id
		updated, err := repo.Update(r.Context(), body)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, updated)
	}
}

func deactivateRoom(repo repository.RoomRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := uuid.Parse(chi.URLParam(r, "id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid room id")
			return
		}
		if err := repo.Deactivate(r.Context(), id); err != nil {
			mapDomainError(w, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}

// checkRoomAvailability proxies to booking-ops for conflict data, then
// enriches the response with total_price from the room's base_price.
func checkRoomAvailability(rooms repository.RoomRepository, cfg config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		roomID, err := uuid.Parse(chi.URLParam(r, "roomID"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid room id")
			return
		}
		checkIn := r.URL.Query().Get("check_in")
		checkOut := r.URL.Query().Get("check_out")
		if checkIn == "" || checkOut == "" {
			writeError(w, http.StatusBadRequest, "check_in and check_out are required (YYYY-MM-DD)")
			return
		}

		// Load room to get base_price and verify it belongs to this hotel.
		room, err := rooms.GetByID(r.Context(), roomID)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		if room.HotelCode != chi.URLParam(r, "code") {
			writeError(w, http.StatusNotFound, "room not found for this hotel")
			return
		}

		// Ask booking-ops whether any overlapping reservations exist.
		url := fmt.Sprintf("%s/v1/availability?room_id=%s&check_in=%s&check_out=%s",
			cfg.BookingOpsURL, roomID, checkIn, checkOut)
		resp, err := http.Get(url) //nolint:noctx
		if err != nil {
			writeError(w, http.StatusBadGateway, "could not reach booking service")
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		if resp.StatusCode != http.StatusOK {
			writeError(w, http.StatusBadGateway, "booking service error")
			return
		}

		var avail struct {
			Available    bool `json:"available"`
			OverlapCount int  `json:"overlap_count"`
		}
		if err := json.Unmarshal(body, &avail); err != nil {
			writeError(w, http.StatusInternalServerError, "invalid booking service response")
			return
		}

		// Calculate total price: base_price × nights.
		in, _ := time.Parse("2006-01-02", checkIn)
		out, _ := time.Parse("2006-01-02", checkOut)
		nights := int(out.Sub(in).Hours() / 24)
		if nights < 1 {
			nights = 1
		}
		basePrice, _ := strconv.ParseFloat(room.BasePrice, 64)
		totalPrice := basePrice * float64(nights)

		writeJSON(w, http.StatusOK, map[string]any{
			"available":   avail.Available,
			"room_id":     roomID,
			"hotel_code":  room.HotelCode,
			"check_in":    checkIn,
			"check_out":   checkOut,
			"nights":      nights,
			"total_price": fmt.Sprintf("%.2f", totalPrice),
			"currency":    room.Currency,
		})
	}
}
