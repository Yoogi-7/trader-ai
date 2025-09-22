import redis
from .config import settings

r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
