import asyncio
from aiokafka import AIOKafkaProducer
from .config import settings
import orjson

class KafkaBus:
    def __init__(self):
        self._producer = None

    async def start(self):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKERS,
            value_serializer=lambda v: orjson.dumps(v),
            compression_type="gzip",
        )
        await self._producer.start()

    async def stop(self):
        if self._producer:
            await self._producer.stop()

    async def publish(self, topic: str, value: dict):
        await self._producer.send_and_wait(topic, value)

bus = KafkaBus()
