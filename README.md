# Poetry / Python 环境 & 测试

## 安装依赖（使用 pyproject.toml）

poetry install

## 运行 E2E / 单测

poetry run pytest -q tests/test_e2e.py
poetry run pytest -q tests/test_validations.py

## （可选）语法快检，能立刻发现粘贴截断/… 的问题

poetry run python -m compileall -q app

## （开发）本地热启动 API

poetry run uvicorn app.main:app --reload
（如果临时用 pip 调包时用到过）

powershell
复制
编辑

## Windows 指定解释器装包

py -3.11 -m pip install -U python-multipart

## 或（非首选）系统 pip

pip install -U python-multipart
（临时把环境变量打到当前 PowerShell 会话）

$env:CELERY_EAGER = "1"
$env:REDIS_URL = "memory://"
Docker / Compose

## 手动拉基础镜像（验证网络/镜像源）

docker pull python:3.11-slim

## （排错时）也拉一个小镜像测试网络

docker pull busybox

## 构建并启动（compose v2）

docker compose up --build

## 只构建（强制更新、无缓存）

docker compose build --no-cache --pull

## 清理构建缓存

docker builder prune -f

## （可选）直接构建镜像

docker build -t hachimi-api .

## （可选）强制平台为 linux/amd64

docker build --platform linux/amd64 -t hachimi-api .

## 登录 Docker Hub（减少匿名限流/鉴权问题）

docker login

## 退出登录

docker logout
容器冒烟检查：

## 健康检查（你加了 /healthz 后）

curl <http://localhost:8000/healthz>
Docker Engine 镜像源（加速器）配置
打开 Docker Desktop → Settings → Docker Engine，把 registry-mirrors 写入 JSON，保存并 Restart。

{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ],
  "dns": ["8.8.8.8","1.1.1.1"]
}
（如果你在 compose 里曾见到 version: 已过时的警告，直接删掉 version: 字段即可。）

WSL / 网络小修（仅在网络异常时用过）
powershell
复制
编辑

## 关闭 WSL、重置 Winsock（网络栈）

wsl --shutdown
netsh winsock reset
运行/配置关键点备忘
测试本机：CELERY_EAGER=1，且在 EAGER 分支使用 broker_url="memory://", result_backend="cache+memory://", task_store_eager_result=True（已写进 celery_app.py）。

Docker/Compose：.env 里 CELERY_EAGER=0、REDIS_URL=redis://redis:6379/0；docker compose up --build 启动 api + worker + redis。

基础镜像：最终选用 python:3.11-slim（你本机已能直接 docker pull 成功）。

排错套路：docker compose build --no-cache --pull → 仍不行就 docker builder prune -f → 指定 --platform linux/amd64 → 检查镜像源/登录。
