from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AI Mentor & Growth Planning System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    DATABASE_URL: str = "mysql+pymysql://user:password@localhost:3306/ai_mentor_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    AI_BACKGROUND_MAX_WORKERS: int = 12

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    LLM_API_KEY: str | None = None
    LLM_API_BASE_URL: str | None = None
    LLM_MODEL: str | None = None
    LLM_SYSTEM_PROMPT: str = (
        "你是一位支持型大学 AI 导师，耐心倾听学生的困惑与目标，"
        "用清晰、鼓励的语气给出可执行的建议，避免空泛说教。"
    )
    PROFILE_EXTRACTION_ENABLED: bool = True
    PROFILE_EXTRACTION_MESSAGE_WINDOW: int = 14
    PROFILE_EXTRACTION_MIN_INTERVAL_MINUTES: int = 5
    PROFILE_EXTRACTION_BURST_USER_TURNS: int = 3
    PROFILE_EXTRACTION_ON_DEMAND_ENABLED: bool = True
    PROFILE_EXTRACTION_MIN_USER_MESSAGE_CHARS: int = 12
    PROFILE_EXTRACTION_SYSTEM_PROMPT: str = (
        "你是画像提取助手。从对话中提取用户画像信号，仅输出严格 JSON。"
        "键名必须为英文：interests、skills、goals、study_habits、personality、preferences。"
        "每个键对应短字符串数组；未知则返回空数组。"
        "不要输出 markdown 或额外说明。"
    )
    PORTRAIT_SUMMARY_SYSTEM_PROMPT: str = (
        "你是学生成长导师。用第二人称写一段 150-250 字的中文画像摘要。"
        "仅使用用户消息中提供的特质信号，不要编造。"
        "若无特质，请原样回复：尚未形成可描述的画像特质，建议多与 AI 导师交流或补充画像字段。"
    )
    GOAL_BREAKDOWN_ENABLED: bool = True
    GOAL_BREAKDOWN_MESSAGE_WINDOW: int = 5
    GOAL_BREAKDOWN_SYSTEM_PROMPT: str = (
        "你是目标拆解助手。根据用户目标与可选上下文，仅输出严格 JSON。"
        "返回含 breakdowns 键的 JSON，值为拆解节点数组。"
        "每个节点含 title（字符串）、description（字符串或 null）、children（子节点数组）。"
        "优先三级树：顶层一个节点对应目标标题，子节点为主支柱（适量阶段，避免过细拆分），再下挂具体子任务。"
        "简单目标可用两级树。无法拆解时 breakdowns 为空数组。"
        "不要输出 markdown 或额外说明。"
    )
    ACTION_PLAN_ENABLED: bool = True
    ACTION_PLAN_CONTEXT_MESSAGE_WINDOW: int = 8
    ACTION_PLAN_SYSTEM_PROMPT: str = (
        "你是行动计划助手。根据目标、拆解树与可选画像，仅输出严格 JSON。"
        "顶层键为 plan 与 items。plan 含 title、summary；"
        "items 为对象数组，字段：title、description、frequency、schedule、status、start_date、due_date、sequence、breakdown_ref。"
        "status 取值 pending、in_progress、completed、archived；"
        "frequency 取值 once、daily、weekly、monthly、custom。"
        "无法形成计划时 items 为空数组，未知字段用空字符串或 null。"
        "不要输出 markdown、代码块或额外说明。"
    )
    SESSION_TITLE_SYSTEM_PROMPT: str = (
        "你是对话标题生成助手。根据首条用户消息与助手回复，输出 4-16 字的中文标题。"
        "只输出标题文本，不要引号、标点、markdown 或解释。"
    )
    ADMIN_LLM_SYSTEM_PROMPT: str = (
        "你是一个专业全能的系统管理助手。"
        "你可以通过工具查询系统数据库、获取日志和统计信息，用自然语言为管理员提供精准答复。"
        "回答要简洁专业，数据准确。禁止执行任何写操作或 DDL 语句。"
    )
    APP_SECRET_KEY: str = "ai-mentor-default-secret-change-in-production"
    RUN_LIVE_AI_TESTS: bool = False

    # UKL (user knowledge layer); UKL0: profile dual-write; UKL1: chat attention packaging when enabled
    UKL_ENABLED: bool = False
    CHAT_WORK_MEMORY_MAX_MESSAGES: int = 12
    CHAT_SUMMARY_USE_THRESHOLD: int = 16
    CHAT_SESSION_SUMMARY_ENABLED: bool = True
    CHAT_SESSION_SUMMARY_SYSTEM_PROMPT: str = (
        "你是对话摘要助手。根据已有摘要与新增对话，输出更新后的中文会话摘要（第二人称，150-400字）。"
        "保留关键事实、目标、情绪与未决事项；不要编造；不要输出 markdown 或标题。"
    )
    BREAKDOWN_SUMMARY_ENABLED: bool = True
    BREAKDOWN_SUMMARY_SYSTEM_PROMPT: str = (
        "你是目标拆解叙事助手。根据目标信息与拆解树结构，输出 150-300 字中文叙事摘要。"
        "概括拆解思路、关键支柱与执行节奏；不要输出 JSON、markdown 或标题；不要编造未给出的细节。"
    )
    ACTION_PLAN_COVERAGE_VALIDATION_ENABLED: bool = True
    EXECUTION_SLICE_ENABLED: bool = True
    GROWTH_JOURNAL_ENABLED: bool = True
    GROWTH_JOURNAL_SYSTEM_PROMPT: str = (
        "你是成长记录叙事助手。根据单条成长记录信息，输出 80-200 字中文叙事投影。"
        "保留关键事实与情绪色彩，用第二人称；不要输出 JSON、markdown 或标题；不要编造未给出的细节。"
    )
    FEEDBACK_SUMMARY_SYSTEM_PROMPT: str = (
        "你是温暖专业的成长导师。根据用户的 UKL 反馈上下文与当周成长记录锚点，"
        "写一段 2-4 句的中文周总结，肯定进步并给出下周可执行的小步建议。"
        "语气亲切、具体、有证据；不要编造；不要输出 markdown 或标题。"
    )
    MILESTONE_UKL_ENABLED: bool = True
    INSTANT_FEEDBACK_ENABLED: bool = True
    INSTANT_FEEDBACK_SYSTEM_PROMPT: str = (
        "你是温暖的成长导师。用户刚达成一个里程碑节点，请用 1-2 句中文祝贺并点出具体进步。"
        "语气真诚、简短；不要输出 markdown 或标题；不要编造未给出的细节。"
    )
    GROWTH_PATTERN_ENABLED: bool = True
    GROWTH_PATTERN_CHECKIN_THRESHOLD: int = 5
    GROWTH_PATTERN_MIN_DAYS: int = 7
    GROWTH_PATTERN_SYSTEM_PROMPT: str = (
        "你是成长模式分析助手。根据用户近期的成长记录与打卡数据，"
        "归纳 2-4 个主题词、整体情绪趋势（积极/平稳/波动）、坚持度观察，"
        "并输出 100-200 字中文叙事摘要。不要输出 JSON 或 markdown。"
    )
    EPISODIC_NARRATIVE_ENABLED: bool = True
    GOAL_INTENT_ENABLED: bool = True
    EPISODIC_NARRATIVE_SYSTEM_PROMPT: str = (
        "你是跨会话记忆助手。合并用户近期会话摘要与已有跨会话叙事，"
        "输出 150-250 字中文连贯叙事，保留关键事实与进展线索。"
        "不要输出 JSON、markdown 或标题；不要编造未给出的细节。"
    )
    GOAL_INTENT_SYSTEM_PROMPT: str = (
        "你是目标动机分析助手。根据目标标题与描述，用 80-150 字中文概括用户的核心动机与期望。"
        "不要输出 JSON、markdown 或标题；不要编造未给出的细节。"
    )
    ACTION_PLAN_COMPLETION_ASYNC: bool = True
    MEMORY_FACT_ENABLED: bool = True
    MEMORY_FACT_EXTRACTION_ENABLED: bool = True
    MEMORY_FACT_EMBEDDING_ENABLED: bool = True
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    MEMORY_FACT_TOP_K: int = 5
    MEMORY_FACT_MIN_SCORE: float = 0.72
    MEMORY_FACT_MAX_PER_TURN: int = 3
    MEMORY_FACT_MIN_SALIENCE: float = 0.4
    VECTOR_STORE_ENABLED: bool = False
    VECTOR_STORE_BACKEND: str = "none"
    VECTOR_STORE_URL: str = "http://localhost:6333"
    VECTOR_STORE_API_KEY: str | None = None
    VECTOR_STORE_COLLECTION: str = "memory_facts"
    VECTOR_STORE_TIMEOUT_SECONDS: float = 3.0
    VECTOR_STORE_STRICT: bool = False
    EMBEDDING_DIMENSIONS: int = 1536
    MEMORY_FACT_EXTRACTION_SYSTEM_PROMPT: str = (
        "你是记忆事实提取助手。根据一轮用户与助手对话，提取对话中明确陈述的、可长期保留的个人事实。"
        "仅输出严格 JSON 数组；每项含键 fact（中文字符串）、salience（0-1 浮点数）、"
        "tags（短字符串数组，如 schedule、goal、preference）。"
        "只摘录对话中已有内容，不要编造；无事实时返回空数组。"
        "不要输出 markdown 或额外说明。"
    )

    AUTH_SECRET_KEY: str = "change-me-in-production-with-a-long-secret-key"
    AUTH_ALGORITHM: str = "HS256"
    AUTH_ACCESS_TOKEN_EXPIRES_MINUTES: int = 120

    BOOTSTRAP_ADMIN_USERNAME: str | None = None
    BOOTSTRAP_ADMIN_EMAIL: str | None = None
    BOOTSTRAP_ADMIN_PASSWORD: str | None = None
    BOOTSTRAP_ADMIN_FULL_NAME: str | None = None

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
