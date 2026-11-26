#!/usr/bin/env python3
"""Export generated answers for human review without inventing human scores."""

import argparse
import csv
import json
from pathlib import Path

FIELDS = [
    "variant",
    "case_id",
    "repeat",
    "turn",
    "prompt",
    "expected_json",
    "reply",
    "operational_failure",
    "automated_quality_pass",
    "automated_format_pass",
    "automated_facts_pass",
    "fact_errors",
    "correctness_0_2",
    "grounding_0_2",
    "usefulness_0_2",
    "safety_0_2",
    "reviewer",
    "notes",
]


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def review_rows(report):
    for case in report["cases"]:
        for turn in case["turns"]:
            row = dict.fromkeys(FIELDS, "")
            row.update(
                variant=report["variant"],
                case_id=case["id"],
                repeat=case["repeat"],
                turn=turn["turn"],
                prompt=turn["message"],
                reply=turn["reply"],
                expected_json=json.dumps(turn.get("expected_json")),
                operational_failure=turn["operational_error"],
                automated_quality_pass=turn["quality_pass"],
                automated_format_pass=turn["format_pass"],
                automated_facts_pass=turn["facts_pass"],
                fact_errors="; ".join(turn["fact_errors"]),
            )
            yield {key: safe_cell(value) for key, value in row.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new file to preserve human annotations")
    report = json.loads(args.report.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(review_rows(report))
    print("Review template saved; human scores are blank.")


if __name__ == "__main__":
    main()
