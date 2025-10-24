from fastapi import FastAPI
from app.core.logging import setup_logging
from app.api.routes import router as api_router

setup_logging()
app = FastAPI(title="hachimi_ai_mad")

# 健康检查
@app.get("/livez")
def livez():
    return {"ok": True}

# 业务路由
app.include_router(api_router)