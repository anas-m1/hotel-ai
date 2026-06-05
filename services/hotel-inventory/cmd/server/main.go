package main

import (
	"context"
	"fmt"
	"log"
	"net/http"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jackc/pgx/v5/stdlib"

	"github.com/hotel-ai/hotel-inventory/internal/config"
	"github.com/hotel-ai/hotel-inventory/internal/handler"
	"github.com/hotel-ai/hotel-inventory/internal/repository"
	db "github.com/hotel-ai/hotel-inventory/internal/repository/db"
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
	hotels := repository.NewHotelRepository(queries)
	rooms := repository.NewRoomRepository(queries)
	locations := repository.NewLocationRepository(queries)

	router := handler.NewRouter(cfg, hotels, rooms, locations)

	addr := fmt.Sprintf(":%s", cfg.Port)
	log.Printf("hotel-inventory listening on %s", addr)
	if err := http.ListenAndServe(addr, router); err != nil {
		log.Fatalf("ListenAndServe: %v", err)
	}
}
