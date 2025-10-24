from app.workers.celery_app import celery_app
from app.core.pipeline_stub import run_pipeline_stub, STEPS

from app.workers.celery_app import celery_app
from app.core.pipeline_stub import run_pipeline_stub as _run_pipeline_stub, STEPS

@celery_app.task(name="tasks.run_pipeline", bind=True)
def run_pipeline_task(self, project_id: str, in_path: str, bpm: int) -> dict:
    total = len(STEPS)

    def on_step(step: str, index: int):
        progress = round(index / total, 4)
        self.update_state(state="PROGRESS", meta={"stage": step, "progress": progress})

    self.update_state(state="STARTED", meta={"stage": "boot", "progress": 0.0})
    payload = _run_pipeline_stub(project_id, in_path, bpm, on_step=on_step)
    return payload


