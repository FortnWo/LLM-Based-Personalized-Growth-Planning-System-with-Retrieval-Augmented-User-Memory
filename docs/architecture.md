# 架构总览

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vue Router、Axios、Vite、ECharts |
| 后端 | FastAPI、SQLAlchemy 2、Pydantic v2、Passlib、PyJWT |
| 数据库 | MySQL 8；可选 Qdrant 向量索引 |
| AI 集成 | OpenAI SDK 与兼容提供方；可选 Embedding API（UKL 记忆事实检索） |

## 高层设计

```text
Vue SPA
    -> API wrappers (src/api)
    -> Axios client with bearer interceptor
    -> WebSocket channel (/ws) for push events
    -> FastAPI routers
    -> Service layer
    -> SQLAlchemy models
    -> MySQL

  UKL memory facts
    -> Embedding API
    -> MySQL memory_embedding (可重建元数据)
    -> Qdrant memory_facts collection (可选检索索引)

后台 AI 任务 (ai_worker 线程池)
    -> chat / goal breakdown / action plan / profile / UKL 投影
    -> 完成后通过 event_bus 触发成长周期编排器

成长周期编排器 (growth_cycle_orchestrator)
    -> 监听领域事件 (ON_GROWTH_UPDATED 等)
    -> 串联里程碑反馈、模式分析、画像刷新等 UKL 写路径
```

后端采用分层设计：

- Routers：请求解析、响应模型、HTTP 错误映射。
- Services：业务规则、校验、与权限敏感逻辑。
- Models：持久化实体。
- Schemas：请求 / 响应契约。
- Core：配置、数据库连接、JWT / 密码工具、启动初始化、AI 线程池、事件总线、WebSocket 管理。
- Workflows：跨模块领域事件编排（成长周期）。

## 后端模块

### Core

- `app/core/config.py`：由环境变量驱动的配置（含 UKL 开关与各类系统提示词）。
- `app/core/database.py`：引擎、会话、声明式基类。
- `app/core/schema_bootstrap.py`：启动时幂等补齐缺失表 / 列（迁移 005–009）。
- `app/core/security.py`：密码哈希、JWT 创建 / 解析、认证依赖、`require_admin` 权限检查。
- `app/core/bootstrap.py`：可选的启动管理员初始化。
- `app/core/ai_worker.py`：后台 AI 任务线程池与 `submit_ai_task`。
- `app/core/event_bus.py`、`app/core/domain_events.py`：进程内领域事件发布。
- `app/core/ws_manager.py`：内存型 WebSocket 连接管理器（按用户连接）。

### Services（主要）

| 模块 | 职责 |
| --- | --- |
| `auth_service` | 登录流程与令牌响应 |
| `user_service` | 用户 CRUD、委托权限、批量导入 / 重置密码 |
| `chat_service` | 会话 / 消息持久化、后台 LLM 交互、停止生成、WebSocket 通知 |
| `chat_context_service` | UKL 启用时的聊天上下文组装 |
| `profile_service` / `trait_service` | 用户画像与特质洞察 |
| `goal_service` / `breakdown_service` | 目标与 AI 拆解 |
| `action_plan_service` / `plan_service` | 行动计划生成与条目更新 |
| `growth_service` / `growth_record_service` / `growth_summary_service` | 成长记录、统计、周总结 |
| `ukl_service` 及 `ukl_*` 系列 | UKL 切片读写、投影、叙事、模式、里程碑、记忆事实 |
| `ai_service` | LLM / Embedding 调用封装 |
| `vector_store` | 可选 Qdrant collection、用户过滤、upsert、查询和健康检查 |
| `system_config_service` / `notify_service` / `verification_service` | 管理后台配置、通知与验证码 |
| `ai_rate_limit_service` | 聊天 AI 限流 |
| `admin_tool_service` | 管理助手工具调用 |

### Routers

| 路由文件 | 前缀 | 说明 |
| --- | --- | --- |
| `health.py` | `/ping` | 健康检查 |
| `auth.py` | `/auth` | 登录与当前用户 |
| `password_reset.py` | `/auth/password-reset` | 忘记密码（验证码 + 重置） |
| `info.py` | `/info` | 当前用户身份信息 |
| `profile.py` | `/profile` | 用户画像与洞察 |
| `chat.py` | `/chat` | 聊天发送 / 列表 / 停止 / 会话管理 |
| `goal.py` | `/goals` | 目标与拆解 |
| `action_plan.py` | `/action-plans` | 行动计划 |
| `growth_record.py` | `/growth-records` | 成长记录与周总结 |
| `user.py` | `/admin/users` | 管理员用户管理与批量操作 |
| `admin_system.py` | `/admin/system` | AI 配置、通知、限流、日志 |
| `ws.py` | `/ws` | 实时聊天推送 |

### Workflows

- `app/workflows/growth_cycle_orchestrator.py`：在应用 lifespan 中初始化，订阅 `ON_GROWTH_UPDATED` 等领域事件，触发 UKL 反馈写路径（里程碑祝贺、模式分析、周总结投影等）。

## UKL（用户知识层）

当 `UKL_ENABLED=true` 时，系统在多个业务场景中写入与读取 `ukl_slice` 表中的结构化切片，并在生成 Prompt 前动态组装上下文。主要切片类型包括会话摘要、拆解叙事、执行切片、成长日志投影、跨会话叙事、记忆事实等。

记忆事实的权威数据保存在 MySQL 的 `ukl_slice`；`memory_embedding` 保存模型、维度和 JSON 向量基线。启用 `VECTOR_STORE_ENABLED=true` 且 backend 为 `qdrant` 后，事实会以 `ukl_slice.id` 作为 point ID 写入 Qdrant `memory_facts` collection。查询强制使用 `user_id` payload filter，Qdrant 不可用时依次回退到 MySQL JSON cosine 和关键词检索，因此向量索引不是业务数据的唯一来源。

Embedding 模型变更或维度变更时应使用新的 collection 并执行回填，不得在同一 collection 中混用不同向量空间。回填入口为 `backend/scripts/reindex_memory_facts.py`。

详细设计与落地进度见 `docs/rag-external-memory/`。

## 聊天交付流程

1. `POST /chat` 同步持久化用户消息并立即返回。
2. 后台任务创建助手占位消息（`pending`）并启动心跳推送。
3. LLM 在后台生成完成后，会更新同一条助手记录为最终内容。
4. 后端通过 WebSocket 推送 `new_message`，前端替换占位内容。
5. 用户可调用 `POST /chat/{session_id}/messages/{message_id}/stop` 取消进行中的生成。

消息状态语义：

- `pending`：尚未完成的助手占位消息。
- `completed`：助手回复生成成功。
- `failed`：助手生成失败，已保存兜底错误文本。

## 认证与 RBAC

- 受保护接口使用 JWT Bearer 认证。
- 用户角色：
  - `user`：普通学生账号。
  - `admin`：管理员账号。
- 管理员权限模型：
  - `full`：不受限制的管理员操作（可访问 `/admin/system` 等）。
  - `limited`：由权限键限定范围。
- 管理员路由使用的权限键：
  - `user.read`
  - `user.create`
  - `user.update`
  - `user.delete`
  - `admin.grant`
- 委托权限可配置可选过期时间。

## 领域规则

- 学生账号用户名必须匹配 10 位数字学号。
- 学生账号不能创建为管理员权限。
- 有限管理员至少需要一个权限键。

## 接口面

### 公共接口

- `GET /ping`
- `POST /auth/login`
- `GET /auth/password-reset/available-methods`
- `POST /auth/password-reset/send-code`
- `POST /auth/password-reset/verify`
- `POST /auth/password-reset/confirm`

### 登录后接口

- `GET /auth/me`
- `GET /info/me`、`PUT /info/me`、`PATCH /info/me/password`
- `GET /profile/me`、`GET /profile/me/insights`、`PUT /profile/me`、`POST /profile/me/refresh-from-chat`
- `POST /chat`、`POST /chat/{session_id}/messages/{message_id}/stop`
- `GET /chat/sessions`、`GET /chat/{session_id}/messages`
- `PATCH /chat/{session_id}`、`DELETE /chat/{session_id}`
- `POST /goals`、`GET /goals`、`GET /goals/{goal_id}`、`PUT /goals/{goal_id}`
- `POST /goals/{goal_id}/refresh-breakdown`、`POST /goals/{goal_id}/reschedule`、`DELETE /goals/{goal_id}`
- `POST /action-plans`、`GET /action-plans`、`GET /action-plans/{plan_id}`
- `PATCH /action-plans/{plan_id}/items/{item_id}`、`POST /action-plans/{plan_id}/refresh`、`DELETE /action-plans/{plan_id}`
- `POST /growth-records`、`GET /growth-records`、`GET /growth-records/stats`
- `GET /growth-records/trend/daily`、`POST /growth-records/summary/generate`
- `GET /growth-records/summary/latest`、`GET /growth-records/{record_id}`

### 实时接口

- `WS /ws?token=<jwt>`

### 管理员专属接口

- `GET/POST /admin/users`、`GET/PUT/DELETE /admin/users/{user_id}`
- `PATCH/DELETE /admin/users/{user_id}/admin-access`
- `POST /admin/users/bulk-reset-password`、`POST /admin/users/import`
- `/admin/system/*`：AI 配置、LLM 预设、通知、限流、验证码、错误日志与用量统计

完整路径列表见根目录 `README.md`。

## 前端路由与守卫

| 路径 | 访问要求 |
| --- | --- |
| `/login`、`/forgot-password` | 仅游客 |
| `/home` | 需登录（登录后默认首页） |
| `/chat`、`/info`、`/profile`、`/plan`、`/growth` | 需登录 |
| `/admin/users` | 需登录且具备 `user.read` 或完整管理员 |
| `/admin/users/:userId/usage` | 需完整管理员 |
| `/admin/system` | 需完整管理员 |

路由守卫会从本地存储恢复认证状态，并在需要时校验 `/auth/me`。完整管理员登录后默认跳转 `/admin/users`，普通用户跳转 `/home`。

## 启动生命周期

FastAPI 使用 lifespan 钩子来：

1. 创建数据库表（`Base.metadata.create_all`），
2. 幂等补齐关键迁移（`ensure_database_schema`），
3. 在配置了初始化环境变量时创建 bootstrap 管理员，
4. 初始化成长周期编排器（`initialize_growth_cycle_orchestrator`），
5. 将主 asyncio 事件循环挂到 WebSocket 管理器上，以便跨线程调度推送。

这能保持本地 / 开发启动一致，并避免使用已弃用的 startup 事件钩子。

## 日志

- 5xx 响应与未捕获异常写入项目根目录 `logs/error.log`（`RotatingFileHandler`，单文件约 1 MB，保留 5 个备份）。
- 管理员可通过 `GET /admin/system/logs/error` 在线查看。
