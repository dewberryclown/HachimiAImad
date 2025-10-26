from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field #用于字段约束

class Settings(BaseSettings):
    #配置元信息:指定从.env文件加载,忽略未定义的环境变量
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    APP_NAME: str = "HachimiAImad"
    ENV: str = "dev"#环境标识:开发
    
    TEMP_DIR: str="/tmp/hachimi_ai_mad"
    RESULT_TTL_HOURS: int = Field(default=24, ge=1, le=169)
    
    PUBLISH_DIR: str = "/var/hachimi_ai_mad/published"
    PUBLISHED_TTL_DAYS: int | None = None
    
    MAX_UPLOAD_MB: int = 32
    
    REDIS_URL: str = "redis://localhost:6379/0"#默认redis连接地址
    #celery消息代理及结果后端地址
    BROKER_URL: str | None = None
    BACKEND_URL: str | None = None
    #动态获取消息代理及结果后端地址
    @property
    def broker_url(self): return self.BROKER_URL or self.REDIS_URL
    @property
    def backend_url(self): return self.BACKEND_URL or self.REDIS_URL
    #管理员密钥
    ADMIN_SECRET: str | None = None
    
    CELERY_TASK_TIME_LIMIT: int = Field(default=300, ge=30, le=3600)
    CELERY_WORKER_CONCURRENCY: int = Field(default=2, ge=1, le=64)
    # 测试方便：是否同步执行（pytest里也会 monkeypatch）
    CELERY_EAGER: int = 1
    
settings = Settings()
    