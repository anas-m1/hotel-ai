"""Check the webhook boundary and parity with the existing deterministic scorer."""

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from import_langfuse import map_suite
from langfuse_experiment import validate_dataset
from scoring import score_turn

HERE = Path(__file__).resolve().parents[1] / "agent"


class EvaluatorParityTests(unittest.TestCase):
    def test_typescript_matches_python_for_catalog_suites_and_failure_modes(self):
        fixtures, expected = [], []
        for filename in ["agent_cases.json", "heldout_cases.json"]:
            _, items = map_suite(HERE / filename, filename)
            for item in items:
                case = item["metadata"]["source_case"]
                rules = case.get("turns", [case])
                for mode in ["correct", "bad_facts", "blocked", "operational", "http_error"]:
                    turns, grades = [], []
                    for rule in rules:
                        tools = [g[0] for g in rule.get("required_tool_groups", [])]
                        for name, count in rule.get("required_tool_counts", {}).items():
                            tools += [name] * max(0, count - tools.count(name))
                        trace = [
                            {"name": n, "status": "executed", "call_id": str(i)}
                            for i, n in enumerate(tools)
                        ]
                        if mode == "blocked":
                            trace.append(
                                {"name": "book_room", "status": "blocked", "call_id": "blocked"}
                            )
                        if mode == "operational":
                            trace.append(
                                {
                                    "name": "get_hotel",
                                    "status": "failed",
                                    "error_category": "operational",
                                    "call_id": "op",
                                }
                            )
                        reply = (
                            json.dumps(rule["expected_json"])
                            if "expected_json" in rule
                            else " ".join(
                                rule.get("required_answer_terms", [])
                                + [g[0] for g in rule.get("required_answer_groups", [])]
                            )
                            or "Answer"
                        )
                        if mode == "bad_facts":
                            reply = '{"invented":true}'
                        raw = {
                            "reply": reply,
                            "tool_trace": trace,
                            "interrupt": None,
                            "error": "TimeoutError" if mode == "http_error" else None,
                        }
                        turns.append(raw)
                        grades.append(score_turn(rule, raw, trace, raw["error"]))
                    fixtures.append(
                        {
                            "observation": {
                                "output": {"schema": "hotel-agent-evidence-v1", "turns": turns}
                            },
                            "experiment": {
                                "itemMetadata": item["metadata"],
                                "itemExpectedOutput": item["expected_output"],
                            },
                        }
                    )
                    op = any(r["operational_error"] for r in grades)
                    metrics = {"operational_success": not op}
                    safety = (
                        False
                        if any(r["forbidden_tools_pass"] is False for r in grades)
                        else None
                        if op
                        else True
                    )
                    if safety is not None:
                        metrics["safety"] = safety
                    if not op:
                        for name, field in [
                            ("task_success", "passed"),
                            ("tool_selection", "tool_selection_pass"),
                            ("answer_terms", "answer_terms_pass"),
                            ("format", "format_pass"),
                        ]:
                            metrics[name] = all(r[field] for r in grades)
                        if any(r["facts_pass"] is not None for r in grades):
                            metrics["facts"] = all(r["facts_pass"] is not False for r in grades)
                    expected.append(metrics)
        # Match 4.36's real dispatcher context, which serializes JSON fields.
        encoded = []
        for fixture in fixtures:
            value = copy.deepcopy(fixture)
            value["observation"]["output"] = json.dumps(value["observation"]["output"])
            metadata = value["experiment"]["itemMetadata"]
            value["experiment"]["itemMetadata"] = {
                k: json.dumps(v) for k, v in metadata.items() if k != "source_case"
            }
            value["experiment"]["itemExpectedOutput"] = json.dumps(
                value["experiment"]["itemExpectedOutput"]
            )
            encoded.append(value)
        fixtures += encoded
        expected += copy.deepcopy(expected)
        script = (
            (HERE / "evaluators/hotel_agent.ts").read_text()
            + '\nconst fixtures=JSON.parse(require("fs").readFileSync(0,"utf8"));'
            + "console.log(JSON.stringify(fixtures.map(ctx=>evaluate(ctx).scores)));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(fixtures),
            text=True,
            capture_output=True,
            check=True,
        )
        for scores, target in zip(json.loads(result.stdout), expected):
            self.assertEqual({s["name"]: s["value"] for s in scores}, target)

    def test_invalid_evidence_does_not_get_a_success_score(self):
        script = (
            HERE / "evaluators/hotel_agent.ts"
        ).read_text() + "\nevaluate({observation:{output:{}},experiment:{}});"
        result = subprocess.run(["node", "-e", script], capture_output=True)
        self.assertNotEqual(result.returncode, 0)


class HostedDatasetTests(unittest.TestCase):
    def test_changed_hosted_checking_rules_are_rejected(self):
        from types import SimpleNamespace

        metadata, plan = map_suite(HERE / "heldout_cases.json", "hotel-agent-heldout")
        items = [
            SimpleNamespace(
                id=i["id"],
                input=i["input"],
                expected_output=i["expected_output"],
                metadata=copy.deepcopy(i["metadata"]),
                status="ACTIVE",
            )
            for i in plan
        ]
        dataset = SimpleNamespace(items=items)
        validate_dataset(dataset, "hotel-agent-heldout")
        items[0].metadata["tool_rules_by_turn"] = []
        with self.assertRaises(ValueError):
            validate_dataset(dataset, "hotel-agent-heldout")


class WebhookTests(unittest.TestCase):
    def test_snapshot_retry_identity_and_run_config_validation(self):
        from experiment_webhook import normalize

        body = {
            "projectId": "project",
            "datasetName": "hotel-agent-dev",
            "datasetId": "dataset",
            "payload": {
                "run_name": "smoke-v1",
                "variant": "local",
                "expected_model": "ollama/test",
                "case_ids": ["facts_HTL001"],
            },
        }
        with patch.dict(os.environ, {"EVAL_PROJECT_ID": "project"}):
            a, b = normalize(body), normalize(body)
            self.assertEqual(a["id"], b["id"])
            self.assertEqual(a["identity"], b["identity"])
            with self.assertRaises(ValueError):
                normalize({**body, "projectId": "wrong"})
            with self.assertRaises(ValueError):
                normalize({**body, "payload": {**body["payload"], "base_url": "http://evil"}})
            with self.assertRaises(ValueError):
                normalize({**body, "payload": {**body["payload"], "repeats": True}})

    def test_http_auth_dedup_and_conflicting_run_name(self):
        import tempfile

        import experiment_webhook as webhook
        from fastapi.testclient import TestClient

        body = {
            "projectId": "project",
            "datasetName": "hotel-agent-dev",
            "datasetId": "dataset",
            "payload": {
                "run_name": "smoke-v1",
                "variant": "local",
                "expected_model": "ollama/test",
            },
        }
        token = "t" * 40
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(webhook, "DATA", Path(directory)),
            patch.dict(os.environ, {"EVAL_PROJECT_ID": "project", "EVAL_WEBHOOK_TOKEN": token}),
            patch.object(webhook, "worker"),
        ):
            with TestClient(webhook.app) as client:
                self.assertEqual(client.post("/experiments", json=body).status_code, 401)
                headers = {"Authorization": "Bearer " + token}
                first = client.post("/experiments", json=body, headers=headers)
                self.assertEqual(first.status_code, 202)
                again = client.post("/experiments", json=body, headers=headers)
                self.assertTrue(again.json()["duplicate"])
                conflict = client.post(
                    "/experiments",
                    json={**body, "payload": {**body["payload"], "variant": "other"}},
                    headers=headers,
                )
                self.assertEqual(conflict.status_code, 409)
                status = client.get("/jobs/" + first.json()["job_id"], headers=headers)
                self.assertEqual(status.json()["status"], "queued")
