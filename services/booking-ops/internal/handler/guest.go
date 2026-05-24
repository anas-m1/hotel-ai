package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"github.com/hotel-ai/booking-ops/internal/domain"
	"github.com/hotel-ai/booking-ops/internal/repository"
)

func mountGuestRoutes(r chi.Router, repo repository.GuestRepository) {
	r.Post("/guests", upsertGuest(repo))
	r.Get("/guests/{id}", getGuest(repo))
}

func upsertGuest(repo repository.GuestRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var body domain.Guest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		if body.Email == "" || body.FirstName == "" || body.LastName == "" {
			writeError(w, http.StatusBadRequest, "email, first_name, and last_name are required")
			return
		}
		guest, err := repo.Upsert(r.Context(), body)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, guest)
	}
}

func getGuest(repo repository.GuestRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := uuid.Parse(chi.URLParam(r, "id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid guest id")
			return
		}
		guest, err := repo.GetByID(r.Context(), id)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, guest)
	}
}
