import os
import logging
from redis import Redis
from rq import Worker, Queue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest_worker")

# Define Redis connection
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_conn = Redis.from_url(redis_url)

if __name__ == '__main__':
    log.info("Starting RQ worker for ingestion queue...")
    import redis
    
    try:
        # Provide the connection directly to the worker
        worker = Worker(['ingestion_queue'], connection=redis_conn)
        worker.work()
    except redis.exceptions.ConnectionError:
        log.error("❌ Could not connect to Redis!")
        log.error("Please ensure Redis is running. You can start it by running: redis-server --daemonize yes")
        exit(1)
