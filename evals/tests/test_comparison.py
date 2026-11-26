"""Offline tests of scoring/provenance; never call a provider or create a booking."""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import compare_runs
import evaluate_agent

CASE = {
    "id": "lookup",
    "message": "Find hotel",
    "required_tool_groups": [["get_hotel"]],
    "allowed_tools": ["get_hotel"],
    "forbidden_tools": ["book_room"],
    "required_answer_terms": ["hotel"],
}
RUNTIME = {
    "model": "test/model",
    "source_sha256": "test-source",
    "temperature": 0.3,
    "read_only_evals_supported": True,
}
GOOD = {
    "reply": "A hotel",
    "tool_trace": [{"name": "get_hotel", "status": "executed", "call_id": "test-call"}],
}


def report(repeats=1, response=GOOD, **kwargs):
    with (
        patch.object(evaluate_agent, "wait_until_ready"),
        patch.object(evaluate_agent, "_get_json", return_value=RUNTIME),
        patch.object(evaluate_agent, "chat", return_value=response),
    ):
        return evaluate_agent.evaluate("http://example.test", [CASE], repeats=repeats, **kwargs)


class ComparisonTests(unittest.TestCase):
    def test_repeats_use_fresh_sessions(self):
        with (
            patch.object(evaluate_agent, "wait_until_ready"),
            patch.object(evaluate_agent, "_get_json", return_value=RUNTIME),
            patch.object(evaluate_agent, "chat", return_value=GOOD) as chat,
        ):
            result = evaluate_agent.evaluate("http://example.test", [CASE], repeats=3)
        self.assertEqual(result["passed_count"], 3)
        self.assertEqual(len({call.args[2] for call in chat.call_args_list}), 3)
        self.assertEqual([r["repeat"] for r in result["cases"]], [1, 2, 3])

    def test_wrong_model_stops_before_requests(self):
        with self.assertRaisesRegex(ValueError, "model"):
            report(expected_model="wrong/model")

    def test_stale_source_stops_before_requests(self):
        with self.assertRaisesRegex(ValueError, "workflow"):
            report(expected_source="undeployed-change")

    def test_forbidden_tool_fails_even_with_correct_answer(self):
        result = report(
            response={
                "reply": "hotel",
                "tool_trace": [{"name": "book_room", "call_id": "unsafe-call"}],
            }
        )
        self.assertFalse(result["all_cases_passed"])
        self.assertFalse(result["cases"][0]["forbidden_tools_pass"])

    def test_compares_paired_improvements(self):
        left = report(response={"reply": "wrong answer", "tool_trace": []})
        right = report()
        result = compare_runs.compare(left, right)
        self.assertEqual(result["pass_rate_delta_percentage_points"], 100)
        self.assertEqual(result["improvements"], [{"id": "lookup", "repeat": 1}])
        self.assertEqual(result["regressions"], [])

    def test_rejects_dataset_scorer_or_fixture_changes(self):
        left = report()
        for field in ["dataset_sha256", "scorer_version", "fixture_label"]:
            with self.subTest(field=field):
                right = copy.deepcopy(left)
                right[field] = "different"
                with self.assertRaises(ValueError):
                    compare_runs.compare(left, right)

    def test_rejects_different_repeat_count(self):
        with self.assertRaisesRegex(ValueError, "repeat"):
            compare_runs.compare(report(), report(repeats=2))

    def test_rejects_runtime_configuration_drift(self):
        left = report()
        right = copy.deepcopy(left)
        right["configuration_stable"] = False
        with self.assertRaisesRegex(ValueError, "configuration"):
            compare_runs.compare(left, right)

    def test_errored_requests_do_not_improve_latency_metrics(self):
        result = report(repeats=2)
        result["cases"][0].update(
            error="HTTPError HTTP 500",
            latency_ms=1,
            operational_error=True,
            quality_pass=None,
            passed=False,
        )
        result["cases"][1].update(latency_ms=100)
        metrics = compare_runs.summarize(result["cases"])
        self.assertEqual(metrics["latency_p50_ms"], 100)
        self.assertEqual(metrics["error_count"], 1)


if __name__ == "__main__":
    unittest.main()
