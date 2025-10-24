# 环境要求

- Windows 10/11（64 位）
- Python 3.11（64 位，安装时务必勾选「Add python.exe to PATH」）
- 可选：`Poetry`（依赖管理，执行 `pip install poetry` 安装）、`Docker Desktop`（全栈模式需用）

## 快速启动

### 方法 A：本地运行（无 Redis，任务同步执行）

适合快速验证流程，无需额外服务。

1. **获取代码**

   ```powershell
   git clone <你的仓库地址> hachimi_ai_mad
   cd hachimi_ai_mad
   ```

2. **安装依赖并启动**

   ```powershell
   # 用 Poetry 安装（推荐）
   poetry install

   # 创建数据目录
   mkdir -Force data\temp data\publish

   # 设置环境变量并启动 API
   $env:CELERY_EAGER=1; $env:TEMP_DIR="$PWD\data\temp"; $env:PUBLISH_DIR="$PWD\data\publish"
   poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. **验证启动**
   浏览器访问 `http://127.0.0.1:8000/livez`，返回 `{"ok": true}` 即成功。

### 方法 B：Docker 全栈（含 Redis + Celery Worker）

适合需要观察异步任务队列的场景。

1. **启动 Docker Desktop**
   确保 WSL2 已启用（Docker 会自动引导配置）。

2. **一键启动所有服务**

   ```powershell
   docker compose up --build
   ```

3. **验证启动**
   浏览器访问 `http://127.0.0.1:8000/docs`，可通过 Swagger 调试 API。

## 替代方案（不用 Poetry）

若不想用 Poetry，可通过 `venv + pip` 安装依赖：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn python-multipart celery
# 之后按“方法 A”设置环境变量并启动 uvicorn
```

## 常见问题

- **端口冲突**：修改启动命令中的 `--port`（本地）或 Docker Compose 的 `ports` 映射。
- **依赖安装慢**：配置国内 PyPI 镜像源（如清华源）后再执行 `poetry install` 或 `pip install`。
- **任务状态异常**：确保 `CELERY_EAGER` 环境变量正确设置（本地模式需设为 `1`）。

