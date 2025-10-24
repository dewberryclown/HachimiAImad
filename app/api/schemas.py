from typing import Optional, List
from pydantic import BaseModel, Field

# 原有模型
class StatusResp(BaseModel):
    job_id: str
    status: str = Field(description="PENDING|STARTED|PROGRESS|SUCCEEDED|FAILED")
    message: Optional[str] = None
    progress: Optional[float] = None

class ProcessResponse(BaseModel):
    job_id: str
    status_url: str
    download_url: str

class PublishResponse(BaseModel):
    public_id: str
    project_name: str
    pen_name: str
    preview_url: str
    result_url: str
    published_at: str

class ShowcaseItem(BaseModel):
    public_id: str
    project_name: str
    pen_name: str
    preview_url: str
    published_at: str

class ShowcaseList(BaseModel):
    items: List[ShowcaseItem]

# 新增管理与阶段接口请求体
class FeatureProjectRequest(BaseModel):
    project_id: str
    admin_secret: str

class SynthesizeRequest(BaseModel):
    project_id: str
    format: str = "wav"
    allow_missing: bool = False
    force: bool = False
    use_custom_midi: bool = False