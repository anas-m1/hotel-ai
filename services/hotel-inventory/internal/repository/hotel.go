package repository

import (
	"context"
	"errors"
	"strconv"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/hotel-ai/hotel-inventory/internal/domain"
	db "github.com/hotel-ai/hotel-inventory/internal/repository/db"
)

type HotelRepository interface {
	GetByCode(ctx context.Context, hotelCode string) (domain.Hotel, error)
	ListByCity(ctx context.Context, cityCode string, limit, offset int32) ([]domain.Hotel, error)
	ListByRating(ctx context.Context, rating domain.HotelRating, limit, offset int32) ([]domain.Hotel, error)
	Search(ctx context.Context, query string, limit, offset int32) ([]domain.Hotel, error)
	Upsert(ctx context.Context, h domain.Hotel) error
	Count(ctx context.Context) (int64, error)
	CountByCity(ctx context.Context, cityCode string) (int64, error)
}

type RoomRepository interface {
	GetByID(ctx context.Context, id uuid.UUID) (domain.Room, error)
	ListByHotel(ctx context.Context, hotelCode string) ([]domain.Room, error)
	ListActiveByHotel(ctx context.Context, hotelCode string) ([]domain.Room, error)
	ListByType(ctx context.Context, hotelCode string, roomType domain.RoomType) ([]domain.Room, error)
	Create(ctx context.Context, r domain.Room) (domain.Room, error)
	Update(ctx context.Context, r domain.Room) (domain.Room, error)
	Deactivate(ctx context.Context, id uuid.UUID) error
	CountActive(ctx context.Context, hotelCode string) (int64, error)
}

// --- Hotel ---

type postgresHotelRepo struct{ q *db.Queries }

func NewHotelRepository(q *db.Queries) HotelRepository { return &postgresHotelRepo{q: q} }

func (r *postgresHotelRepo) GetByCode(ctx context.Context, hotelCode string) (domain.Hotel, error) {
	row, err := r.q.GetHotelByCode(ctx, hotelCode)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return domain.Hotel{}, domain.ErrNotFound
		}
		return domain.Hotel{}, err
	}
	return hotelFromDB(row), nil
}

func (r *postgresHotelRepo) ListByCity(ctx context.Context, cityCode string, limit, offset int32) ([]domain.Hotel, error) {
	rows, err := r.q.ListHotelsByCity(ctx, db.ListHotelsByCityParams{
		CityCode: cityCode,
		Limit:    limit,
		Offset:   offset,
	})
	if err != nil {
		return nil, err
	}
	return hotelsFromDB(rows), nil
}

func (r *postgresHotelRepo) ListByRating(ctx context.Context, rating domain.HotelRating, limit, offset int32) ([]domain.Hotel, error) {
	rows, err := r.q.ListHotelsByRating(ctx, db.ListHotelsByRatingParams{
		Rating: db.HotelRating(rating),
		Limit:  limit,
		Offset: offset,
	})
	if err != nil {
		return nil, err
	}
	return hotelsFromDB(rows), nil
}

func (r *postgresHotelRepo) Search(ctx context.Context, query string, limit, offset int32) ([]domain.Hotel, error) {
	rows, err := r.q.SearchHotelsFTS(ctx, db.SearchHotelsFTSParams{
		PlaintoTsquery: query,
		Limit:          limit,
		Offset:         offset,
	})
	if err != nil {
		return nil, err
	}
	return hotelsFromDB(rows), nil
}

func (r *postgresHotelRepo) Upsert(ctx context.Context, h domain.Hotel) error {
	return r.q.UpsertHotel(ctx, db.UpsertHotelParams{
		HotelCode:   h.HotelCode,
		Name:        h.Name,
		Rating:      db.HotelRating(h.Rating),
		Address:     strToPtr(h.Address),
		PinCode:     strToPtr(h.PinCode),
		Lat:         float64PtrToStrPtr(h.Lat),
		Lng:         float64PtrToStrPtr(h.Lng),
		Phone:       strToPtr(h.Phone),
		Fax:         strToPtr(h.Fax),
		WebsiteUrl:  strToPtr(h.WebsiteURL),
		Facilities:  strToPtr(h.Facilities),
		Description: strToPtr(h.Description),
		Attractions: strToPtr(h.Attractions),
		CityCode:    h.CityCode,
	})
}

func (r *postgresHotelRepo) Count(ctx context.Context) (int64, error) {
	return r.q.CountHotels(ctx)
}

func (r *postgresHotelRepo) CountByCity(ctx context.Context, cityCode string) (int64, error) {
	return r.q.CountHotelsByCity(ctx, cityCode)
}

// --- Room ---

type postgresRoomRepo struct{ q *db.Queries }

func NewRoomRepository(q *db.Queries) RoomRepository { return &postgresRoomRepo{q: q} }

func (r *postgresRoomRepo) GetByID(ctx context.Context, id uuid.UUID) (domain.Room, error) {
	row, err := r.q.GetRoomByID(ctx, id)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return domain.Room{}, domain.ErrNotFound
		}
		return domain.Room{}, err
	}
	return roomFromDB(row), nil
}

func (r *postgresRoomRepo) ListByHotel(ctx context.Context, hotelCode string) ([]domain.Room, error) {
	rows, err := r.q.ListRoomsByHotel(ctx, hotelCode)
	if err != nil {
		return nil, err
	}
	return roomsFromDB(rows), nil
}

func (r *postgresRoomRepo) ListActiveByHotel(ctx context.Context, hotelCode string) ([]domain.Room, error) {
	rows, err := r.q.ListActiveRoomsByHotel(ctx, hotelCode)
	if err != nil {
		return nil, err
	}
	return roomsFromDB(rows), nil
}

func (r *postgresRoomRepo) ListByType(ctx context.Context, hotelCode string, roomType domain.RoomType) ([]domain.Room, error) {
	rows, err := r.q.ListRoomsByType(ctx, db.ListRoomsByTypeParams{
		HotelCode: hotelCode,
		RoomType:  db.RoomType(roomType),
	})
	if err != nil {
		return nil, err
	}
	return roomsFromDB(rows), nil
}

func (r *postgresRoomRepo) Create(ctx context.Context, room domain.Room) (domain.Room, error) {
	row, err := r.q.CreateRoom(ctx, db.CreateRoomParams{
		HotelCode:  room.HotelCode,
		RoomNumber: room.RoomNumber,
		RoomType:   db.RoomType(room.RoomType),
		Capacity:   room.Capacity,
		BasePrice:  room.BasePrice,
		Currency:   room.Currency,
		Amenities:  room.Amenities,
	})
	if err != nil {
		return domain.Room{}, err
	}
	return roomFromDB(row), nil
}

func (r *postgresRoomRepo) Update(ctx context.Context, room domain.Room) (domain.Room, error) {
	row, err := r.q.UpdateRoom(ctx, db.UpdateRoomParams{
		ID:        room.ID,
		RoomType:  db.RoomType(room.RoomType),
		Capacity:  room.Capacity,
		BasePrice: room.BasePrice,
		Currency:  room.Currency,
		Amenities: room.Amenities,
	})
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return domain.Room{}, domain.ErrNotFound
		}
		return domain.Room{}, err
	}
	return roomFromDB(row), nil
}

func (r *postgresRoomRepo) Deactivate(ctx context.Context, id uuid.UUID) error {
	return r.q.DeactivateRoom(ctx, id)
}

func (r *postgresRoomRepo) CountActive(ctx context.Context, hotelCode string) (int64, error) {
	return r.q.CountActiveRoomsByHotel(ctx, hotelCode)
}

// --- mapping: db → domain ---

func hotelFromDB(row db.Hotel) domain.Hotel {
	return domain.Hotel{
		HotelCode:   row.HotelCode,
		Name:        row.Name,
		Rating:      domain.HotelRating(row.Rating),
		Address:     ptrToStr(row.Address),
		PinCode:     ptrToStr(row.PinCode),
		Lat:         strPtrToFloat64Ptr(row.Lat),
		Lng:         strPtrToFloat64Ptr(row.Lng),
		Phone:       ptrToStr(row.Phone),
		Fax:         ptrToStr(row.Fax),
		WebsiteURL:  ptrToStr(row.WebsiteUrl),
		Facilities:  ptrToStr(row.Facilities),
		Description: ptrToStr(row.Description),
		Attractions: ptrToStr(row.Attractions),
		CityCode:    row.CityCode,
		CreatedAt:   row.CreatedAt,
		UpdatedAt:   row.UpdatedAt,
	}
}

func hotelsFromDB(rows []db.Hotel) []domain.Hotel {
	out := make([]domain.Hotel, len(rows))
	for i, row := range rows {
		out[i] = hotelFromDB(row)
	}
	return out
}

func roomFromDB(row db.Room) domain.Room {
	return domain.Room{
		ID:         row.ID,
		HotelCode:  row.HotelCode,
		RoomNumber: row.RoomNumber,
		RoomType:   domain.RoomType(row.RoomType),
		Capacity:   row.Capacity,
		BasePrice:  row.BasePrice,
		Currency:   row.Currency,
		Amenities:  row.Amenities,
		IsActive:   row.IsActive,
		CreatedAt:  row.CreatedAt,
		UpdatedAt:  row.UpdatedAt,
	}
}

func roomsFromDB(rows []db.Room) []domain.Room {
	out := make([]domain.Room, len(rows))
	for i, row := range rows {
		out[i] = roomFromDB(row)
	}
	return out
}

// --- conversion helpers ---

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

func float64PtrToStrPtr(f *float64) *string {
	if f == nil {
		return nil
	}
	s := strconv.FormatFloat(*f, 'f', 6, 64)
	return &s
}

func strPtrToFloat64Ptr(s *string) *float64 {
	if s == nil {
		return nil
	}
	f, err := strconv.ParseFloat(*s, 64)
	if err != nil {
		return nil
	}
	return &f
}
