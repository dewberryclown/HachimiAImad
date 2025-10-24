# 2025.10.24技术日志 -----by dewberry(zmzll)

## 一、概要

### 核心信息

- **目标**：打通“上传音频→触发处理→查询状态→下载结果→发布/展示→项目直链”后端闭环。
- **技术栈**：FastAPI + Pydantic(v2)、Celery、内存broker/backend（测试）、本地磁盘存储。
- **成果**：E2E测试全绿（2 passed），本地测试无Redis依赖；路由与存储目录规范统一，支持发布与展示。

## 二、实现清单（功能点）

1. **任务提交**：`/hachimi_ai_mad/tasks/process`
   - 接收表单（`file`、`bpm`、`project_name`、`pen_name`），校验MIME（`audio/*`）与BPM。
   - 保存文件至`TEMP_DIR/projects/{project_id}/uploads/`。
   - 提交Celery任务（`task_id=project_id`），返回`job_id`/`status_url`/`download_url`。

2. **任务状态**：`/hachimi_ai_mad/tasks/{job_id}/status`
   - 统一状态语义：`SUCCESS`→`SUCCEEDED`，`FAILURE`→`FAILED`，其余（`PENDING`/`STARTED`/`PROGRESS`）保持原样。

3. **结果下载**：`/hachimi_ai_mad/tasks/{job_id}/download`
   - 读取`result.json`，返回`preview_url`/`result_url`（项目内直链）。

4. **项目产物列表**：`/hachimi_ai_mad/projects/{project_id}/artifacts`
   - 扫描`separate/`、`midi/`、`lyrics/`、`synth/`、`preview/`、`mix/`、`uploads`目录，合并`meta["stage_artifacts"]`。

5. **项目文件直链**：`/hachimi_ai_mad/projects/{project_id}/{stage}/{filename}`
   - 经`_safe_join`保护，直接返回`FileResponse`。

6. **发布与展示**
   - POST `/{job_id}/publish`：拷贝`synth`与`preview`产物至`PUBLISH_DIR/{public_id}/`，返回公开URL。
   - GET `/hachimi_ai_mad/showcase`、`/showcase/{public_id}/preview|result`。

7. **元数据与精选**
   - `meta.json`包含：`project_id`/`created_at`/`is_featured`/`stage_artifacts`/`published`。
   - 支持`feature_project()`及列表接口（`recent`/`featured`）。

## 三、关键设计决策

1. **ID统一**：`task_id == project_id`，避免因ID不一致导致的`/download` 404和状态查询异常。
2. **测试环境无Redis依赖**：`CELERY_EAGER=1`时使用内存`broker`/`result_backend`，并开启`task_store_eager_result=True`，确保`AsyncResult`能获取最终状态。
3. **状态语义映射**：将Celery的`SUCCESS`/`FAILURE`映射为API的`SUCCEEDED`/`FAILED`，对齐业务表达。
4. **路径/路由口径统一**：文件直链与路由统一为`/hachimi_ai_mad/projects/{project_id}/{stage}/{filename}`。
5. **阶段命名统一**：全局替换阶段名为`separate`，规避“`seperate`”拼写错误导致的双目录问题。
6. **避免递归**：`ensure_project_initialized()`与`save_project_meta()`互不调用，防止`RecursionError`。

## 四、踩坑与解决方案

- ❌ **python-multipart 依赖环境冲突**：Anaconda与系统Python混用导致依赖检测异常，执行`pytest`时提示“`python-multipart`未安装”（即使已`pip`安装）  
  ✅ 解决：改用**Poetry统一环境**，将`python-multipart`写入`pyproject.toml`，通过`poetry install`确保依赖版本和环境一致性。
- ❌ **递归深度超限（RecursionError）**：调用`project_root`等文件操作函数时，因`ensure_project_initialized()`与`save_project_meta()`相互递归，触发“`maximum recursion depth exceeded`”  
  ✅ 解决：修改元数据初始化逻辑，写`meta.json`时仅执行`os.makedirs`和文件写入操作，不再反向调用`ensure_project_initialized()`。
- ❌ **Celery 与 Redis 连接失败**：日志持续输出“`Connection to Redis lost`”，重试超限后任务执行失败  
  ✅ 解决：测试环境配置`CELERY_EAGER=1`、`broker="memory://"`、`result_backend="cache+memory://"`；开发/容器环境检查Redis服务启动状态与`REDIS_URL`配置。
- ❌ **响应验证失败（ResponseValidationError）**：`process`接口返回值缺少`status_url`或`download_url`，触发FastAPI响应验证错误  
  ✅ 解决：确保`process`接口完整返回`job_id`、`status_url`、`download_url`三字段，严格对齐Pydantic模型`ProcessResponse`定义。
- ❌ **任务状态与下载接口断言失败**：任务状态长期停留在`PROGRESS`，下载接口返回404  
  ✅ 解决：统一`task_id=project_id`；测试环境开启`task_store_eager_result=True`并使用内存`result_backend`；统一文件路由为`/projects/...`，修正`file_url()`路径生成逻辑。
- ❌ **导入失败/语法错误**：上传或粘贴代码时出现`...`占位或半截行，导致导入/语法错误  
  ✅ 解决：统一使用完整文件/压缩包；通过`python -m compileall -q app`预检语法。
- ❌ **Settings缺字段**：`CELERY_WORKER_CONCURRENCY`等字段找不到  
  ✅ 解决：在`Settings`中补齐字段并统一大写命名；引用时使用`settings.CELERY_...`。
- ❌ **send_task + EAGER不生效**：日志警告“`AlwaysEagerIgnored`”  
  ✅ 解决：改用`run_pipeline_task.apply_async(...)`。
- ❌ **函数/任务重名导致递归**：`run_pipeline_stub`任务与导入名重复，触发递归  
  ✅ 解决：导入时改别名`_run_pipeline_stub`，任务函数命名为`run_pipeline_task`。
- ❌ **MIME/字段名不匹配**：表单字段或MIME类型与接口定义不一致，触发415/422错误  
  ✅ 解决：表单固定字段名为`file`，MIME判断规则设为`audio/*`。

## 五、目录与数据规范

### 1. 目录结构

- **项目根路径**：`{TEMP_DIR}/projects/{project_id}/`  
  子目录：`uploads/`、`separate/`、`midi/`、`lyrics/`、`synth/`、`preview/`、`mix/`、`pub/`  
  核心文件：`meta.json`、`result.json`
- **发布区路径**：`{PUBLISH_DIR}/{public_id}/`  
  产物：`preview.wav`、`result.wav`

### 2. 公网URL

- 项目文件直链：`/hachimi_ai_mad/projects/{project_id}/{stage}/{filename}`
- 展示区URL：`/hachimi_ai_mad/showcase/{public_id}/preview|result`

## 六、配置与环境（要点）

### 1. 测试环境（本地）

- 核心配置：`CELERY_EAGER=1`、`broker="memory://"`、`result_backend="cache+memory://"`、`task_store_eager_result=True`。
- 路径隔离：`pytest`中指定`TEMP_DIR`/`PUBLISH_DIR`为`tmp_path`，避免污染本地环境。

### 2. 开发/容器环境

- `.env`配置：`CELERY_EAGER=0`、`REDIS_URL=redis://redis:6379/0`。
- `docker-compose`：包含`api`、`worker`、`redis`服务；挂载`./data/tmp`（临时文件）和`./data/publish`（发布产物）。
- 健康检查：GET `/healthz`返回`{"ok": true}`（已建议添加）。

## 七、测试策略

1. **单元测试**：针对`validators.validate_bpm`，覆盖类型校验与边界值场景。
2. **E2E测试**：覆盖两条核心路径
   - 路径1：`process`→`status(SUCCEEDED)`→`download`→`publish`→`showcase`→`project file`
   - 路径2：`midi/lyrics`上传→`separate`重试→`synth`重试→`artifacts`查询
3. **冒烟测试（容器）**：验证`/healthz`返回200；`CELERY_EAGER=0`时，`worker`能正常获取并执行任务。

## 八、已知风险 & 规避

1. **路径穿越风险**：所有文件直链均通过`_safe_join`校验，防止越权访问。
2. **磁盘膨胀风险**：未来需实现过期清理策略（按`RESULT_TTL_HOURS`/`PUBLISHED_TTL_DAYS`）。
3. **接口变更风险**：调整既有路由/字段前，将提供迁移策略（如别名路由+旧字段兼容窗口）。
