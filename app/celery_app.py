from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "msg91_bigin_integration",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

interval_hours = getattr(settings, 'RECONCILIATION_INTERVAL_HOURS', 4) or 4

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "run-full-reconciliation-periodic": {
            "task": "app.tasks.lead_tasks.run_full_reconciliation_task",
            "schedule": crontab(minute=0, hour=f"*/{interval_hours}"),
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
