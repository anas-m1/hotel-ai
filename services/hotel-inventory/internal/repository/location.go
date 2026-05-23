package repository

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"

	"github.com/hotel-ai/hotel-inventory/internal/domain"
	db "github.com/hotel-ai/hotel-inventory/internal/repository/db"
)

type LocationRepository interface {
	GetByCityCode(ctx context.Context, cityCode string) (domain.Location, error)
	ListByCounty(ctx context.Context, countyCode string) ([]domain.Location, error)
	Upsert(ctx context.Context, loc domain.Location) error
}

type postgresLocationRepo struct {
	q *db.Queries
}

func NewLocationRepository(q *db.Queries) LocationRepository {
	return &postgresLocationRepo{q: q}
}

func (r *postgresLocationRepo) GetByCityCode(ctx context.Context, cityCode string) (domain.Location, error) {
	row, err := r.q.GetLocationByCityCode(ctx, cityCode)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return domain.Location{}, domain.ErrNotFound
		}
		return domain.Location{}, err
	}
	return locationFromDB(row), nil
}

func (r *postgresLocationRepo) ListByCounty(ctx context.Context, countyCode string) ([]domain.Location, error) {
	rows, err := r.q.ListLocationsByCounty(ctx, countyCode)
	if err != nil {
		return nil, err
	}
	out := make([]domain.Location, len(rows))
	for i, row := range rows {
		out[i] = locationFromDB(row)
	}
	return out, nil
}

func (r *postgresLocationRepo) Upsert(ctx context.Context, loc domain.Location) error {
	return r.q.UpsertLocation(ctx, db.UpsertLocationParams{
		CityCode:   loc.CityCode,
		CityName:   loc.CityName,
		CountyCode: loc.CountyCode,
		CountyName: loc.CountyName,
	})
}

func locationFromDB(row db.Location) domain.Location {
	return domain.Location{
		CityCode:   row.CityCode,
		CityName:   row.CityName,
		CountyCode: row.CountyCode,
		CountyName: row.CountyName,
	}
}
