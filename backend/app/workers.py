"""rq worker entrypoint: `python app/workers.py`."""
from redis import Redis
from rq import Worker, Queue

from app.config import settings

redis = Redis.from_url(settings.redis_url, decode_responses=False)
queue = Queue("nomos-jobs", connection=redis, default_timeout=300)


def run_slow_job(delay: float = 0.1) -> dict:  # pragma: no cover - worker runtime
    from app.api.jobs import run_slow_job as impl  # avoid circular import at app load
    return impl(delay)


if __name__ == "__main__":
    worker = Worker([queue], connection=redis)
    worker.work()