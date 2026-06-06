"""
Kafka producer for hotel.agent.events.

Publishes events when the multi-agent system completes a significant action
(e.g., booking confirmed via agent, search performed). Downstream analytics
consumers can subscribe to this topic in Phase 7.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from aiokafka import AIOKafkaProducer

from config import settings

log = structlog.get_logger()

_producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await _producer.start()
    log.info("kafka_producer_started")


async def stop_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        log.info("kafka_producer_stopped")


async def publish_agent_event(event_type: str, payload: dict[str, Any]) -> None:
    if _producer is None:
        log.warning("kafka_producer_not_started", event_type=event_type)
        return

    envelope = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "payload": payload,
    }

    try:
        await _producer.send_and_wait(settings.kafka_agent_topic, envelope)
    except Exception as exc:
        log.error("kafka_publish_error", event_type=event_type, error=str(exc))
