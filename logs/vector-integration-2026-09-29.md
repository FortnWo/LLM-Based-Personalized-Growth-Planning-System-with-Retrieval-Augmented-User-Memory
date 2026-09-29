# 向量检索试验修改日志

日期：2026-09-29

## 已完成

- 将 `009_add_memory_embedding.sql` 纳入启动时 schema bootstrap。
- 增加 Qdrant 客户端依赖和可选向量库配置。
- 新增懒加载的 `vector_store` 服务，支持 collection 初始化、维度校验、upsert、按用户过滤查询、删除、健康检查和显式重建。
- 事实记忆写入时增加 Qdrant 双写；MySQL 仍为事实源。
- Qdrant 写入或查询失败时保留 JSON cosine / 关键词 fallback；可通过 `VECTOR_STORE_STRICT` 选择严格失败模式。
- 新增 `backend/scripts/reindex_memory_facts.py`，支持 dry-run、用户过滤、数量限制和索引重建。
- 增加 schema bootstrap、Qdrant 写入和 Qdrant 故障降级测试。
- 更新 README、架构文档和本地 Qdrant Compose 配置。

## 配置方法

1. 执行 `docker compose -f docker-compose.vector.yml up -d`。
2. 在 `backend/.env` 设置 `UKL_ENABLED=true`、`MEMORY_FACT_EMBEDDING_ENABLED=true`、`VECTOR_STORE_ENABLED=true`、`VECTOR_STORE_BACKEND=qdrant`。
3. 配置支持 `/embeddings` 的 `LLM_API_KEY`、`LLM_API_BASE_URL` 和 `EMBEDDING_MODEL`。
4. 用 `python backend/scripts/reindex_memory_facts.py --dry-run` 检查待回填数量，再执行小批量回填。

## 验证状态

- 静态错误检查：已通过，目标 Python 文件未发现编辑器诊断错误。
- Python 编译检查：`python3 -m compileall -q app scripts tests` 已通过。
- Git 补丁检查：`git diff --check` 已通过。
- 定向 pytest：当前 `/usr/bin/python3` 没有 `pytest` 模块，当前环境也没有 `pip`，因此尚未执行；需要先准备项目 Python 3.11 虚拟环境并安装 `requirements-dev.txt`。
- 真实 Qdrant/MySQL 集成测试：未执行，需安装后端开发依赖并启动服务。
- 已增加的 mock 测试覆盖：migration 009、Qdrant upsert、Qdrant 查询失败降级。

## 回滚方式

- 将 `VECTOR_STORE_ENABLED=false`，应用继续使用现有 MySQL JSON cosine / 关键词路径。
- 不删除 `memory_embedding` 或 MySQL 事实数据；Qdrant collection 可独立删除后重新回填。