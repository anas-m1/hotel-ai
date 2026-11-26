import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import evaluate_agent
from fixtures import verify_catalog
from scoring import json_differences, score_turn

RUNTIME = {"model": "test/model", "source_sha256": "test-source", "read_only_evals_supported": True}


class QualityScoringTests(unittest.TestCase):
    def test_wrong_price_fails_even_with_correct_hotel_name(self):
        case = {"expected_json": {"name": "City Centre Suites", "price": 280, "currency": "USD"}}
        response = {
            "reply": json.dumps({"name": "City Centre Suites", "price": 140, "currency": "USD"})
        }
        result = score_turn(case, response, [])
        self.assertFalse(result["facts_pass"])
        self.assertFalse(result["passed"])

    def test_currency_and_unrequested_claims_are_checked(self):
        self.assertTrue(json_differences({"currency": "USD"}, {"currency": "GBP"}))
        self.assertTrue(json_differences({"price": 280}, {"price": 280, "pool": True}))

    def test_numeric_format_and_fact_array_order_are_tolerated(self):
        self.assertFalse(
            json_differences(
                {"price": 280, "facilities": ["gym", "spa"]},
                {"price": "280.00", "facilities": ["SPA", "gym"]},
            )
        )
        self.assertTrue(json_differences(1, True))

    def test_invalid_json_is_format_failure(self):
        result = score_turn({"expected_json": {"found": False}}, {"reply": "not found"}, [])
        self.assertFalse(result["format_pass"])
        self.assertFalse(result["passed"])

    def test_operational_failure_is_not_answer_quality_failure(self):
        result = score_turn(
            {"expected_json": {"price": 280}}, {"reply": ""}, [], "HTTPError HTTP 500"
        )
        self.assertTrue(result["operational_error"])
        self.assertIsNone(result["quality_pass"])
        self.assertIsNone(result["facts_pass"])
        self.assertIsNone(result["forbidden_tools_pass"])

    def test_tool_outage_is_not_scored_as_empty_catalog(self):
        result = score_turn(
            {},
            {"reply": "No hotels"},
            [
                {
                    "name": "semantic_search_hotels",
                    "status": "failed",
                    "error_category": "operational",
                }
            ],
        )
        self.assertIsNone(result["quality_pass"])
        self.assertFalse(result["passed"])

    def test_multiturn_reuses_session_without_double_counting_tools(self):
        case = {
            "id": "context",
            "turns": [
                {"message": "lookup", "required_tool_groups": [["get_hotel"]]},
                {"message": "follow up", "allowed_tools": []},
            ],
        }
        response = {
            "reply": "Hotel",
            "tool_trace": [{"name": "get_hotel", "call_id": "one", "status": "executed"}],
        }
        with (
            patch.object(evaluate_agent, "wait_until_ready"),
            patch.object(evaluate_agent, "_get_json", return_value=RUNTIME),
            patch.object(evaluate_agent, "chat", return_value=response) as chat,
        ):
            result = evaluate_agent.evaluate("http://example.test", [case])
        self.assertEqual(chat.call_args_list[0].args[2], chat.call_args_list[1].args[2])
        self.assertEqual(result["cases"][0]["tools_used"], ["get_hotel"])
        self.assertTrue(result["cases"][0]["passed"])

    def test_fixture_mismatch_stops_preflight(self):
        expected = json.loads(
            (Path(__file__).resolve().parents[1] / "agent/catalog_fixture.json").read_text()
        )

        def lookup(url):
            if "?limit=" in url:
                return [{"hotel_code": h["hotel_code"]} for h in expected["hotels"]]
            code = url.split("/hotels/")[1].split("/")[0]
            h = copy.deepcopy(next(h for h in expected["hotels"] if h["hotel_code"] == code))
            if url.endswith("/rooms"):
                h["rooms"][0]["base_price"] = 99999
                return h["rooms"]
            h["facilities"] = ",".join(h["facilities"])
            return h

        with self.assertRaisesRegex(ValueError, "fixture mismatch"):
            verify_catalog("http://example.test", expected, lookup)


if __name__ == "__main__":
    unittest.main()
