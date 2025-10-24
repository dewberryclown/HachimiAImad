# app/workers/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery("hachimi_ai_mad")

if settings.CELERY_EAGER:
    # 本地/测试：完全不依赖 Redis，且把 eager 结果存起来供 AsyncResult 查询
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        task_store_eager_result=True,     # 关键：存储结果
        task_track_started=True,          # 允许 STARTED
        broker_url="memory://",
        result_backend="cache+memory://",
    )
else:
    celery_app.conf.update(
        broker_url=settings.REDIS_URL,
        result_backend=settings.REDIS_URL,
        worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        task_track_started=True,
    )

