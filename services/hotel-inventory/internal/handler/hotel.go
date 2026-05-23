package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/hotel-ai/hotel-inventory/internal/domain"
	"github.com/hotel-ai/hotel-inventory/internal/repository"
)

func mountHotelRoutes(r chi.Router, repo repository.HotelRepository) {
	r.Get("/hotels/{code}", getHotel(repo))
	r.Get("/hotels", listHotels(repo))
	r.Put("/hotels/{code}", upsertHotel(repo))
}

func getHotel(repo repository.HotelRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hotel, err := repo.GetByCode(r.Context(), chi.URLParam(r, "code"))
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, hotel)
	}
}

// listHotels dispatches to the right query based on which filter param is present:
//
//	?city=NYC           → ListByCity
//	?rating=four_star   → ListByRating
//	?q=beach+resort     → full-text search
func listHotels(repo repository.HotelRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := parsePagination(r)
		q := r.URL.Query()

		var hotels []domain.Hotel
		var err error

		switch {
		case q.Get("city") != "":
			hotels, err = repo.ListByCity(r.Context(), q.Get("city"), limit, offset)
		case q.Get("rating") != "":
			hotels, err = repo.ListByRating(r.Context(), domain.HotelRating(q.Get("rating")), limit, offset)
		case q.Get("q") != "":
			hotels, err = repo.Search(r.Context(), q.Get("q"), limit, offset)
		default:
			writeError(w, http.StatusBadRequest, "one of city, rating, or q is required")
			return
		}

		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, hotels)
	}
}

func upsertHotel(repo repository.HotelRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hotelCode := chi.URLParam(r, "code")
		var body domain.Hotel
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		body.HotelCode = hotelCode
		if body.Name == "" || body.CityCode == "" {
			writeError(w, http.StatusBadRequest, "name and city_code are required")
			return
		}
		if body.Rating == "" {
			body.Rating = domain.RatingUnrated
		}
		if err := repo.Upsert(r.Context(), body); err != nil {
			mapDomainError(w, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}
