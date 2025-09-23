# apps/common/event_bus.py
# PL: Prosty producent zdarzeń do Redpanda/Kafka z bezpiecznym fallbackiem (Noop).
# EN: Simple Kafka producer for Redpanda with safe Noop fallback.

from __future__ import annotations
import os, json, time
from typing import Dict, Any, Optional

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "redpanda:9092")
EVENTS_TOPIC = os.getenv("EVENTS_TOPIC", "traderai.events")
CLIENT_ID = os.getenv("KAFKA_CLIENT_ID", "trader-ai")

class _NoopProducer:
    def send(self, topic: str, value: bytes):
        # No-op – useful in dev without Kafka
        pass
    def flush(self, timeout: float = 0.0):
        pass

try:
    from kafka import KafkaProducer  # kafka-python
    _producer: Optional[KafkaProducer] = KafkaProducer(
        bootstrap_servers=KAFKA_BROKERS.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        api_version_auto_timeout_ms=5000,
        client_id=CLIENT_ID,
        linger_ms=10,
        retries=3,
    )
except Exception:
    _producer = None

def publish(event_type: str, payload: Dict[str, Any]):
    """
    PL: Wyślij zdarzenie do Redpandy (topic=EVENTS_TOPIC). Fallback: Noop.
    EN: Publish event to Redpanda. Fallback: Noop.
    """
    msg = {
        "type": event_type,
        "ts": int(time.time() * 1000),
        "payload": payload,
    }
    if _producer is None:
        _NoopProducer().send(EVENTS_TOPIC, json.dumps(msg).encode("utf-8"))
        return
    try:
        _producer.send(EVENTS_TOPIC, msg)
    except Exception:
        # soft-fail
        pass

def flush():
    if _producer is not None:
        try:
            _producer.flush(1.0)
        except Exception:
            pass
