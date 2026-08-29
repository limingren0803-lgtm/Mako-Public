# Mako 安全说明

本文说明 Mako 当前的管理接口、本机工作区、网络、上传、官方职位来源与职位分析边界。它不替代公网部署所需的用户身份系统。

## 管理接口密钥

以下运维接口需要在请求头中提供 `X-Admin-Key`：

- `GET /skills`
- `POST /skills/reload`
- `GET /monitor`
- `GET /debug/profile/{user_id}`
- `POST /knowledge/add`
- `POST /knowledge/upload`
- `GET /knowledge/stats`
- `/knowledge/sources*`
- `/knowledge/documents*`
- `GET /knowledge/audit`
- `POST /jobs/sources/{source_id}/refresh`
- `GET /jobs`
- `POST /eval/run`

`MAKO_ADMIN_API_KEY` 应设置为至少 32 个字符的随机值。变量缺失或长度不足时，这些接口保持不可用。密钥保存在本地 `.env`，不进入版本控制。

可以在本地生成随机值：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

调用受保护接口时通过请求头传入：

```bash
curl -H "X-Admin-Key: <your-admin-key>" http://localhost:8000/skills
```

该请求头只适合在本机或 HTTPS 连接中使用，普通 HTTP 无法保护传输中的请求头内容。

## 网络边界

Docker Compose 将应用、Redis、ChromaDB 和 Prometheus 的直连端口绑定到 `127.0.0.1`，容器通过 `mako-network` 通信。Nginx 是默认的外部 HTTP 入口，使用 80 端口。Redis、ChromaDB、Prometheus、Nginx 和知识登记库沿用明确的兼容卷名，升级时可继续使用现有数据。

Compose 解析配置时需要 `REDIS_PASSWORD`。已有部署可以保留当前密码，新部署应使用足够长的随机值。

## 浏览器访问与接口文档

`MAKO_CORS_ALLOW_ORIGINS` 接受逗号分隔的可信来源。默认值只允许常见的 `localhost` 和 `127.0.0.1` 开发来源，面向公网时不应使用 `*`。

Swagger UI、ReDoc 和 OpenAPI 文档由 `ENABLE_SWAGGER_UI` 控制。示例配置默认关闭；本地开发或可信管理网络可以按需启用。

## 上传与日志

知识库上传支持 UTF-8 编码的 `.txt`、`.md` 和 `.json` 文件，单个文件不超过 10 MB。应用以限制大小的分块读取文件，并校验文档数量、字段长度和文件名。

CareerProfile 内容和意图学习的原始消息不会写入应用日志。用于运行关联的用户标识与会话标识以短摘要表示。

## 官方招聘来源

内置目录覆盖 23 家经过核验的企业官方招聘域名。目录覆盖与页面级职位解析是两项不同能力；百度、SAP 和 Microsoft 用于验证页面接入链路，其他企业按各自官网结构和访问边界分别评估。目录不收录社交平台、招聘聚合站、论坛或来源不明的域名。

登记来源不会自动抓取内容。自动获取默认关闭，需要经过授权的策略修改才能开启。获取过程限制在已登记的 HTTPS 域名和允许的委托域名，并检查 DNS、实际连接地址、重定向、robots 规则、响应类型、内容大小和常见指令注入特征。

外部招聘文本只作为不可信的事实背景，不能改变 Agent 身份、系统规则、工具权限或输出要求。

## 职位分析边界

职位更新使用现有的已审核来源目录。适配和存储层都会检查来源身份、企业名称与职位链接域名。空结果或不完整解析不会让已有职位失效，只有明确标记为完整的来源快照才会进入对账。

聊天请求不会实时访问招聘网站。`career_match` 和 `career_jd` 可以读取本地有效且未过期的职位记录，其他意图不会接收职位上下文。响应会说明是否使用职位数据，并返回对应的官方来源链接。

需要登录、绕过验证码、访问受限静态资源或使用未经核验动态接口的网站不会被自动解析。

## Career Workspace

Career Workspace 面向本机单用户使用。首次进入时，前端通过 `POST /v2/workspace/session` 建立 12 小时 HttpOnly 会话，后续同源请求自动携带 Cookie。页面不会读取 Cookie 内容，也不使用管理员密钥、任意 `user_id` 或 localStorage 中的长期令牌。

创建岗位和行动支持 `Idempotency-Key`。更新和删除需要当前 `revision`；版本不一致时返回 `409`，由页面重新读取最新状态。删除岗位与清空工作区前会先查询影响范围。

工作区使用独立 SQLite 和 Docker volume。它不反向修改 CareerProfile、Redis、ChromaDB、官方职位库或 Evidence Registry。用户自行提供的职位链接只作为来源标注，不会触发网络访问。

## 仍需补充的部署边界

`POST /chat` 和 `POST /search` 尚未提供终端用户身份系统。Nginx 会对通过 80 端口进入的请求限制连接数和请求节奏。公网多用户部署仍需增加身份层与 TLS 终止，并配置明确的 CORS 来源。

## 依赖审计

CI 使用 `pip-audit` 检查固定版本的 Python 依赖。ChromaDB 当前稳定版本尚未修复 CVE-2026-45830、CVE-2026-45831 和 CVE-2026-45833，因此公开 CI 只为这三项公告保留精确临时例外，不会忽略其他审计结果。

ChromaDB 的直连端口继续只绑定 `127.0.0.1`，也不通过 Nginx 对外代理。上游发布修复版本并通过兼容性回归后，应升级依赖并移除这些例外。
