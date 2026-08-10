# Mako v1.3.0 发布说明

发布日期：2026-08-10

## 版本概览

Mako v1.3.0 主要改进回答可靠性、API 一致性和运行时部署。六个 Career Skills、CareerProfile Schema、Memory 行为和现有 API 路径保持不变。

## 回答可靠性

- 根据模型服务的停止原因和响应结构检查 token 上限、空输出、未闭合代码块和明显未完成的结尾；
- 对疑似截断的回答进行一次有界续写，第二次结果仍不完整时返回明确的质量状态；
- `/chat` 响应包含 `request_id`、`response_complete`、`continuation_used` 和 `quality_flags`；
- 端到端评测将不完整回答判定为失败，即使其 LLM 质量评分高于其他通过阈值。

## API 契约

- 成功和失败的请求均返回 `X-Request-ID`，调用方可以提供有效 request ID，也可以由 Mako 生成；
- API 错误采用统一的 `error.code`、`error.message` 和 `error.request_id` 结构；
- 参数校验错误会标明相关字段，但不会回显被拒绝的输入值。

## 运行时与部署

- Skill 配置使用 `MAKO_SKILLS_DIR` 和 `MAKO_SKILLS_MAX_PROMPT_CHARS`；
- Compose project、应用服务、容器、网络、镜像、Nginx upstream、Prometheus 标签和镜像内非 root 用户采用 Mako 命名；
- 四个现有 Docker volume 使用显式名称，升级过程继续使用 Redis、ChromaDB、Prometheus 和 Nginx 数据，全新安装会自动创建相同名称的 volumes。

## 验证结果

- Python syntax/import 检查通过；
- 确定性回归测试 62/62 通过；
- Docker Compose 配置校验通过；
- 五个 Mako 容器均完成重建并达到 healthy 状态；
- 在线健康检查、结构化参数错误、request ID、GeneralAgent 对话和管理边界检查通过；
- 受保护的在线评测 16/16 通过，通过率为 1.0，未发现回归或不完整回答；
- Redis 保留 26 个 keys，知识库保留 7 个片段，四个持久化 volumes 仍挂载在原目标位置；
- 容器迁移前，现有持久化备份通过 manifest 和 checksum 校验。

## 兼容性

以下接口和数据结构保持不变：

- `/chat`、`/monitor`、`/debug/profile`、知识库、Skills 和评测路由；
- CareerProfile 字段和 conservative merge 行为；
- Redis keys 和 ChromaDB collection 名称；
- 四个持久化 Docker volume 名称；
- 六个 Career intents 和 Skills。

升级安装首次启动 v1.3 时，Compose 可能提示某个命名 volume 由此前的 Compose project 创建。该 volume 会继续使用，不会被复制或清空。
