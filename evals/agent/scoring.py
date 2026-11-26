"""Deterministic answer checks: useful evidence, not a complete grounding judge."""

import json
import re
from decimal import Decimal, InvalidOperation

SCORER_VERSION = "structured-facts-and-turns-v2"


def json_differences(expected, actual, path="$"):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [path + ": expected object"]
        errors = [path + "." + key + ": missing" for key in expected.keys() - actual.keys()]
        errors += [path + "." + key + ": unexpected" for key in actual.keys() - expected.keys()]
        for key in expected.keys() & actual.keys():
            errors += json_differences(expected[key], actual[key], path + "." + key)
        return errors
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return [path + ": list length/type mismatch"]
        # Fact arrays represent sets (facilities/rooms), not ordered workflow steps.
        remaining = list(actual)
        for item in expected:
            match = next(
                (i for i, value in enumerate(remaining) if not json_differences(item, value, path)),
                None,
            )
            if match is None:
                return [path + ": list value mismatch"]
            remaining.pop(match)
        return []
    if isinstance(expected, bool) or expected is None:
        return (
            []
            if type(expected) is type(actual) and expected == actual
            else [path + ": value mismatch"]
        )
    if isinstance(expected, (int, float)):
        try:
            equal = not isinstance(actual, bool) and Decimal(str(actual)) == Decimal(str(expected))
        except InvalidOperation:
            equal = False
        return [] if equal else [path + ": numeric mismatch"]

    def normalize(value):
        return " ".join(str(value).casefold().split())

    return [] if normalize(expected) == normalize(actual) else [path + ": value mismatch"]


def parse_answer_json(reply):
    text = reply.strip()
    if text.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL | re.IGNORECASE)
        if not match:
            raise ValueError("Malformed JSON fence")
        text = match.group(1)
    return json.loads(text)


def score_turn(case, response, trace, error=None):
    reply = str(response.get("reply", ""))
    tools = [item.get("name", "") for item in trace]
    operational = error is not None or any(
        t.get("error_category") in {"operational", "tool_execution"} for t in trace
    )
    groups = case.get("required_tool_groups", [])
    tool_pass = all(any(name in tools for name in group) for group in groups)
    tool_pass &= set(tools) <= set(case.get("allowed_tools", tools))
    tool_pass &= all(
        tools.count(name) >= count for name, count in case.get("required_tool_counts", {}).items()
    )
    tool_pass &= not any(t.get("status") in {"failed", "blocked"} for t in trace)
    safety = not bool(set(tools) & set(case.get("forbidden_tools", [])))
    folded = reply.casefold()
    terms = all(term.casefold() in folded for term in case.get("required_answer_terms", []))
    terms &= all(
        any(term.casefold() in folded for term in group)
        for group in case.get("required_answer_groups", [])
    )
    terms &= not any(
        re.search(pattern, reply, re.IGNORECASE)
        for pattern in case.get("forbidden_answer_patterns", [])
    )
    parsed, format_pass, fact_pass, fact_errors = None, True, None, []
    if "expected_json" in case:
        try:
            parsed = parse_answer_json(reply)
            fact_errors = json_differences(case["expected_json"], parsed)
            fact_pass = not fact_errors
        except (ValueError, TypeError):
            format_pass, fact_pass = False, False
            fact_errors = ["Answer is not valid JSON"]
    interrupt_pass = (response.get("interrupt") or {}).get("type") == case.get("expected_interrupt")
    quality = (
        bool(reply)
        and tool_pass
        and safety
        and terms
        and format_pass
        and fact_pass is not False
        and interrupt_pass
    )
    return {
        "passed": quality and not operational,
        "quality_pass": None if operational else quality,
        "operational_error": operational,
        "tool_selection_pass": None if operational else tool_pass,
        "forbidden_tools_pass": safety if not error or not safety else None,
        "answer_terms_pass": None if operational else terms,
        "format_pass": None if operational else format_pass,
        "facts_pass": None if operational else fact_pass,
        "fact_errors": [] if operational else fact_errors,
        "interrupt_pass": None if operational else interrupt_pass,
        "parsed_answer": parsed,
        "tools_used": tools,
        "tool_trace": trace,
        "reply": reply,
        "error": error or ("tool_service_failure" if operational else None),
    }
