package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/hotel-ai/hotel-inventory/internal/handler"
	"github.com/hotel-ai/hotel-inventory/internal/repository"
	db "github.com/hotel-ai/hotel-inventory/internal/repository/db"
)

func main() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		log.Fatal("DATABASE_URL not set")
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	ctx := context.Background()

	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		log.Fatalf("pgxpool.ParseConfig: %v", err)
	}
	// Use simple protocol so NUMERIC columns are sent/received as text,
	// which maps cleanly to Go string without pgtype.Numeric wrappers.
	cfg.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		log.Fatalf("pgxpool.NewWithConfig: %v", err)
	}
	defer pool.Close()

	if err := pool.Ping(ctx); err != nil {
		log.Fatalf("db ping: %v", err)
	}

	queries := db.New(pool)
	hotels := repository.NewHotelRepository(queries)
	rooms := repository.NewRoomRepository(queries)
	locations := repository.NewLocationRepository(queries)

	router := handler.NewRouter(hotels, rooms, locations)

	addr := fmt.Sprintf(":%s", port)
	log.Printf("hotel-inventory listening on %s", addr)
	if err := http.ListenAndServe(addr, router); err != nil {
		log.Fatalf("ListenAndServe: %v", err)
	}
}
