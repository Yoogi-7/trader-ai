import os

class Settings:
    DB_URL = f"postgresql+psycopg://{os.getenv('DB_USER','trader')}:{os.getenv('DB_PASSWORD','traderpass')}@{os.getenv('DB_HOST','db')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME','traderai')}"
    REDIS_URL = os.getenv("REDIS_URL","redis://redis:6379/0")
    KAFKA_BROKERS = os.getenv("KAFKA_BROKERS","redpanda:9092").split(",")
    TOPIC_SIGNALS = os.getenv("KAFKA_TOPIC_SIGNALS","signals.live.v1")
    TOPIC_BACKFILL = os.getenv("KAFKA_TOPIC_BACKFILL","jobs.backfill.v1")
    TOPIC_METRICS = os.getenv("KAFKA_TOPIC_METRICS","models.metrics.v1")
    API_TITLE = os.getenv("API_TITLE","Trader AI")
    DEBUG = os.getenv("API_DEBUG","false").lower()=="true"
    SECRET_KEY = os.getenv("SECRET_KEY","devsecret")
    MIN_NET_PCT = float(os.getenv("MIN_NET_PROFIT_PCT","2.0"))
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD","0.58"))

settings = Settings()
