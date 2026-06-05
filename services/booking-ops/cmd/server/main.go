package main

import (
	"context"
	"fmt"
	"log"
	"net/http"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jackc/pgx/v5/stdlib"

	"github.com/hotel-ai/booking-ops/internal/config"
	"github.com/hotel-ai/booking-ops/internal/handler"
	"github.com/hotel-ai/booking-ops/internal/repository"
	db "github.com/hotel-ai/booking-ops/internal/repository/db"
)

func main() {
	cfg := config.Load()

	ctx := context.Background()

	poolCfg, err := pgxpool.ParseConfig(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("pgxpool.ParseConfig: %v", err)
	}
	// Use simple protocol so NUMERIC columns are sent/received as text,
	// which maps cleanly to Go string without pgtype.Numeric wrappers.

	//numeric is passed over wire as string: both to and fro the server-db. db repsonsibel for converting from string to numberic instead of complex logic on applctn side. little latency addition at the cost of simplicity. later, can be changed to normal.
	poolCfg.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol
	

	pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
	if err != nil {
		log.Fatalf("pgxpool.NewWithConfig: %v", err)
	}
	defer pool.Close()

	if err := pool.Ping(ctx); err != nil {
		log.Fatalf("db ping: %v", err)
	}

	sqlDB := stdlib.OpenDBFromPool(pool)
	defer sqlDB.Close()

	queries := db.New(sqlDB)
	guests := repository.NewGuestRepository(queries)
	bookings := repository.NewBookingRepository(queries)
	events := repository.NewBookingEventRepository(queries)

	router := handler.NewRouter(cfg, guests, bookings, events)

	addr := fmt.Sprintf(":%s", cfg.Port)
	log.Printf("booking-ops listening on %s", addr)
	if err := http.ListenAndServe(addr, router); err != nil {
		log.Fatalf("ListenAndServe: %v", err)
	}
}
