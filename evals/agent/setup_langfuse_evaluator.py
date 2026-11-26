#!/usr/bin/env python3
"""Publish an immutable, content-addressed evaluator and narrowly scoped rule."""

import hashlib

from langfuse.api.evaluation_commons.types.evaluation_rule_filter import (
    EvaluationRuleFilter_Boolean,
    EvaluationRuleFilter_StringObject,
    EvaluationRuleFilter_StringOptions,
)
from langfuse.api.evaluation_rules.types.evaluation_rule_evaluator_assignment_input import (
    EvaluationRuleEvaluatorAssignmentInput,
)
from langfuse.api.evaluators.types.create_evaluator_request import CreateEvaluatorRequest_Code
from langfuse_experiment import EVALUATOR, make_client


def setup():
    client = make_client()
    try:
        source = EVALUATOR.read_text()
        name = "hotel-agent-deterministic-" + hashlib.sha256(source.encode()).hexdigest()[:12]
        evaluators = client.api.evaluators.list(limit=100).data
        evaluator = next((e for e in evaluators if e.name == name), None)
        if evaluator is None:
            evaluator = client.api.evaluators.create(
                request=CreateEvaluatorRequest_Code(
                    name=name, source_code=source, source_code_language="TYPESCRIPT"
                )
            )
        if evaluator.source_code != source:
            raise ValueError("Evaluator name collision; refusing to overwrite")
        rule_name = name + "-experiments"
        rules = client.api.evaluation_rules.list(limit=100).data
        rule = next((r for r in rules if r.name == rule_name), None)
        filters = [
            EvaluationRuleFilter_StringOptions(
                column="name", operator="any of", value=["hotel-agent-scenario"]
            ),
            EvaluationRuleFilter_Boolean(
                column="isExperimentItemRootSpan", operator="=", value=True
            ),
            # 4.36 stores string metadata as JSON text during in-memory matching.
            # contains matches the full content hash with or without JSON quotes.
            EvaluationRuleFilter_StringObject(
                column="metadata",
                key="evaluator_sha256",
                operator="contains",
                value=hashlib.sha256(source.encode()).hexdigest(),
            ),
        ]
        assignments = [EvaluationRuleEvaluatorAssignmentInput(evaluator_id=evaluator.id)]
        if rule is None:
            rule = client.api.evaluation_rules.create(
                name=rule_name,
                enabled=True,
                sampling=1,
                evaluator_assignments=assignments,
                filter=filters,
            )
        else:
            rule = client.api.evaluation_rules.update(
                rule.id,
                enabled=True,
                sampling=1,
                evaluator_assignments=assignments,
                filter=filters,
            )
        print("Evaluator:", evaluator.id, name)
        print("Rule:", rule.id)
    finally:
        client.shutdown()


if __name__ == "__main__":
    try:
        setup()
    except Exception as exc:
        print("Setup failed:", type(exc).__name__)
        raise SystemExit(1) from None
