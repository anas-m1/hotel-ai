package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"github.com/hotel-ai/hotel-inventory/internal/domain"
	"github.com/hotel-ai/hotel-inventory/internal/repository"
)

func mountRoomRoutes(r chi.Router, repo repository.RoomRepository) {
	r.Get("/hotels/{code}/rooms", listRooms(repo))
	r.Post("/hotels/{code}/rooms", createRoom(repo))
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
