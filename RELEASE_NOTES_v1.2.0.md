# Mako v1.2.0 Release Notes

发布日期：2026-08-10

Mako v1.2.0 集中完善部署边界、隐私保护、依赖安全和自动化验证，不改变 Career Agent 的业务能力。

## 主要更新

- 管理、调试、知识库管理和评测接口使用 `X-Admin-Key`，由本地 `MAKO_ADMIN_API_KEY` 提供。
- CORS 默认仅允许本地开发来源，Swagger、ReDoc 和 OpenAPI 文档由 `ENABLE_SWAGGER_UI` 控制。
- `/chat` 标识符、检索参数、知识文档和上传内容增加数量与长度边界。
- 知识文件采用分块读取，仅接受不超过 10 MB 的 UTF-8 `.txt`、`.md` 和 `.json` 文件。
- 日志不再记录完整 CareerProfile、原始学习消息、Skill 请求内容或改写后的查询。
- 应用、Redis、ChromaDB 和 Prometheus 的宿主机直连端口仅绑定 `127.0.0.1`。
- Compose 要求本地提供 `REDIS_PASSWORD`，不再提供公开的默认密码。
- FastAPI、Starlette、python-multipart 和 python-dotenv 已完成安全升级，CI 增加依赖漏洞审计。

## 兼容性

现有 API 路径、CareerProfile Schema、Redis keys、ChromaDB collections、Compose 内部兼容标识和持久化 volume 名称保持不变，不需要数据迁移。

## 验证结果

- 45/45 项确定性回归测试通过。
- Python syntax/import 与 Docker Compose 配置校验通过。
- Python 依赖审计为 0 个已知漏洞。
- 五个 Compose 服务均为 healthy。
- 在线评测 16/16 通过，通过率 1.0，未检测到回归。
- 备份校验和隔离恢复检查通过，正式数据卷未被覆盖。

## 部署边界

`POST /chat` 和 `POST /search` 不提供最终用户身份认证。公开的多用户部署需要在 Mako 前增加 TLS 和身份认证，并配置明确的 CORS 来源。
