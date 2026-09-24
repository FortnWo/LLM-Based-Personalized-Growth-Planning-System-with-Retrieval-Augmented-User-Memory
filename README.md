# 基于大语言模型与检索增强用户记忆的大学生成长规划智能系统

一个面向大学生与管理员的全栈导师平台，提供基于角色的访问控制、临时委托管理员权限、成长规划（目标拆解 / 行动计划 / 成长记录），以及通过 OpenAI 兼容提供方实现的 AI 聊天支持。可选启用 UKL（用户知识层）以在聊天与规划场景中组装跨会话记忆上下文。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vue Router、TypeScript、Vite、Axios、ECharts |
| 后端 | FastAPI、SQLAlchemy 2、Pydantic v2 |
| 数据库 | MySQL 8（或兼容实现） |
| AI 提供方 | OpenAI 兼容 API（通过环境变量或管理后台配置） |

## 核心功能

- JWT 登录与前端会话恢复；忘记密码流程（短信 / 邮件验证码）。
- 管理员管理用户全生命周期（创建 / 列表 / 更新 / 删除 / Excel 批量导入 / 批量重置密码）。
- 学生账号约束：用户名必须是 10 位学号。
- 角色模型：`user` 与 `admin`。
- 委托管理员权限支持：
  - 完整管理员权限，或
  - 有限权限键与可选过期时间。
- 当前用户身份信息自助 API（`/info/me`）。
- 用户画像 API（`/profile/me`）与特质洞察 API（`/profile/me/insights`）。
- AI 聊天会话与消息历史；支持停止生成、重命名与删除会话。
- 非阻塞聊天流程：用户消息立即落库，助手回复在后台生成。
- 通过 WebSocket（`/ws`）推送助手实时更新，并提供轮询兜底。
- 明确的助手消息状态语义：`pending`、`completed`、`failed`。
- 成长规划：目标创建与 AI 拆解、行动计划生成与条目更新、目标重排期。
- 成长记录：打卡 / 日记、统计与趋势、AI 周总结。
- UKL（用户知识层，可选）：画像双写、会话摘要、记忆事实抽取与向量检索、跨会话叙事等（`UKL_ENABLED=true` 时生效）。
- 成长周期编排器：基于领域事件串联画像刷新、里程碑反馈、模式分析等后台任务。
- 管理员系统面板：AI 配置、LLM 预设、通知（短信 / SMTP）、限流与验证码策略、错误日志与 AI 用量统计。
- 后端 5xx 错误记录到项目根目录 `logs/error.log`。

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 20+
- MySQL 8+

### 1. 初始化数据库

全新安装（推荐）：

```bash
mysql -u root -p < database/schema.sql
```

`schema.sql` 已包含当前版本所需的全部表结构（含 UKL、`memory_embedding` 等）。

若数据库在较早版本创建，可按顺序执行增量迁移；或在启动后端时由 `ensure_database_schema` 自动补齐缺失表 / 列（当前自动处理 005–009）：


缺少 `users.risk_flag` 等列时，依赖用户表的 API 会返回 500（日志中为 SQLAlchemy `OperationalError` / e3q8），前端表现为请求超时或失败。

### 2. 启动后端

```bash
cd backend

python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env

uvicorn app.main:app --reload --reload-exclude "logs/*" --port 8000
```

Swagger UI：http://localhost:8000/docs

运行后端测试：

```bash
pip install -r requirements-dev.txt
pytest -q
```

### 3. 启动前端

```bash
cd frontend

npm install
cp .env.example .env

npm run dev
```

前端地址：http://localhost:5173

生产构建：

```bash
npm run build
```

## 环境变量

`backend/.env` 中的重要后端变量：

- `DATABASE_URL`：SQLAlchemy 连接串。
- `DB_POOL_SIZE`、`DB_MAX_OVERFLOW`、`DB_POOL_TIMEOUT`：连接池参数。
- `AI_BACKGROUND_MAX_WORKERS`：后台 AI 任务线程池大小。
- `ALLOWED_ORIGINS`：CORS 的 JSON 数组，例如 `["http://localhost:5173"]`。
- `AUTH_SECRET_KEY`：JWT 签名密钥（生产环境必须更改）。
- `AUTH_ACCESS_TOKEN_EXPIRES_MINUTES`：令牌过期时间（分钟）。
- `LLM_API_KEY`、`LLM_API_BASE_URL`、`LLM_MODEL`：AI 提供方配置（也可在管理后台覆盖）。
- `LLM_SYSTEM_PROMPT`、`ADMIN_LLM_SYSTEM_PROMPT`：聊天 / 管理助手系统提示词（优先级：管理后台 DB 配置 > `.env` > `config.py` 默认值）。
- `RUN_LIVE_AI_TESTS`：设为 `1` 后启用真实 AI 集成测试。
- `GOAL_BREAKDOWN_ENABLED`：启用 / 禁用目标拆解生成接口。
- `ACTION_PLAN_ENABLED`：启用 / 禁用行动计划生成接口。
- `UKL_ENABLED`：启用 UKL 画像双写与聊天 / 拆解 / 行动计划上下文组装；详见 `docs/rag-external-memory/`。
- `MEMORY_FACT_*`、`EMBEDDING_MODEL`：记忆事实抽取与向量检索（需提供方支持 `/embeddings`）。
- `BOOTSTRAP_ADMIN_USERNAME`、`BOOTSTRAP_ADMIN_EMAIL`、`BOOTSTRAP_ADMIN_PASSWORD`、`BOOTSTRAP_ADMIN_FULL_NAME`：
  可选的启动初始化管理员；配置后，后端会在不存在时创建该管理员。

更多 UKL 相关开关（会话摘要、执行切片、成长日志、里程碑反馈、模式分析、跨会话叙事等）见 `backend/.env.example` 与 `app/core/config.py`。

前端变量：

- `VITE_API_BASE_URL`：后端基础地址，默认 `http://localhost:8000`。
- `VITE_WS_BASE`：可选的 WebSocket 基础地址（用于开发 / 代理自定义）。

## 接口总览

### 公共接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/ping` | 健康检查 |
| POST | `/auth/login` | 登录并获取 JWT |
| GET | `/auth/password-reset/available-methods` | 查询已配置的找回密码方式 |
| POST | `/auth/password-reset/send-code` | 发送验证码 |
| POST | `/auth/password-reset/verify` | 校验验证码，获取一次性令牌 |
| POST | `/auth/password-reset/confirm` | 使用令牌重置密码 |

### 登录后接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/auth/me` | 获取当前用户 |
| GET | `/info/me` | 获取我的身份信息 |
| PUT | `/info/me` | 更新我的身份信息 |
| PATCH | `/info/me/password` | 修改我的密码 |
| POST | `/chat` | 发送消息；立即返回会话和用户消息，助手回复异步生成 |
| POST | `/chat/{session_id}/messages/{message_id}/stop` | 停止正在生成的助手消息 |
| GET | `/chat/sessions` | 列出当前登录用户的聊天会话 |
| GET | `/chat/{session_id}/messages` | 列出该会话的消息 |
| PATCH | `/chat/{session_id}` | 重命名聊天会话 |
| DELETE | `/chat/{session_id}` | 删除聊天会话 |
| GET | `/profile/me` | 获取用户画像（缺失时自动创建） |
| GET | `/profile/me/insights` | 获取画像特质洞察 |
| PUT | `/profile/me` | 更新用户画像 |
| POST | `/profile/me/refresh-from-chat` | 根据聊天历史重建用户画像 |

### 成长规划（登录后）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/goals` | 创建目标并触发异步 AI 拆解 |
| GET | `/goals` | 列出当前用户的目标 |
| GET | `/goals/{goal_id}` | 获取带拆解树的目标详情 |
| PUT | `/goals/{goal_id}` | 更新目标元数据 |
| POST | `/goals/{goal_id}/refresh-breakdown` | 异步重新生成 AI 目标拆解 |
| POST | `/goals/{goal_id}/reschedule` | 异步重排目标时间线 |
| DELETE | `/goals/{goal_id}` | 删除目标及相关拆解节点 |
| POST | `/action-plans` | 为某个目标创建或复用进行中的行动计划 |
| GET | `/action-plans` | 列出当前用户的行动计划 |
| GET | `/action-plans/{plan_id}` | 获取行动计划详情 |
| PATCH | `/action-plans/{plan_id}/items/{item_id}` | 更新行动计划条目状态 / 进度 |
| POST | `/action-plans/{plan_id}/refresh` | 异步刷新行动计划 |
| DELETE | `/action-plans/{plan_id}` | 删除行动计划 |

### 成长记录（登录后）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/growth-records` | 创建成长记录 |
| GET | `/growth-records` | 分页列出成长记录 |
| GET | `/growth-records/stats` | 获取统计摘要 |
| GET | `/growth-records/trend/daily` | 获取日趋势数据 |
| POST | `/growth-records/summary/generate` | 异步生成周总结 |
| GET | `/growth-records/summary/latest` | 获取最近一次周总结 |
| GET | `/growth-records/{record_id}` | 获取单条成长记录 |

### WebSocket

| 协议 | 路径 | 说明 |
| --- | --- | --- |
| WS | `/ws?token=<jwt>` | 用于推送正在输入 / 新助手消息的实时通道 |

典型推送事件：

- `typing`：`{ "type": "typing", "session_id": number, "message_id": number, "status": "pending" }`
- `new_message`：`{ "type": "new_message", "message": { "id": number, "session_id": number, "role": "assistant", "content": string, "status": "completed|failed", "created_at": string } }`

### 管理员专属

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/users` | 列出用户 |
| POST | `/admin/users` | 创建用户 / 管理员 |
| GET | `/admin/users/{user_id}` | 获取用户 |
| PUT | `/admin/users/{user_id}` | 更新用户 |
| DELETE | `/admin/users/{user_id}` | 删除用户 |
| PATCH | `/admin/users/{user_id}/admin-access` | 授予 / 更新管理员委托 |
| DELETE | `/admin/users/{user_id}/admin-access` | 撤销委托管理员权限 |
| POST | `/admin/users/bulk-reset-password` | 批量重置密码 |
| POST | `/admin/users/import` | 从 Excel 批量导入学生账号 |
| GET | `/admin/system/ai-config` | 读取 AI 运行时配置 |
| PUT | `/admin/system/ai-config` | 更新 AI 运行时配置 |
| GET | `/admin/system/llm-presets` | 列出 LLM 预设 |
| POST | `/admin/system/llm-presets` | 创建 LLM 预设 |
| DELETE | `/admin/system/llm-presets/{preset_id}` | 删除 LLM 预设 |
| POST | `/admin/system/llm-presets/{preset_id}/activate` | 激活 LLM 预设 |
| GET | `/admin/system/notify-config` | 读取通知配置 |
| PUT | `/admin/system/notify-config/sms` | 更新短信配置 |
| PUT | `/admin/system/notify-config/smtp` | 更新邮件配置 |
| GET | `/admin/system/rate-limit-config` | 读取 AI 限流配置 |
| PUT | `/admin/system/rate-limit-config` | 更新 AI 限流配置 |
| GET | `/admin/system/verification-config` | 读取验证码策略 |
| PUT | `/admin/system/verification-config` | 更新验证码策略 |
| GET | `/admin/system/logs/error` | 读取后端错误日志 |
| GET | `/admin/system/logs/usage` | 读取 AI 用量统计 |
| GET | `/admin/system/logs/usage/debug` | 调试用用量明细 |

## 权限键

有限管理员当前可用的权限键：

- `user.read`
- `user.create`
- `user.update`
- `user.delete`
- `admin.grant`

## 项目结构

```text
LLM-Based-Personalized-Growth-Planning-System-with-Retrieval-Augmented-User-Memory/
├── backend/
│   ├── app/
│   │   ├── core/       # 配置、安全、数据库、AI 线程池、事件总线、WebSocket
│   │   ├── models/     # SQLAlchemy ORM 模型
│   │   ├── routers/    # FastAPI 路由处理器
│   │   ├── schemas/    # Pydantic DTO
│   │   ├── services/   # 业务服务（auth、user、chat、goal、ukl 等）
│   │   ├── workflows/  # 成长周期编排器
│   │   └── main.py
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/        # 类型化 API 封装
│       ├── components/ # 通用与管理员组件
│       ├── stores/     # 认证会话存储
│       ├── router/     # 路由与守卫
│       └── views/      # 首页、聊天、资料、计划、成长记录、用户与系统管理
├── database/
│   ├── schema.sql
│   └── migrations/
├── docs/
│   ├── architecture.md
│   └── rag-external-memory/   # UKL / 外置记忆设计文档
└── logs/               # 运行时错误日志（error.log）
```

##注意：如果Growth_Records页面出现Vue组件错误，可能是由于缺少echarts包，使用

```bash
npm install echarts
```

安装echarts后，前端组件错误会得到解决

## 贡献说明

1. 遵循分层模式：routers -> services -> models / schemas。
2. 对行为变更和 RBAC 敏感路径补充测试。
3. 保持文档和环境变量模板与代码变更同步。
