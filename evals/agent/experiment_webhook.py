"""Authenticated dashboard trigger with a durable, single-worker local job queue."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from langfuse_experiment import SUITES, digest_json, run_job

DATA = Path(os.environ.get("EVAL_DATA_DIR", "/data"))
MAX_BODY = 32 * 1024


def connection():
    db = sqlite3.connect(DATA / "jobs.sqlite", timeout=10)
    db.row_factory = sqlite3.Row
    return db


def normalize(body):
    if body.get("datasetName") not in SUITES:
        raise ValueError("Dataset is not allowlisted")
    if body.get("projectId") != os.environ["EVAL_PROJECT_ID"]:
        raise ValueError("Project mismatch")
    if not isinstance(body.get("datasetId"), str) or not body["datasetId"]:
        raise ValueError("Missing dataset ID")
    config = body.get("payload", {})
    if isinstance(config, str):
        config = json.loads(config)
    if not isinstance(config, dict) or set(config) - {
        "run_name",
        "variant",
        "expected_model",
        "dataset_version",
        "case_ids",
        "repeats",
    }:
        raise ValueError("Unsupported experiment config")
    for field in ["run_name", "variant", "expected_model"]:
        if not isinstance(config.get(field), str) or not re.fullmatch(
            r"[A-Za-z0-9_./:@+-]{1,180}", config[field]
        ):
            raise ValueError("Invalid required experiment label")
    repeats = config.get("repeats", 1)
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError("repeats must be 1..3")
    cases = config.get("case_ids")
    if cases is not None and (
        not isinstance(cases, list)
        or not cases
        or len(cases) > 25
        or any(not isinstance(c, str) for c in cases)
        or len(set(cases)) != len(cases)
    ):
        raise ValueError("Invalid case_ids")
    version = config.get("dataset_version")
    if version:
        parsed = datetime.fromisoformat(version.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed > datetime.now(UTC):
            raise ValueError("dataset_version must be a past timezone-aware timestamp")
        version = parsed.isoformat()
    # Exclude server-assigned snapshot from dedup identity for retried deliveries.
    identity = digest_json(
        {"project": body["projectId"], "dataset": body["datasetId"], "config": config}
    )
    job_id = hashlib.sha256(
        (body["projectId"] + "/" + body["datasetId"] + "/" + config["run_name"]).encode()
    ).hexdigest()
    return {
        "id": job_id,
        "identity": identity,
        "projectId": body["projectId"],
        "datasetId": body["datasetId"],
        "datasetName": body["datasetName"],
        "config": {
            **config,
            "repeats": repeats,
            "dataset_version": version or datetime.now(UTC).isoformat(),
        },
    }


def worker(stop):
    while not stop.wait(1):
        with connection() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1"
            ).fetchone()
            if row is None:
                continue
            db.execute("UPDATE jobs SET status='running' WHERE id=?", (row["id"],))
        try:
            result = run_job(json.loads(row["request"]))
            status, error = "completed", None
        except Exception as exc:
            # Exception messages/SDK bodies can include request secrets. Persist type only.
            result, status, error = {}, "failed", type(exc).__name__
        with connection() as db:
            db.execute(
                "UPDATE jobs SET status=?, result=?, error=? WHERE id=?",
                (status, json.dumps(result), error, row["id"]),
            )


@asynccontextmanager
async def lifespan(app):
    if len(os.environ.get("EVAL_WEBHOOK_TOKEN", "")) < 32:
        raise RuntimeError("Configure a random webhook token of at least 32 characters")
    DATA.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, identity TEXT NOT NULL, "
            "request TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL, "
            "result TEXT, error TEXT)"
        )
        # Never replay a request whose agent/tool execution may already have happened.
        db.execute(
            "UPDATE jobs SET status='failed', error='InterruptedProcess' WHERE status='running'"
        )
    stop = threading.Event()
    thread = threading.Thread(target=worker, args=(stop,), daemon=True)
    thread.start()
    yield
    stop.set()
    thread.join(timeout=2)


app = FastAPI(lifespan=lifespan)


def authorize(request):
    expected = "Bearer " + os.environ["EVAL_WEBHOOK_TOKEN"]
    if not hmac.compare_digest(request.headers.get("authorization", ""), expected):
        raise HTTPException(401, "Invalid webhook authentication")


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.post("/experiments", status_code=202)
async def trigger(request: Request):
    authorize(request)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BODY:
            raise HTTPException(413, "Request too large")
    try:
        job = normalize(json.loads(data))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(422, "Invalid experiment config") from None
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT identity, status FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if old:
            if old["identity"] != job["identity"]:
                raise HTTPException(409, "Run name already used for a different config")
            return {"job_id": job["id"], "status": old["status"], "duplicate": True}
        if (
            db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[
                0
            ]
            >= 2
        ):
            raise HTTPException(409, "Experiment queue is full")
        db.execute(
            "INSERT INTO jobs (id, identity, request, status, created) VALUES (?,?,?,?,?)",
            (job["id"], job["identity"], json.dumps(job), "queued", datetime.now(UTC).isoformat()),
        )
    return {"job_id": job["id"], "status": "queued"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str, request: Request):
    authorize(request)
    with connection() as db:
        row = db.execute(
            "SELECT id, status, error, result FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown job")
    return {
        "job_id": row["id"],
        "status": row["status"],
        "error": row["error"],
        "result": json.loads(row["result"]) if row["result"] else None,
    }
