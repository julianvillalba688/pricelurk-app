from celery import Celery

from app.core.config import settings

TASK = "app.workers.tasks.check_product_prices"
celery_app = Celery("pricelurk", broker=settings.REDIS_URL, backend=settings.REDIS_URL,
                    include=["app.workers.tasks"])
celery_app.conf.update(
    task_default_queue=settings.CELERY_QUEUE,
    task_routes={"app.workers.tasks.*": {"queue": settings.CELERY_QUEUE}},
    beat_schedule={"monitor-prices": {"task": TASK, "schedule": settings.MONITOR_INTERVAL_SECONDS,
                                      "options": {"queue": settings.CELERY_QUEUE, "expires": settings.MONITOR_INTERVAL_SECONDS}}},
    timezone="UTC", task_track_started=True, worker_prefetch_multiplier=1,
    task_soft_time_limit=3000, task_time_limit=3060,
    broker_connection_retry_on_startup=True,
)
