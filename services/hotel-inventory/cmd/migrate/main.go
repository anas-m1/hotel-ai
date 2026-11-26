package main

import (
	"log"
	"os"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/source/file"
)

func main() {
	direction := "up"
	if len(os.Args) > 1 {
		direction = os.Args[1]
	}

	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		log.Fatal("DATABASE_URL not set")
	}

	m, err := migrate.New("file://db/migrations", dsn)
	if err != nil {
		log.Fatalf("migrate.New: %v", err)
	}
	defer m.Close()

	switch direction {
	case "up":
		err = m.Up()
	case "down":
		err = m.Down()
	default:
		log.Fatalf("unknown direction %q — use up or down", direction)
	}

	if err != nil && err != migrate.ErrNoChange {
		log.Fatalf("migration %s: %v", direction, err)
	}
	log.Printf("migration %s: done", direction)
}
