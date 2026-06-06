"""
Kafka event schemas shared between Go producers and Python consumers.

Go services serialize these as JSON and publish to hotel.booking.events.
Python services deserialize and validate with these Pydantic models.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(StrEnum):
    BOOKING_CREATED = "booking.created"
    BOOKING_CANCELLED = "booking.cancelled"
    BOOKING_CONFIRMED = "booking.confirmed"
    PAYMENT_PROCESSED = "payment.processed"
    PAYMENT_FAILED = "payment.failed"


class EventEnvelope(BaseModel):
    """Top-level wrapper for all hotel.booking.events messages."""
    event_id: UUID
    event_type: EventType
    occurred_at: datetime
    schema_version: str = "1.0"
    payload: dict[str, Any]


class BookingCreatedPayload(BaseModel):
    booking_id: UUID
    guest_id: UUID
    hotel_code: str
    room_id: UUID
    check_in: date
    check_out: date
    total_price: Decimal
    currency: str = "USD"


class BookingCancelledPayload(BaseModel):
    booking_id: UUID
    guest_id: UUID
    hotel_code: str
    cancelled_at: datetime
    reason: str = ""


class BookingConfirmedPayload(BaseModel):
    booking_id: UUID
    confirmation_code: str
    confirmed_at: datetime


class PaymentProcessedPayload(BaseModel):
    booking_id: UUID
    amount: Decimal
    currency: str
    payment_method: str
    transaction_id: str
    processed_at: datetime


class PaymentFailedPayload(BaseModel):
    booking_id: UUID
    amount: Decimal
    currency: str
    failure_reason: str
    failed_at: datetime


_PAYLOAD_TYPES: dict[EventType, type[BaseModel]] = {
    EventType.BOOKING_CREATED: BookingCreatedPayload,
    EventType.BOOKING_CANCELLED: BookingCancelledPayload,
    EventType.BOOKING_CONFIRMED: BookingConfirmedPayload,
    EventType.PAYMENT_PROCESSED: PaymentProcessedPayload,
    EventType.PAYMENT_FAILED: PaymentFailedPayload,
}


def parse_payload(envelope: EventEnvelope) -> BaseModel:
    """Deserialize payload dict into the typed model for this event type."""
    payload_type = _PAYLOAD_TYPES.get(envelope.event_type)
    if payload_type is None:
        raise ValueError(f"Unknown event type: {envelope.event_type}")
    return payload_type.model_validate(envelope.payload)
