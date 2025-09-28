# apps/ops/event_consumer.py
# PL: Kafka została usunięta – moduł pozostaje jako no-op dla kompatybilności.
# EN: Kafka support removed – keep a lightweight placeholder for backwards compatibility.

import time


def main() -> None:
    print("[event_consumer] Kafka support removed – nothing to do.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
