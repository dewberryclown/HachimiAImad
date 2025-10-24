import os
import json
import shutil
import datetime as _dt
from typing import Dict, Any, Optional

from fastapi import HTTPException
from starlette.responses import FileResponse

from app.core.config import settings

def _safe_join(base: str, *paths: str) -> str:
    base = os.path.abspath(base)
    final = os.path.abspath(os.path.join(base, *paths))
    if not final.startswith(base + os.sep) and final != base:
        raise HTTPException(status_code=400, detail="invalid path")
    return final

def project_root(project_id: str) -> str:
    return os.path.join(settings.TEMP_DIR, "projects", project_id)

def meta_path(project_id: str) -> str:
    return os.path.join(project_root(project_id), "meta.json")

def result_json_path(project_id: str) -> str:
    return os.path.join(project_root(project_id), "result.json")

def _ensure_meta_file(project_id: str) -> None:
    """确保元数据文件存在，避免递归调用"""
    meta_file = meta_path(project_id)
    if not os.path.exists(meta_file):
        initial_meta = {
            "project_id": project_id,
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
            "is_featured": False,
            "stage_artifacts": {},
        }
        os.makedirs(os.path.dirname(meta_file), exist_ok=True)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(initial_meta, f, ensure_ascii=False, indent=2)

def ensure_project_initialized(project_id: str) -> str:
    """初始化项目目录结构，避免递归调用 save_project_meta"""
    root = project_root(project_id)
    for d in ("uploads", "separate", "midi", "lyrics", "synth", "preview", "mix", "pub"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    
    # 使用内部函数避免递归
    _ensure_meta_file(project_id)
    return root

def stage_dir(project_id: str, stage: str) -> str:
    ensure_project_initialized(project_id)
    return _safe_join(project_root(project_id), stage)

# 元数据操作
def load_project_meta(project_id: str) -> Dict[str, Any]:
    _ensure_meta_file(project_id)  # 确保文件存在
    p = meta_path(project_id)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"project_id": project_id, "created_at": None, "is_featured": False, "stage_artifacts": {}}

def save_project_meta(project_id: str, meta: Dict[str, Any]) -> None:
    p = meta_path(project_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def update_project_meta(project_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    meta = load_project_meta(project_id)
    meta.update(patch)
    save_project_meta(project_id, meta)
    return meta

# 记录阶段处理产物
def record_stage_artifacts(project_id: str, stage: str, files: Dict[str, Optional[str]], skipped: bool = False) -> Dict[str, Any]:
    meta = load_project_meta(project_id)
    meta.setdefault("stage_artifacts", {})
    meta["stage_artifacts"][stage] = {
        "files": files,
        "skipped": skipped,
        "at": _dt.datetime.now(_dt.timezone.utc).isoformat().replace('+00:00', 'Z')
    }
    save_project_meta(project_id, meta)
    return meta["stage_artifacts"][stage]

def mark_stage_skipped(project_id: str, stage: str) -> Dict[str, Any]:
    return record_stage_artifacts(project_id, stage, files={}, skipped=True)

# 上传与结果处理
async def save_upload(project_id: str, upload, stage: str = "uploads", dst_name: Optional[str] = None) -> str:
    ensure_project_initialized(project_id)
    sd = stage_dir(project_id, stage)
    name = dst_name or upload.filename
    if not name:
        raise ValueError("Filename is required")
    dst = _safe_join(sd, name)
    with open(dst, "wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return dst

def save_job_meta(project_id: str, meta: Dict[str, Any]) -> None:
    update_project_meta(project_id, patch=meta)

def write_result(project_id: str, payload: Dict[str, Any]) -> None:
    p = result_json_path(project_id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def read_result(project_id: str) -> Optional[Dict[str, Any]]:
    p = result_json_path(project_id)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

# 文件URL与访问
def file_url(project_id: str, stage: str, filename: str) -> str:
    """生成文件访问URL，与路由统一"""
    return f"/hachimi_ai_mad/projects/{project_id}/{stage}/{filename}"

def list_artifacts(project_id: str) -> Dict[str, Any]:
    ensure_project_initialized(project_id)
    root = project_root(project_id)
    stages: Dict[str, Any] = {}
    
    # 扫描目录中的文件
    for stage in os.listdir(root):
        sd = os.path.join(root, stage)
        if not os.path.isdir(sd):
            continue
        files = {}
        for fn in os.listdir(sd):
            full = os.path.join(sd, fn)
            if os.path.isfile(full):
                files[fn] = file_url(project_id, stage, fn)
        if files:
            stages[stage] = {"stage": stage, "files": files}
    
    # 合并元数据中的阶段信息
    meta = load_project_meta(project_id)
    for stg, entry in meta.get("stage_artifacts", {}).items():
        stages.setdefault(stg, {"stage": stg, "files": {}})
        if entry.get("skipped"):
            stages[stg]["skipped"] = True
            stages[stg]["at"] = entry.get("at")
    
    return stages

def serve_file(project_id: str, kind: str, filename: str) -> FileResponse:
    """文件响应接口，参数名与路由统一"""
    sd = stage_dir(project_id, kind)
    fp = _safe_join(sd, filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(fp, filename=os.path.basename(fp))

# 发布功能
def _pub_dir(public_id: str) -> str:
    d = os.path.join(settings.PUBLISH_DIR, public_id)
    os.makedirs(d, exist_ok=True)
    return d

def publish_job(project_id: str) -> Dict[str, Any]:
    """发布任务结果，返回完整JSON"""
    # 查找预览文件
    preview_candidates = []
    for stage in ("preview", "synth", "mix"):
        sd = stage_dir(project_id, stage)
        if not os.path.isdir(sd):
            continue
        for fn in os.listdir(sd):
            if fn.endswith(".wav"):
                preview_candidates.append((stage, fn))
    if not preview_candidates:
        raise FileNotFoundError("no artifacts to publish")
    
    public_id = project_id
    pub = _pub_dir(public_id)
    stage, fn = preview_candidates[0]
    
    # 复制文件到发布目录
    shutil.copy2(os.path.join(stage_dir(project_id, stage), fn), os.path.join(pub, "preview.wav"))
    shutil.copy2(os.path.join(stage_dir(project_id, stage), fn), os.path.join(pub, "result.wav"))
    
    # 构建完整元数据
    project_meta = load_project_meta(project_id)
    meta = {
        "public_id": public_id,
        "project_id": project_id,
        "project_name": project_meta.get("project_name", "Unknown"),
        "pen_name": project_meta.get("pen_name", "Anonymous"),
        "published_at": _dt.datetime.now(_dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
        "preview_url": f"/hachimi_ai_mad/showcase/{public_id}/preview",
        "result_url": f"/hachimi_ai_mad/showcase/{public_id}/result",
        "created_at": project_meta.get("created_at"),
        "is_featured": project_meta.get("is_featured", False)
    }
    
    # 保存发布元数据
    with open(os.path.join(pub, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    return meta

def list_published() -> Any:
    base = settings.PUBLISH_DIR
    if not os.path.isdir(base):
        return []
    items = []
    for pid in os.listdir(base):
        pr = os.path.join(base, pid)
        if not os.path.isdir(pr):
            continue
        meta_file = os.path.join(pr, "meta.json")
        if os.path.exists(meta_file):
            with open(meta_file, "r", encoding="utf-8") as f:
                items.append(json.load(f))
    items.sort(key=lambda m: m.get("published_at") or "", reverse=True)
    return items

def serve_published(public_id: str, filename: str) -> FileResponse:
    """返回已发布项目的文件，参数名统一为public_id"""
    fp = _safe_join(os.path.join(settings.PUBLISH_DIR, public_id), filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(fp, filename=os.path.basename(fp))

def feature_project(project_id: str) -> Dict[str, Any]:
    meta = load_project_meta(project_id)
    meta["is_featured"] = True
    save_project_meta(project_id, meta)
    return meta

def list_recent_projects(limit: int = 40) -> Any:
    base = os.path.join(settings.TEMP_DIR, "projects")
    if not os.path.isdir(base):
        return []
    items = []
    for pid in os.listdir(base):
        pr = os.path.join(base, pid)
        if not os.path.isdir(pr):
            continue
        meta = load_project_meta(pid)
        items.append(meta)
    items.sort(key=lambda m: m.get("created_at") or "", reverse=True)
    return items[:limit]

def list_featured_projects(limit: int = 40) -> Any:
    featured = [m for m in list_recent_projects(1000) if m.get("is_featured")]
    return featured[:limit]