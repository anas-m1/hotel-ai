#!/bin/bash
# Creates additional databases beyond the default POSTGRES_DB.
# Runs automatically on first container start via docker-entrypoint-initdb.d.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE booking_ops;
    GRANT ALL PRIVILEGES ON DATABASE booking_ops TO $POSTGRES_USER;
EOSQL
