"""Full-agent experiment execution; deterministic scoring runs inside Langfuse."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime
from functools import lru_cache

from evaluate_agent import HERE, _get_json, execute_turns, wait_until_ready
from fixtures import verify_catalog
from import_langfuse import map_suite

ROOT = HERE.parents[1]
SUITES = {"hotel-agent-dev": "agent_cases.json", "hotel-agent-heldout": "heldout_cases.json"}
EVALUATOR = HERE / "evaluators/hotel_agent.ts"


def digest_json(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_hash():
    source = ROOT / "ai/booking-assistant/src"
    digest = hashlib.sha256()
    for path in sorted(source.rglob("*.py")):
        digest.update(path.relative_to(source).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=1)
def make_client():
    from langfuse import Langfuse

    return Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        base_url=os.environ.get("LANGFUSE_HOST", "http://langfuse-web:3000"),
        additional_headers={"x-langfuse-ingestion-version": "4"},
        timeout=60,
    )


def validate_dataset(dataset, name):
    """Use the pinned hosted items, but reject drift from the reviewed repo suite."""
    metadata, plan = map_suite(HERE / SUITES[name], name)
    planned = {i["id"]: i for i in plan}
    active = [i for i in dataset.items if str(i.status).upper().split(".")[-1] == "ACTIVE"]
    if set(planned) != {i.id for i in active}:
        raise ValueError("Hosted dataset item IDs differ from repository")
    for item in active:
        target = planned[item.id]
        if any(getattr(item, k) != target[k] for k in ["input", "expected_output", "metadata"]):
            raise ValueError("Hosted dataset content differs from repository")
    return metadata, sorted(active, key=lambda i: i.metadata["case_id"])


def run_job(job, *, client=None):
    client = client or make_client()
    config = job["config"]
    base = os.environ.get("ASSISTANT_URL", "http://booking-assistant:8092")
    inventory = os.environ.get("INVENTORY_URL", "http://hotel-inventory:8080")
    try:
        dataset = client.get_dataset(
            job["datasetName"], version=datetime.fromisoformat(config["dataset_version"])
        )
        if dataset.id != job["datasetId"] or dataset.project_id != job["projectId"]:
            raise ValueError("Dataset/project mismatch")
        suite_meta, items = validate_dataset(dataset, job["datasetName"])
        requested = config.get("case_ids")
        if requested:
            if not set(requested) <= {i.metadata["case_id"] for i in items}:
                raise ValueError("Unknown case IDs")
            items = [i for i in items if i.metadata["case_id"] in requested]
        fixture = json.loads((HERE / "catalog_fixture.json").read_text())
        fixture_hash = verify_catalog(inventory, fixture, _get_json)
        wait_until_ready(base)
        runtime = _get_json(base + "/v1/eval-info")
        if runtime.get("model") != config["expected_model"]:
            raise ValueError("Deployed model differs from expected_model")
        if runtime.get("source_sha256") != source_hash() or not runtime.get(
            "read_only_evals_supported"
        ):
            raise ValueError("Deploy matching assistant source with read-only eval support")
        source_sha = hashlib.sha256(EVALUATOR.read_bytes()).hexdigest()
        evaluator_name = "hotel-agent-deterministic-" + source_sha[:12]
        # Fail before model calls if setup has not published this exact evaluator.
        evaluators = client.api.evaluators.list(limit=100).data
        if not any(
            e.name == evaluator_name and getattr(e, "source_code", None) == EVALUATOR.read_text()
            for e in evaluators
        ):
            raise ValueError("Publish matching Langfuse code evaluator before running")
        metadata = {
            "variant": config["variant"],
            "runtime": json.dumps(runtime, sort_keys=True),
            "source_sha256": runtime["source_sha256"],
            "fixture_sha256": fixture_hash,
            "prompt_sha256": hashlib.sha256(
                (ROOT / "ai/booking-assistant/src/agent/prompts.py").read_bytes()
            ).hexdigest(),
            "dataset_sha256": suite_meta["source_sha256"],
            "evaluator_sha256": source_sha,
            "dataset_version": config["dataset_version"],
            "eval_mode": "enforced-read-only",
            "scope": "subset" if requested else "full",
            "case_ids": json.dumps(requested or []),
            "repeats": str(config["repeats"]),
            "job_id": job["id"],
        }
        manifests = []

        def task(*, item, **kwargs):
            if _get_json(base + "/v1/eval-info") != runtime:
                raise ValueError("Runtime changed during experiment")
            session = "eval-webhook-" + uuid.uuid4().hex
            from opentelemetry.trace import get_current_span

            span = get_current_span().get_span_context()
            parent = f"00-{span.trace_id:032x}-{span.span_id:016x}-01" if span.is_valid else None
            from langfuse import propagate_attributes

            client.update_current_span(
                name="hotel-agent-scenario",
                metadata={"session_id": session, "case_id": item.metadata["case_id"]},
            )
            started = time.perf_counter()
            with propagate_attributes(
                session_id=session, user_id="eval-user", tags=["hotel-agent-experiment"]
            ):
                turns = execute_turns(base, item.input["turns"], session, traceparent=parent)
            stable = _get_json(base + "/v1/eval-info") == runtime
            output = {
                "schema": "hotel-agent-evidence-v1",
                "turns": turns,
                "session_id": session,
                "operational_error": not stable,
                "configuration_stable": stable,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
            manifests.append(
                {
                    "case_id": item.metadata["case_id"],
                    "trace_id": client.get_current_trace_id(),
                    "session_id": session,
                    "output": output,
                }
            )
            return output

        urls = []
        for repeat in range(1, config["repeats"] + 1):
            run_name = config["run_name"] + (f"-r{repeat}" if config["repeats"] > 1 else "")
            result = client.run_experiment(
                name=job["datasetName"],
                run_name=run_name,
                data=items,
                task=task,
                max_concurrency=1,
                metadata={**metadata, "repeat": str(repeat)},
                _dataset_version=dataset.version,
            )
            if len(result.item_results) != len(items) or any(
                r.output is None for r in result.item_results
            ):
                raise RuntimeError("Experiment item execution failed; inspect linked traces")
            urls.append(result.experiment_url)
        client.flush()
        return {"experiments": urls, "metadata": metadata, "items": manifests}
    finally:
        # SDK resources are process-wide. Shutdown here would break later jobs.
        client.flush()
