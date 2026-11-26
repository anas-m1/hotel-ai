//go:build integration

package repository

import (
	"context"
	"errors"
	"os"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/stdlib"

	"github.com/hotel-ai/booking-ops/internal/domain"
	db "github.com/hotel-ai/booking-ops/internal/repository/db"
)

// TestAvailabilityDateBoundaries verifies the actual SQL bindings, not a mock.
// The caller supplies a disposable, migrated database; all records roll back.
func TestAvailabilityDateBoundaries(t *testing.T) {
	url := os.Getenv("HOTEL_AI_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("set HOTEL_AI_TEST_DATABASE_URL to a disposable migrated database")
	}
	cfg, err := pgx.ParseConfig(url)
	if err != nil {
		t.Fatal(err)
	}
	cfg.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol
	conn := stdlib.OpenDB(*cfg)
	defer conn.Close()
	ctx := context.Background()
	tx, err := conn.BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer tx.Rollback()
	queries := db.New(tx)
	guest, err := NewGuestRepository(queries).Upsert(ctx, domain.Guest{
		Email:     "availability-" + uuid.NewString() + "@example.com",
		FirstName: "Integration", LastName: "Test",
	})
	if err != nil {
		t.Fatal(err)
	}
	day := func(n int) time.Time { return time.Date(2027, 6, n, 0, 0, 0, 0, time.UTC) }
	repo := NewBookingRepository(queries)
	booking, err := repo.Create(ctx, domain.Booking{
		GuestID: guest.ID, HotelCode: "TEST", RoomID: uuid.New(),
		CheckInDate: day(10), CheckOutDate: day(15), TotalPrice: "500.00", Currency: "USD",
	})
	if err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		name    string
		in, out int
		want    int64
	}{
		{"same interval", 10, 15, 1},
		{"inside", 11, 14, 1},
		{"contains", 9, 16, 1},
		{"overlaps start", 9, 11, 1},
		{"overlaps end", 14, 16, 1},
		{"ends at check in", 8, 10, 0},
		{"starts at check out", 15, 17, 0},
		{"before", 1, 3, 0},
		{"after", 20, 22, 0},
	} {
		t.Run(test.name, func(t *testing.T) {
			count, err := repo.CheckAvailability(ctx, booking.RoomID, day(test.in), day(test.out))
			if err != nil {
				t.Fatal(err)
			}
			if count != test.want {
				t.Fatalf("overlap count = %d, want %d", count, test.want)
			}
		})
	}
	if _, err := tx.ExecContext(ctx, "SAVEPOINT overlap_check"); err != nil {
		t.Fatal(err)
	}
	_, err = repo.Create(ctx, domain.Booking{
		GuestID: guest.ID, HotelCode: "TEST", RoomID: booking.RoomID,
		CheckInDate: day(11), CheckOutDate: day(14), TotalPrice: "300.00", Currency: "USD",
	})
	var pgErr *pgconn.PgError
	if !errors.As(err, &pgErr) || pgErr.Code != "23P01" {
		t.Fatalf("expected PostgreSQL overlap constraint, got %T", err)
	}
	if _, err := tx.ExecContext(ctx, "ROLLBACK TO SAVEPOINT overlap_check"); err != nil {
		t.Fatal(err)
	}
	if _, err := repo.UpdateStatus(ctx, booking.ID, booking.Version, domain.StatusCancelled); err != nil {
		t.Fatal(err)
	}
	count, err := repo.CheckAvailability(ctx, booking.RoomID, day(10), day(15))
	if err != nil || count != 0 {
		t.Fatalf("cancelled booking should not block availability: count=%d error=%v", count, err)
	}
}
