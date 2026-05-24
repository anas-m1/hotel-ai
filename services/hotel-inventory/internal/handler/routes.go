package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	"github.com/hotel-ai/hotel-inventory/internal/config"
	"github.com/hotel-ai/hotel-inventory/internal/domain"
	"github.com/hotel-ai/hotel-inventory/internal/repository"
)

func NewRouter(cfg config.Config, hotels repository.HotelRepository, rooms repository.RoomRepository, locations repository.LocationRepository) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	r.Get("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	r.Route("/v1", func(r chi.Router) {
		mountLocationRoutes(r, locations)
		mountHotelRoutes(r, hotels, cfg)
		mountRoomRoutes(r, rooms)
	})

	return r
}

// --- shared response helpers ---

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

func mapDomainError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, domain.ErrNotFound):
		writeError(w, http.StatusNotFound, err.Error())
	case errors.Is(err, domain.ErrConflict):
		writeError(w, http.StatusConflict, err.Error())
	default:
		writeError(w, http.StatusInternalServerError, "internal error")
	}
}

func par sePagination(r *http.Request, cfg config.Config) (limit, offset int32) {
	limit = cfg.PaginationDefault
	offset = 0
	if v, err := strconv.Atoi(r.URL.Query().Get("limit")); err == nil && v > 0 && int32(v) <= cfg.PaginationMax {
		limit = int32(v)
	}
	if v, err := strconv.Atoi(r.URL.Query().Get("offset")); err == nil && v >= 0 {
		offset = int32(v)
	}
	return
}
