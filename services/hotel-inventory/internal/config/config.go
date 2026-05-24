package config

import (
	"log"
	"os"
	"strconv"
)

type Config struct {
	DatabaseURL       string
	Port              string
	PaginationDefault int32
	PaginationMax     int32
}

func Load() Config {
	return Config{
		DatabaseURL:       mustEnv("DATABASE_URL"),
		Port:              getEnv("PORT", "8080"),
		PaginationDefault: int32(getEnvInt("PAGINATION_DEFAULT", 20)),
		PaginationMax:     int32(getEnvInt("PAGINATION_MAX", 100)),
	}
}

func mustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		log.Fatalf("required env var %s is not set", key)
	}
	return v
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			log.Fatalf("env var %s must be an integer, got %q", key, v)
		}
		return n
	}
	return fallback
}
