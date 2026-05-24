package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/hotel-ai/booking-ops/internal/handler"
	"github.com/hotel-ai/booking-ops/internal/repository"
	db "github.com/hotel-ai/booking-ops/internal/repository/db"
)

func main() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		log.Fatal("DATABASE_URL not set")
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8081"
	}

	ctx := context.Background()

	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		log.Fatalf("pgxpool.ParseConfig: %v", err)
	}
	cfg.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol //numeric is passed over wire as string: both to and fro the server-db. db repsonsibel for converting from string to numberic instead of complex logic on applctn side. little latency addition at the cost of simplicity. later, can be changed to normal.

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		log.Fatalf("pgxpool.NewWithConfig: %v", err)
	}
	defer pool.Close()

	if err := pool.Ping(ctx); err != nil {
		log.Fatalf("db ping: %v", err)
	}

	queries := db.New(pool)
	guests := repository.NewGuestRepository(queries)
	bookings := repository.NewBookingRepository(queries)
	events := repository.NewBookingEventRepository(queries)

	router := handler.NewRouter(guests, bookings, events)

	addr := fmt.Sprintf(":%s", port)
	log.Printf("booking-ops listening on %s", addr)
	if err := http.ListenAndServe(addr, router); err != nil {
		log.Fatalf("ListenAndServe: %v", err)
	}
}
