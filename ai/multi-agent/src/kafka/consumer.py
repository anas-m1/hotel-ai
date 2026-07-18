"""
Kafka consumer for hotel.booking.events.

Runs as a background asyncio task alongside the FastAPI server.
Each message is validated against the shared EventEnvelope schema,
then dispatched to the appropriate handler.
"""

from __future__ import annotations

import json

import structlog
from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from config import settings

log = structlog.get_logger()


async def run_consumer() -> None:
    """Consume hotel.booking.events indefinitely. Called at app startup."""
    # Import inside the coroutine so a missing shared volume only kills the
    # consumer task, not the whole FastAPI process.
    try:
        from booking_events import EventEnvelope, EventType, parse_payload
    except ImportError:
        log.warning("booking_events_unavailable", reason="shared volume not mounted; consumer disabled")
        return

    async def _handle_booking_created(envelope: EventEnvelope) -> None:
        payload = parse_payload(envelope)
        log.info(
            "booking_created",
            booking_id=str(payload.booking_id),  # type: ignore[attr-defined]
            hotel_code=payload.hotel_code,  # type: ignore[attr-defined]
            total_price=str(payload.total_price),  # type: ignore[attr-defined]
        )

    async def _handle_booking_cancelled(envelope: EventEnvelope) -> None:
        payload = parse_payload(envelope)
        log.info(
            "booking_cancelled",
            booking_id=str(payload.booking_id),  # type: ignore[attr-defined]
            hotel_code=payload.hotel_code,  # type: ignore[attr-defined]
        )

    handlers = {
        EventType.BOOKING_CREATED: _handle_booking_created,
        EventType.BOOKING_CANCELLED: _handle_booking_cancelled,
    }

    consumer = AIOKafkaConsumer(
        settings.kafka_booking_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    await consumer.start()
    log.info("kafka_consumer_started", topic=settings.kafka_booking_topic)

    try:
        async for msg in consumer:
            try:
                raw = json.loads(msg.value.decode("utf-8"))
                envelope = EventEnvelope.model_validate(raw)
            except (json.JSONDecodeError, ValidationError) as exc:
                log.warning("kafka_bad_message", error=str(exc), offset=msg.offset)
                continue

            handler = handlers.get(envelope.event_type)
            if handler:
                try:
                    await handler(envelope)
                except Exception as exc:
                    log.error(
                        "kafka_handler_error",
                        event_type=envelope.event_type,
                        error=str(exc),
                    )
    finally:
        await consumer.stop()
        log.info("kafka_consumer_stopped")
