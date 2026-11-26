.PHONY: generate build test lint migrate-up migrate-down

generate:
	sqlc generate

build:
	go build ./...

test:
	go test ./...

lint:
	golangci-lint run

migrate-up:
	go run cmd/migrate/main.go up

migrate-down:
	go run cmd/migrate/main.go down
