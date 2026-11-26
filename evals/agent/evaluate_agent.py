#!/usr/bin/env python3
"""Run live agent scenarios and score tool selection, safety, answer terms, and latency."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from compare_runs import summarize
from fixtures import verify_catalog
from scoring import SCORER_VERSION, score_turn

HERE = Path(__file__).resolve().parent


def _get_json(url: str, timeout: float = 5) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.load(response)


def wait_until_ready(base_url: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if _get_json(f"{base_url.rstrip('/')}/healthz").get("status") == "ok":
                return
        except (HTTPError, URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f"Assistant did not become ready in {timeout}s: {last_error}")


def chat(base_url: str, message: str, session_id: str, *, traceparent=None) -> dict[str, Any]:
    # No automatic retry: a timed-out agent request may still have executed tools.
    body = json.dumps(
        {"message": message, "session_id": session_id, "user_id": "eval-user", "read_only": True}
    ).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/v1/chat",
        data=body,
        headers={
            "content-type": "application/json",
            **({"traceparent": traceparent} if traceparent else {}),
        },
        method="POST",
    )
    with urlopen(request, timeout=240) as response:
        return json.load(response)


def execute_turns(base_url, turns, session, *, traceparent=None):
    """Collect raw agent evidence. Dashboard experiments score it in Langfuse."""
    rows, seen_ids = [], set()
    for index, turn in enumerate(turns, 1):
        tick = time.perf_counter()
        error = None
        try:
            kwargs = {"traceparent": traceparent} if traceparent else {}
            response = chat(base_url, turn["message"], session, **kwargs)
        except (
            HTTPError,
            URLError,
            TimeoutError,
            ConnectionError,
            RuntimeError,
            json.JSONDecodeError,
        ) as exc:
            response = {"reply": "", "tool_trace": [], "interrupt": None}
            error = type(exc).__name__ + (f" HTTP {exc.code}" if isinstance(exc, HTTPError) else "")
        trace = []
        for item in response.get("tool_trace", []):
            call_id = item.get("call_id")
            if not call_id:
                raise ValueError("Tool trace lacks call IDs; deploy current assistant")
            if call_id not in seen_ids:
                trace.append(item)
                seen_ids.add(call_id)
        rows.append(
            {
                "turn": index,
                "message": turn["message"],
                "reply": response.get("reply", ""),
                "interrupt": response.get("interrupt"),
                "tool_trace": trace,
                "error": error,
                "latency_ms": round((time.perf_counter() - tick) * 1000, 2),
            }
        )
        if error or any(
            t.get("error_category") in {"operational", "tool_execution"} for t in trace
        ):
            break
    return rows


def evaluate(
    base_url: str,
    cases: list[dict[str, Any]],
    *,
    variant="unlabeled",
    repeats=1,
    fixture_label="unverified-local-data",
    expected_model=None,
    expected_source=None,
    fixture_sha256=None,
    suite_name="hotel-agent-quality-v2",
    progress=False,
    environment_label="unspecified",
) -> dict[str, Any]:
    wait_until_ready(base_url)
    runtime = _get_json(f"{base_url.rstrip('/')}/v1/eval-info")
    if not runtime.get("model") or not runtime.get("source_sha256"):
        raise ValueError("Deploy the assistant's eval identity endpoint before running comparisons")
    if expected_model and runtime["model"] != expected_model:
        raise ValueError("Served model does not match --expected-model; no eval requests were sent")
    if expected_source and runtime["source_sha256"] != expected_source:
        raise ValueError("Served workflow source differs from this checkout; rebuild the assistant")
    if not runtime.get("read_only_evals_supported"):
        raise ValueError(
            "Assistant does not support enforced read-only evals; rebuild before running"
        )
    run_id = uuid.uuid4().hex
    results = []
    repeated_cases = [(repeat, case) for repeat in range(1, repeats + 1) for case in cases]
    for index, (repeat, case) in enumerate(repeated_cases, 1):
        started = time.perf_counter()
        session = f"eval-{run_id}-{repeat}-{hashlib.sha256(case['id'].encode()).hexdigest()[:12]}"
        turns = case.get("turns", [case])
        rows = []
        for turn, raw in zip(turns, execute_turns(base_url, turns, session)):
            row = score_turn(turn, raw, raw["tool_trace"], raw["error"])
            row.update(
                turn=raw["turn"],
                message=raw["message"],
                expected_json=turn.get("expected_json"),
                latency_ms=raw["latency_ms"],
            )
            rows.append(row)
        operational = any(r["operational_error"] for r in rows)
        result = {
            "id": case["id"],
            "category": case.get("category", "smoke"),
            "repeat": repeat,
            "passed": len(rows) == len(turns) and all(r["passed"] for r in rows),
            "quality_pass": None if operational else all(r["passed"] for r in rows),
            "operational_error": operational,
            "tool_selection_pass": None
            if operational
            else all(r["tool_selection_pass"] for r in rows),
            "forbidden_tools_pass": (
                False
                if any(r["forbidden_tools_pass"] is False for r in rows)
                else None
                if operational
                else True
            ),
            "answer_terms_pass": None if operational else all(r["answer_terms_pass"] for r in rows),
            "facts_pass": None
            if operational or not any(r["facts_pass"] is not None for r in rows)
            else all(r["facts_pass"] is not False for r in rows),
            "format_pass": None if operational else all(r["format_pass"] for r in rows),
            "tools_used": [name for r in rows for name in r["tools_used"]],
            "session_id": session,
            "reply": rows[-1]["reply"],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": next((r["error"] for r in rows if r["error"]), None),
            "turns": rows,
        }
        results.append(result)
        if progress:
            label = (
                "OPERATIONAL FAILURE"
                if operational
                else "PASS"
                if result["passed"]
                else "QUALITY FAIL"
            )
            print(
                f"[{index}/{len(repeated_cases)}] {case['id']} repeat={repeat}: {label}", flush=True
            )

    count = len(results)
    passed_count = sum(result["passed"] for result in results)
    end_runtime = _get_json(f"{base_url.rstrip('/')}/v1/eval-info")
    return {
        "variant": variant,
        "run_id": run_id,
        "repeats": repeats,
        "fixture_label": fixture_label,
        "scorer_version": SCORER_VERSION,
        "evaluator_sha256": hashlib.sha256(
            b"".join(
                (HERE / name).read_bytes()
                for name in ["evaluate_agent.py", "scoring.py", "fixtures.py", "compare_runs.py"]
            )
        ).hexdigest(),
        "fixture_verified": fixture_sha256 is not None,
        "fixture_sha256": fixture_sha256,
        "environment_label": environment_label,
        "eval_mode": "enforced-read-only",
        "dataset_sha256": hashlib.sha256(
            json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "runtime": runtime,
        "configuration_stable": runtime == end_runtime,
        "metrics": summarize(results),
        "suite": suite_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url.rstrip("/"),
        "case_count": count,
        "passed_count": passed_count,
        "pass_rate": round(passed_count / count, 4) if count else 0.0,
        "all_cases_passed": count > 0 and passed_count == count,
        "limitations": [
            "The small seeded smoke dataset is not representative of production use.",
            "Structured JSON checks verify requested facts, not every natural-language claim.",
            "CPU inference latency is local to this machine; "
            "do not compare it directly with cloud GPU serving.",
        ],
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8092")
    parser.add_argument("--cases", type=Path, default=HERE / "agent_cases.json")
    parser.add_argument("--output", type=Path, default=Path("/tmp/hotel-agent-eval.json"))
    parser.add_argument(
        "--variant", default="unlabeled", help="Name of this model/workflow variant"
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--fixture-label", default="unverified-local-data")
    parser.add_argument(
        "--expected-model", help="Verify the model actually served before evaluation"
    )
    parser.add_argument(
        "--allow-different-source",
        action="store_true",
        help="Evaluate remote source intentionally different from this checkout",
    )
    parser.add_argument("--inventory-url", default="http://localhost:8080")
    parser.add_argument("--environment-label", default="unspecified")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    parsed = urlsplit(args.base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        parser.error("Use an HTTP(S) base URL without credentials")
    suite = json.loads(args.cases.read_text(encoding="utf-8"))
    ids = [case["id"] for case in suite["cases"]]
    if not ids or len(set(ids)) != len(ids):
        parser.error("Cases must have unique IDs and the suite must not be empty")
    fixture_sha256 = None
    if suite.get("fixture"):
        parsed_inventory = urlsplit(args.inventory_url)
        if (
            parsed_inventory.scheme not in {"http", "https"}
            or parsed_inventory.username
            or parsed_inventory.password
        ):
            parser.error("Use an HTTP(S) inventory URL without credentials")
        fixture = json.loads((args.cases.parent / suite["fixture"]).read_text())
        try:
            fixture_sha256 = verify_catalog(args.inventory_url, fixture, _get_json)
        except (ValueError, HTTPError, URLError, KeyError, TypeError) as exc:
            parser.error("Catalog preflight failed: " + type(exc).__name__)
    expected_source = None
    if not args.allow_different_source:
        source = HERE.parents[1] / "ai/booking-assistant/src"
        digest = hashlib.sha256()
        for path in sorted(source.rglob("*.py")):
            digest.update(path.relative_to(source).as_posix().encode())
            digest.update(path.read_bytes())
        expected_source = digest.hexdigest()
    try:
        report = evaluate(
            args.base_url,
            suite["cases"],
            variant=args.variant,
            repeats=args.repeats,
            fixture_label=args.fixture_label,
            expected_model=args.expected_model,
            expected_source=expected_source,
            fixture_sha256=fixture_sha256,
            suite_name=suite["suite"],
            progress=True,
            environment_label=args.environment_label,
        )
    except ValueError as exc:
        parser.error(str(exc))
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=HERE, capture_output=True, text=True
    )
    report["checkout"] = {
        "commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "dirty": bool(dirty.stdout) if dirty.returncode == 0 else None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary_keys = ("suite", "case_count", "passed_count", "pass_rate", "all_cases_passed")
    print(json.dumps({key: report[key] for key in summary_keys}, indent=2))
    if not report["all_cases_passed"] or not report["configuration_stable"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
