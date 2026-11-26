#!/usr/bin/env python3
"""Evaluate hotel retrieval against a small, versioned expected-result set."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent


def search(base_url: str, query: str, city_code: str, limit: int) -> list[dict[str, Any]]:
    body = json.dumps({"query": query, "city_code": city_code, "limit": limit}).encode()
    request = Request(
        f"{base_url.rstrip('/')}/v1/search/hotels",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)["results"]


def evaluate(base_url: str, cases: list[dict[str, Any]], k: int) -> dict[str, Any]:
    results = []
    for case in cases:
        started = time.perf_counter()
        error = None
        try:
            found = search(base_url, case["query"], case["city_code"], k)
        except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
            found = []
            error = f"{type(exc).__name__}: {exc}"
        codes = [hotel["hotel_code"] for hotel in found[:k] if "hotel_code" in hotel]
        expected = set(case["expected_hotel_codes"])
        reciprocal_rank = next(
            (1 / rank for rank, code in enumerate(codes, 1) if code in expected), 0.0
        )
        recall = len(set(codes) & expected) / len(expected) if expected else 0.0
        results.append(
            {
                "id": case["id"],
                "expected_hotel_codes": sorted(expected),
                "retrieved_hotel_codes": codes,
                "recall_at_k": round(recall, 4),
                "reciprocal_rank": round(reciprocal_rank, 4),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": error,
            }
        )
    count = len(results)
    return {
        "suite": "hotel-retrieval-smoke-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url.rstrip("/"),
        "k": k,
        "case_count": count,
        "recall_at_k": round(sum(r["recall_at_k"] for r in results) / count, 4) if count else 0.0,
        "mean_reciprocal_rank": round(sum(r["reciprocal_rank"] for r in results) / count, 4)
        if count
        else 0.0,
        "all_cases_retrieved": count > 0 and all(r["reciprocal_rank"] > 0 for r in results),
        "limitations": [
            "Three seeded hotels and one expected result per query; "
            "this is a smoke baseline, not a quality claim."
        ],
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8091")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--cases", type=Path, default=HERE / "retrieval_cases.json")
    parser.add_argument("--output", type=Path, default=Path("/tmp/hotel-retrieval-eval.json"))
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k must be at least 1")
    suite = json.loads(args.cases.read_text(encoding="utf-8"))
    report = evaluate(args.base_url, suite["cases"], args.k)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "suite",
                    "case_count",
                    "recall_at_k",
                    "mean_reciprocal_rank",
                    "all_cases_retrieved",
                )
            },
            indent=2,
        )
    )
    if not report["all_cases_retrieved"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
