# Mako

AI Career Intelligence System

Mako 是一个面向求职场景的多 Agent 系统。它把用户的职业背景、目标岗位和历史对话组织成可复用的 CareerProfile，并针对岗位匹配、JD 分析、简历、面试和求职规划等任务选择对应能力。

当前版本为 v1.4.0。仓库包含可运行代码、公开基线测试和部署文档。

## V1 能力

| Intent | 处理内容 |
|---|---|
| `career_profile` | 求职背景与竞争力诊断 |
| `career_match` | 岗位方向匹配 |
| `career_jd` | 具体职位 JD 分析 |
| `career_resume` | 简历诊断与定向优化 |
| `career_interview` | 笔试、面试与复盘准备 |
| `career_planning` | 求职行动与能力补强规划 |

CareerAgent 不会补写用户未提供的经历、职责、技能、证书、数据或成果。缺失信息会保持为“尚未确认”，并在需要时向用户追问。

## 工程实现

| 模块 | V1 实现 |
|---|---|
| Agent | GeneralAgent、TechnicalAgent、CareerAgent |
| Skills | 6 个 Career Skills，另有 General 和 Technical Skill |
| 用户画像 | Structured CareerProfile、schema-guided extraction、conservative merge |
| 画像更新 | 只在检测到新增职业信息时异步更新 |
| 工作记忆 | Redis Working Memory |
| 长期记忆 | ChromaDB Episodic Memory 与跨会话画像复用 |
| 能力加载 | Dynamic SkillManager，按 Intent 精确注入单个 Career Skill |
| 知识检索 | RAG knowledge retrieval、文档版本与回滚 |
| 招聘来源 | 企业官方招聘网站目录与受控更新 |
| 可观测性 | `/monitor`、Prometheus、evaluation |
| 回答可靠性 | 完整性检测、一次有界续写和质量状态返回 |
| API 契约 | Request ID、结构化错误和安全的验证摘要 |
| 部署 | Docker Compose |

请求主链路：

```text
POST /chat
  -> Redis Working Memory + ChromaDB
  -> IntentRecognizer
  -> AgentOrchestrator
  -> GeneralAgent / TechnicalAgent / CareerAgent
  -> SkillManager
  -> LLM response
  -> memory / profile / monitor / evaluation
```

## 官方招聘来源

v1.4.0 的默认目录仅收录能够确认企业归属的招聘网站：

| 企业 | 官方招聘域名 |
|---|---|
| 腾讯 | `hr.tencent.com` |
| 华为 | `career.huawei.com` |
| 字节跳动 | `jobs.bytedance.com` |
| 美团 | `zhaopin.meituan.com` |
| 百度 | `talent.baidu.com` |

默认目录不包含社交平台、招聘聚合站、论坛或来源不明的网站。目录注册本身不会抓取内容；自动更新默认关闭，启用前需要管理员确认来源策略。抓取过程会检查 HTTPS、允许域名、DNS 与连接地址、重定向、robots 规则、响应类型、内容大小和常见指令注入特征。

知识文档在 SQLite registry 中保存来源、版本和审计信息，在 ChromaDB 中保存可检索内容。更新、停用和回滚成功后会同步刷新检索数据及缓存。

## v1.4.0 验证结果

| 检查项 | 结果 |
|---|---|
| Python syntax / import | 通过 |
| 公开基线回归 | 通过 |
| Docker Compose config | 通过 |
| Docker image build | 通过 |
| Docker 服务健康检查 | 5/5 healthy |
| Career Intent 路由 | 6/6 路由到 CareerAgent |
| Career Skill 注入 | 每次只注入对应的一个 Skill |

## 快速启动

环境要求：Docker Desktop、Docker Compose v2，以及 Anthropic API Key 或支持 Anthropic 协议的兼容服务密钥。

```bash
cp .env.example .env
docker compose up -d --build
```

在本地 `.env` 中填写服务地址、模型名和 API Key，同时设置随机的 `REDIS_PASSWORD` 和至少 32 个字符的 `MAKO_ADMIN_API_KEY`。`.env` 已被 Git 忽略，不进入仓库。

Swagger 默认关闭。本地需要接口文档时，可在 `.env` 中设置：

```env
ENABLE_SWAGGER_UI=true
```

启动后可访问：

| 地址 | 用途 |
|---|---|
| `http://localhost:8000/docs` | Swagger UI，需启用 `ENABLE_SWAGGER_UI` |
| `http://localhost:8000/health` | 应用健康和 Agent 统计 |
| `http://localhost:8000/skills` | Skill 加载摘要，需 `X-Admin-Key` |
| `http://localhost:8000/monitor` | 监控摘要，需 `X-Admin-Key` |
| `http://localhost:9090` | Prometheus |

查看与停止服务：

```bash
docker compose ps
docker compose logs -f mako
docker compose down
```

更完整的环境准备和部署步骤见 [Mako 从 0 到 1 部署指南](Mako_从0到1部署指南.md)。

## 调用示例

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user","message":"请根据我的背景分析求职优势和短板"}'
```

响应包含：

- `response`
- `intent`
- `agent_type`
- `review_required`
- `latency_ms`
- `knowledge_used`
- `request_id`
- `response_complete`
- `continuation_used`
- `quality_flags`

当模型输出因 token 上限或结构未闭合而可能中断时，Mako 最多执行一次有界续写。调用方可以根据完整性和质量字段决定是否重试或转入人工检查。

## 本地测试

```powershell
.\.venv-win\Scripts\python.exe -m unittest discover -s tests -v
```

内置意图与对话评测可通过 Swagger 调用 `POST /eval/run`。

## 目录结构

```text
agents/       Agent 实现与编排
api/          FastAPI 入口和 HTTP 路由
core/         Intent、CareerProfile 与 Skill 加载
memory/       Redis 与 ChromaDB 记忆层
skills/       动态业务规则
mcp/          工具管理与知识库
monitor/      运行监控
evaluation/   意图与对话评测
tests/        公开基线回归与安全边界测试
tools/        持久化备份和恢复验证工具
```

## 数据兼容性

v1.4.0 保持现有 API 路径、Redis key、ChromaDB collection 和 CareerProfile Schema 不变。Redis、ChromaDB、Prometheus 与 Nginx 的既有 volume 名称继续沿用；新增的 `mako_knowledge-registry-data` volume 用于保存知识来源、文档版本和审计记录。

## 项目文档

- [Mako 从 0 到 1 部署指南](Mako_从0到1部署指南.md)
- [Mako v1.4.0 Release Notes](RELEASE_NOTES_v1.4.0.md)
- [Mako v1.3.0 Release Notes](RELEASE_NOTES_v1.3.0.md)
- [Mako v1.2.0 Release Notes](RELEASE_NOTES_v1.2.0.md)
- [Security Guide](SECURITY.md)

## 安全边界

- 管理、调试、知识库管理和评测接口使用独立的 `X-Admin-Key`。
- 应用、Redis、ChromaDB 和 Prometheus 的直连端口默认仅绑定本机。
