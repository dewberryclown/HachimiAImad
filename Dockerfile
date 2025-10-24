# 基础镜像
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装系统依赖（如需 ffmpeg/demucs 再加）
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# 复制项目与依赖
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install "poetry>=1.7,<2"
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi

COPY . .

EXPOSE 8000

# 默认启动 API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
