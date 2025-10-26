from uuid import uuid4
from time import gmtime, strftime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from celery.result import AsyncResult

from app.api.schemas import ProcessResponse, StatusResp, FeatureProjectRequest, SynthesizeRequest
from app.api.validators import validate_bpm
from app.workers.celery_app import celery_app
from app.core import storage
from app.core.pipeline_stub import stub_separate, stub_synthesize
from app.core.config import settings
from app.core.task import run_pipeline_task

router = APIRouter()

#健康检查节点
@router.get("/healthz")
def healthz():
    return {"ok": True}

@router.post("/hachimi_ai_mad/tasks/process", response_model=ProcessResponse, status_code=201)
#!!!!!!!!!!确保task_id,project_id,job_id三者同步,避免404!!!!!!!!!!
async def process(
    file: UploadFile = File(...),
    bpm: int = Form(...),
    project_name: str = Form(...), 
    pen_name: str = Form(...)
):
    if (file.content_type or "").split("/")[0] != "audio":
        raise HTTPException(415, "不支持的文件类型")
    validate_bpm(bpm)

    project_id = str(uuid4())
    in_path = await storage.save_upload(project_id, file)
    storage.save_project_meta(project_id, {
        "project_name": project_name,
        "pen_name": pen_name,
        "created_at": strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()),
    })

    res = run_pipeline_task.apply_async(
        kwargs={"project_id": project_id, "bpm": bpm, "in_path": in_path},
        task_id = project_id
    )
    job_id = res.id
    return {
        "job_id": job_id,
        "status_url": f"/hachimi_ai_mad/tasks/{job_id}/status",
        "download_url": f"/hachimi_ai_mad/tasks/{job_id}/download",
    }



@router.get("/hachimi_ai_mad/tasks/{job_id}/status", response_model=StatusResp)
def get_task_status(job_id: str):
    r = AsyncResult(job_id, app=celery_app)
    state = r.state  # 获取Celery原生状态（PENDING/STARTED/PROGRESS/SUCCESS/FAILURE等）
    
    # 1. 统一状态语义（修改后的核心逻辑）
    if state == "SUCCESS":
        status = "SUCCEEDED"  # 映射为业务语义的"成功"
    elif state == "FAILURE":
        status = "FAILED"     # 映射为业务语义的"失败"
    else:
        status = state  # 保留PENDING/STARTED/PROGRESS等中间状态
    
    # 2. 补充任务详情（原代码的核心功能）
    result = {"job_id": job_id, "status": status}  # 基础返回
    
    # 任务执行中（STARTED/PROGRESS）：返回阶段和进度
    if state in ("STARTED", "PROGRESS"):
        meta = r.info or {}  # 获取任务执行中的元数据（由任务函数通过update_state传递）
        result["message"] = meta.get("stage")  # 如"separate" "midi"等当前阶段
        result["progress"] = meta.get("progress")  # 如0-100的进度百分比
    
    # 任务失败（FAILURE）：返回错误详情
    elif state == "FAILURE":
        result["message"] = str(r.info)  # 错误信息（如异常堆栈或描述）
    
    return result

@router.get("/hachimi_ai_mad/tasks/{job_id}/download")
def download_result(job_id: str):
    payload = storage.read_result(job_id)
    if not payload:
        raise HTTPException(status_code=404, detail="result not ready")
    return payload

@router.post("/hachimi_ai_mad/tasks/{job_id}/publish")
def publish_job_result(job_id: str):
    try:
        publish_meta = storage.publish_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="result not ready or missing")
    return publish_meta

# ========== 阶段处理流程 ==========
@router.post("/hachimi_ai_mad/stages/separate/retry")
async def separate_retry(
    project_id: str = Form(...),
    bpm: int = Form(120),
    allow_missing: bool = Form(False),
    force: bool = Form(False),
    audio_file: Optional[UploadFile] = File(None),
):
    """分离重试"""
    storage.ensure_project_initialized(project_id)
    if audio_file is not None:
        await storage.save_upload(project_id, audio_file, stage="uploads")
    try:
        out = stub_separate(project_id, bpm=int(bpm), allow_missing=bool(allow_missing))
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="缺少输入音频；请先上传或设置 allow_missing=true")
    return out

@router.post("/hachimi_ai_mad/stages/midi/upload")
async def midi_upload(
    project_id: str = Form(...),
    quantize: bool = Form(True),
    midi_file: UploadFile = File(...),
):
    """MIDI上传"""
    storage.ensure_project_initialized(project_id)
    midi_url = await storage.save_upload(project_id, midi_file, stage="midi")
    q_url = midi_url if bool(quantize) else None
    storage.record_stage_artifacts(project_id, "midi", {"midi": midi_url, "quantized": q_url or midi_url})
    return {"ok": True, "midi_url": midi_url, "quantized_url": q_url}

@router.post("/hachimi_ai_mad/stages/lyrics/upload")
async def lyrics_upload(
    project_id: str = Form(...),
    phrases_json: UploadFile = File(...),
):
    """歌词上传"""
    storage.ensure_project_initialized(project_id)
    phrases_url = await storage.save_upload(project_id, phrases_json, stage="lyrics", dst_name="phrases.json")
    storage.record_stage_artifacts(project_id, "lyrics", {"phrases_json": phrases_url})
    return {"ok": True, "phrases_json_url": phrases_url}

@router.post("/hachimi_ai_mad/stages/synthesize/retry")
def synth_retry(body: SynthesizeRequest):
    """合成重试"""
    storage.ensure_project_initialized(body.project_id)
    try:
        out = stub_synthesize(body.project_id, fmt=body.format, allow_missing=bool(body.allow_missing))
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="缺少上游产物")
    return out

# ========== 展示区 ==========
@router.get("/hachimi_ai_mad/showcase")
def list_showcase():
    return storage.list_published()

@router.get("/hachimi_ai_mad/showcase/{public_id}/preview")
def get_showcase_preview(public_id: str):
    """预览展示，参数名统一为public_id"""
    return storage.serve_published(public_id, "preview.wav")

@router.get("/hachimi_ai_mad/showcase/{public_id}/result")
def get_showcase_result(public_id: str):
    """结果展示，参数名统一为public_id"""
    return storage.serve_published(public_id, "result.wav")

# ========== 项目管理 ==========
@router.get("/hachimi_ai_mad/projects/{project_id}/artifacts")
def get_project_artifacts(project_id: str):
    return {"project_id": project_id, "stages": storage.list_artifacts(project_id)}

@router.get("/hachimi_ai_mad/projects/{project_id}/{kind}/{filename:path}")
def get_file(project_id: str, kind: str, filename: str):
    return storage.serve_file(project_id, kind, filename)

# ========== 项目列表 ==========
@router.get("/hachimi_ai_mad/projects/featured")
def get_featured_projects():
    return storage.list_featured_projects()

@router.get("/hachimi_ai_mad/projects/recent")
def get_recent_projects():
    return storage.list_recent_projects()

# ========== 管理员功能 ==========
@router.post("/hachimi_ai_mad/admin/feature-project")
def admin_feature_project(req: FeatureProjectRequest):
    if not settings.ADMIN_SECRET or req.admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")
    meta = storage.feature_project(req.project_id)
    return {"ok": True, "project_id": req.project_id, "is_featured": meta.get("is_featured", False)}