# Mako

AI Career Intelligence System

Mako 是一个面向求职场景的多 Agent 系统。它把用户的职业背景、目标岗位和历史对话组织成可复用的 CareerProfile，并针对岗位匹配、JD 分析、简历、面试和求职规划等任务选择对应能力。

当前公开版本为 v1.0.0。本仓库不包含私有开发历史、真实密钥、运行数据或内部交接资料。

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
| 知识检索 | RAG knowledge retrieval |
| 可观测性 | `/monitor`、Prometheus、evaluation |
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

## V1 验证结果

| 检查项 | 结果 |
|---|---|
| Python syntax / import | 通过 |
| V1 自动回归测试 | 10/10 |
| V1 内置评测 | 11/11 |
| Docker Compose config | 通过 |
| Docker image build | 通过 |
| Career Intent 路由 | 6/6 路由到 CareerAgent |
| Career Skill 注入 | 每次只注入对应的一个 Skill |

## 快速启动

环境要求：Docker Desktop、Docker Compose v2，以及 Anthropic API Key 或支持 Anthropic 协议的兼容服务密钥。

```bash
cp .env.example .env
docker compose up -d --build
```

在本地 `.env` 中填写服务地址、模型名和 API Key。`.env` 已被 Git 忽略，不应提交到仓库。

启动后可访问：

| 地址 | 用途 |
|---|---|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/health` | 应用健康和 Agent 统计 |
| `http://localhost:8000/skills` | Skill 加载摘要 |
| `http://localhost:8000/monitor` | 监控摘要 |
| `http://localhost:9090` | Prometheus |

查看与停止服务：

```bash
docker compose ps
docker compose logs -f echomind
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
tests/        V1 自动回归测试
```

## V1 兼容性

对外品牌为 Mako。Docker service、container、image、network、volume 中的 `echomind`，以及 `ECHOMIND_*` 环境变量，是为了兼容已有部署和持久化数据而保留的工程标识。

本次发布没有迁移 API 路径、Redis key、ChromaDB collection 或 CareerProfile Schema。

## 安全边界

- `.env`、本地运行数据、日志、PDF、ZIP 和备份文件不进入公开提交。
- 不提交真实用户简历、CareerProfile 或 ChromaDB 数据。
- API Key 如果曾进入 Git 历史，应立即在服务商后台撤销并更换。
