#!/usr/bin/env python3
"""Compare paired eval artifacts, rejecting incompatible datasets or scoring rules."""

import argparse
import json
import math
import statistics
from pathlib import Path


def summarize(cases):
    eligible = [c for c in cases if not c.get("operational_error", c.get("error") is not None)]
    latency = sorted(c["latency_ms"] for c in eligible)
    count = len(cases)
    quality_passed = sum(c.get("quality_pass", c["passed"]) is True for c in eligible)
    facts = [c for c in eligible if c.get("facts_pass") is not None]
    return {
        "case_count": count,
        "passed_count": sum(bool(c["passed"]) for c in cases),
        "pass_rate": sum(bool(c["passed"]) for c in cases) / count if count else 0,
        "operational_failure_count": count - len(eligible),
        "quality_eligible_count": len(eligible),
        "quality_pass_rate": quality_passed / len(eligible) if eligible else None,
        "fact_check_count": len(facts),
        "fact_pass_rate": sum(c["facts_pass"] for c in facts) / len(facts) if facts else None,
        "error_count": sum(c.get("error") is not None for c in cases),
        "forbidden_tool_failures": sum(c["forbidden_tools_pass"] is False for c in cases),
        "safety_unknown_count": sum(c["forbidden_tools_pass"] is None for c in cases),
        "latency_p50_ms": statistics.median(latency) if latency else None,
        "latency_p95_ms": latency[math.ceil(len(latency) * 0.95) - 1] if latency else None,
    }


def compare(baseline, candidate):
    for field in ["dataset_sha256", "scorer_version", "evaluator_sha256", "fixture_label"]:
        if not baseline.get(field) or baseline[field] != candidate.get(field):
            raise ValueError(f"Cannot compare different or missing {field}")
    if baseline.get("fixture_verified") != candidate.get("fixture_verified"):
        raise ValueError("Fixture verification status differs")
    if (
        baseline.get("fixture_verified")
        and baseline["fixture_sha256"] != candidate["fixture_sha256"]
    ):
        raise ValueError("Catalog fixture hashes differ")
    if not all(r.get("configuration_stable") for r in [baseline, candidate]):
        raise ValueError("Runtime configuration changed during an evaluation")

    def indexed(report):
        rows = report["cases"]
        mapped = {(c["id"], c["repeat"]): c for c in rows}
        if len(mapped) != len(rows):
            raise ValueError("Duplicate case/repeat identifiers")
        return mapped

    left, right = indexed(baseline), indexed(candidate)
    if not left or left.keys() != right.keys():
        raise ValueError("Both runs must contain the same cases and repeat count")
    improvements, regressions = [], []
    quality_improvements, quality_regressions, operational_transitions = [], [], []
    paired_quality = []
    for key in sorted(left):
        if left[key]["passed"] != right[key]["passed"]:
            target = improvements if right[key]["passed"] else regressions
            target.append({"id": key[0], "repeat": key[1]})
        a_quality, b_quality = left[key].get("quality_pass"), right[key].get("quality_pass")
        if a_quality is not None and b_quality is not None:
            paired_quality.append((a_quality, b_quality))
            if a_quality != b_quality:
                target = quality_improvements if b_quality else quality_regressions
                target.append({"id": key[0], "repeat": key[1]})
        elif left[key].get("operational_error") != right[key].get("operational_error"):
            operational_transitions.append(
                {
                    "id": key[0],
                    "repeat": key[1],
                    "baseline_failed_operationally": left[key].get("operational_error"),
                    "candidate_failed_operationally": right[key].get("operational_error"),
                }
            )
    a, b = summarize(list(left.values())), summarize(list(right.values()))
    return {
        "baseline": {"variant": baseline["variant"], "runtime": baseline["runtime"], **a},
        "candidate": {"variant": candidate["variant"], "runtime": candidate["runtime"], **b},
        "pass_rate_delta_percentage_points": round(100 * (b["pass_rate"] - a["pass_rate"]), 2),
        "improvements": improvements,
        "regressions": regressions,
        "quality_improvements": quality_improvements,
        "quality_regressions": quality_regressions,
        "operational_transitions": operational_transitions,
        "paired_quality_count": len(paired_quality),
        "paired_quality_delta_percentage_points": (
            round(100 * sum(int(b) - int(a) for a, b in paired_quality) / len(paired_quality), 2)
            if paired_quality
            else None
        ),
        "notes": [
            "Verified fixture hashes cover catalog facts, "
            "not vector-index state or all database tables.",
            "Operational failures are excluded from answer-quality rates and latency percentiles.",
            "A tiny suite does not establish statistical significance or production quality.",
            "Cost and token accounting are not captured by this runner; inspect provider traces.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = compare(
            json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text())
        )
    except ValueError as exc:
        parser.error(str(exc))
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
