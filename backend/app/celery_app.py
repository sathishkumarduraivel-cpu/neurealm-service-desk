"""Optional Celery worker for horizontally-scaled deployments:
   celery -A app.celery_app worker -B   (requires `pip install celery redis`, REDIS_URL)"""
import os
try:
    from celery import Celery
except ImportError:  # celery is optional
    Celery = None

if Celery:
    celery = Celery("servicedesk", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    celery.conf.beat_schedule = {"sla-escalation": {"task": "app.celery_app.sla_task", "schedule": 60.0}}

    @celery.task
    def sla_task():
        from .scheduler import sla_job
        sla_job()
