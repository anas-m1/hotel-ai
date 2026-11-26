#!/usr/bin/env python3
"""Build the Go APIs and run their HTTP contract test against temporary PostgreSQL.

Requires Go, uv and PostgreSQL 16 binaries (including btree_gist) on the host.
Does not use or modify the normal Compose databases or running application.
"""

import argparse
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} exited {result.returncode}")
    return result


def wait_ready(url, process):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Test API exited before becoming healthy")
        try:
            with urllib.request.urlopen(url + "/healthz", timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError("Test API health check timed out")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, default=Path("/usr/lib/postgresql/16/bin"))
    args = parser.parse_args()
    for name in ["initdb", "pg_ctl", "psql", "createdb"]:
        if not (args.pg_bin / name).is_file():
            parser.error(f"Missing PostgreSQL binary: {args.pg_bin / name}")
    if not shutil.which("uv") or not shutil.which("go"):
        parser.error("Go and uv must be installed")
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    (cache / "tmp").mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "GOTOOLCHAIN": "go1.23.12",
            "GOCACHE": str(cache / "go-build"),
            "GOPATH": str(cache / "gopath"),
            "GOTMPDIR": str(cache / "tmp"),
            "UV_CACHE_DIR": str(cache / "uv"),
            "UV_PYTHON_INSTALL_DIR": str(cache / "python"),
            "UV_PROJECT_ENVIRONMENT": str(cache / "venvs/booking-assistant"),
        }
    )
    with tempfile.TemporaryDirectory(prefix="backend-check-", dir=cache) as temp:
        temp = Path(temp)
        processes = []
        logs = []
        database_started = False
        data = temp / "postgres"
        try:
            binaries = {}
            for service in ["hotel-inventory", "booking-ops"]:
                binary = temp / service
                run(
                    ["go", "build", "-o", str(binary), f"./services/{service}/cmd/server"],
                    cwd=ROOT,
                    env=env,
                )
                binaries[service] = binary
            run(
                [
                    str(args.pg_bin / "initdb"),
                    "-D",
                    str(data),
                    "--username=hotel_ai_test",
                    "--auth=trust",
                    "--encoding=UTF8",
                    "--no-locale",
                ],
                env=env,
            )
            db_port = free_port()
            options = (
                f"-h 127.0.0.1 -p {db_port} -c unix_socket_directories='' "
                "-c shared_buffers=32MB -c max_connections=20 -c fsync=off"
            )
            run(
                [
                    str(args.pg_bin / "pg_ctl"),
                    "-D",
                    str(data),
                    "-l",
                    str(temp / "postgres.log"),
                    "-o",
                    options,
                    "-w",
                    "start",
                ],
                env=env,
            )
            database_started = True
            connection = ["-h", "127.0.0.1", "-p", str(db_port), "-U", "hotel_ai_test"]
            for database, service in [
                ("hotel_inventory", "hotel-inventory"),
                ("booking_ops", "booking-ops"),
            ]:
                run([str(args.pg_bin / "createdb"), *connection, database], env=env)
                migrations = sorted(
                    (ROOT / "services" / service / "db/migrations").glob("*.up.sql")
                )
                for migration in migrations:
                    run(
                        [
                            str(args.pg_bin / "psql"),
                            *connection,
                            "-d",
                            database,
                            "-v",
                            "ON_ERROR_STOP=1",
                            "-f",
                            str(migration),
                        ],
                        env=env,
                    )
            run(
                [
                    str(args.pg_bin / "psql"),
                    *connection,
                    "-d",
                    "hotel_inventory",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-f",
                    str(ROOT / "infra/docker/seed.sql"),
                ],
                env=env,
            )
            env["HOTEL_AI_TEST_DATABASE_URL"] = (
                f"postgres://hotel_ai_test@127.0.0.1:{db_port}/booking_ops?sslmode=disable"
            )
            print("Running package-local Go database integration tests.", flush=True)
            result = subprocess.run(
                [
                    "go",
                    "test",
                    "-tags=integration",
                    "./services/booking-ops/internal/repository",
                    "-v",
                ],
                cwd=ROOT,
                env=env,
            )
            if result.returncode:
                raise SystemExit(result.returncode)
            ports = {name: free_port() for name in binaries}
            for service, binary in binaries.items():
                database = "hotel_inventory" if service == "hotel-inventory" else "booking_ops"
                process_env = dict(env)
                process_env.update(
                    {
                        "PORT": str(ports[service]),
                        "DATABASE_URL": f"postgres://hotel_ai_test@127.0.0.1:{db_port}/{database}?sslmode=disable",
                        "BOOKING_OPS_URL": f"http://127.0.0.1:{ports['booking-ops']}",
                    }
                )
                log = (temp / (service + ".log")).open("w")
                logs.append(log)
                processes.append(
                    subprocess.Popen(
                        [str(binary)], cwd=ROOT, env=process_env, stdout=log, stderr=log
                    )
                )
            for service, process in zip(binaries, processes):
                wait_ready(f"http://127.0.0.1:{ports[service]}", process)
            env.update(
                {
                    "HOTEL_AI_E2E": "1",
                    "HOTEL_INVENTORY_URL": f"http://127.0.0.1:{ports['hotel-inventory']}",
                    "BOOKING_OPS_URL": f"http://127.0.0.1:{ports['booking-ops']}",
                }
            )
            print("Running backend contract test against temporary databases.", flush=True)
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "--locked",
                    "--project",
                    "ai/booking-assistant",
                    "pytest",
                    "tests/e2e/",
                    "-v",
                ],
                cwd=ROOT,
                env=env,
            )
            if result.returncode:
                raise SystemExit(result.returncode)
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for log in logs:
                log.close()
            if database_started:
                # Only stop this script's temporary cluster, never a system service.
                run(
                    [str(args.pg_bin / "pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop"],
                    env=env,
                )
    print("Temporary APIs and PostgreSQL stopped; temporary data removed.")


if __name__ == "__main__":
    main()
