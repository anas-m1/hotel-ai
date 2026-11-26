package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/hotel-ai/hotel-inventory/internal/domain"
	"github.com/hotel-ai/hotel-inventory/internal/repository"
)

func mountLocationRoutes(r chi.Router, repo repository.LocationRepository) {
	r.Get("/locations/{cityCode}", getLocation(repo))
	r.Get("/locations", listLocationsByCounty(repo))
	r.Put("/locations/{cityCode}", upsertLocation(repo))
}

func getLocation(repo repository.LocationRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cityCode := chi.URLParam(r, "cityCode")
		loc, err := repo.GetByCityCode(r.Context(), cityCode)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, loc)
	}
}

func listLocationsByCounty(repo repository.LocationRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		countyCode := r.URL.Query().Get("county")
		if countyCode == "" {
			writeError(w, http.StatusBadRequest, "county query param required")
			return
		}
		locs, err := repo.ListByCounty(r.Context(), countyCode)
		if err != nil {
			mapDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, locs)
	}
}

func upsertLocation(repo repository.LocationRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cityCode := chi.URLParam(r, "cityCode")
		var body domain.Location
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		body.CityCode = cityCode
		if body.CityName == "" || body.CountyCode == "" || body.CountyName == "" {
			writeError(w, http.StatusBadRequest, "city_name, county_code, county_name are required")
			return
		}
		if err := repo.Upsert(r.Context(), body); err != nil {
			mapDomainError(w, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}
