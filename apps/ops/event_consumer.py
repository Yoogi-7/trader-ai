# apps/ops/event_consumer.py
# PL: Konsument Redpanda: czyta topic i wysyła do API /internal/events aby iść na WS/Redis.
# EN: Redpanda consumer: reads topic, forwards to API /internal/events for WS/Redis.

from __future__ import annotations
import os, json, time
import requests  # type: ignore

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "redpanda:9092")
EVENTS_TOPIC = os.getenv("EVENTS_TOPIC", "traderai.events")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "trader-ai-consumers")
API_URL = os.getenv("API_INTERNAL_URL", "http://api:8000")
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "changeme")

def _forward(evt: dict):
    try:
        requests.post(f"{API_URL}/api/internal/events", json={"type": evt.get("type"), "payload": evt.get("payload", {})},
                      headers={"x-internal-secret": INTERNAL_SECRET}, timeout=3.0)
    except Exception:
        pass

def main():
    try:
        from kafka import KafkaConsumer  # kafka-python
    except Exception as exc:  # pragma: no cover - optional dep missing in some envs
        print(f"[event_consumer] kafka-python not available ({exc!r}), running noop loop")
        while True:
            time.sleep(30)
        # never reached

    consumer = KafkaConsumer(
        EVENTS_TOPIC,
        bootstrap_servers=KAFKA_BROKERS.split(","),
        group_id=GROUP_ID,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="latest",
        consumer_timeout_ms=10000,
    )
    print("[event_consumer] started")
    while True:
        try:
            for msg in consumer:
                evt = msg.value
                _forward(evt)
        except Exception as e:
            time.sleep(1.0)

if __name__ == "__main__":
    main()
