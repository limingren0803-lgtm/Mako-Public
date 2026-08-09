# Mako — AI Career Intelligence System

Mako 是一个面向求职者的 AI Career Intelligence System。当前里程碑为 **Mako v1.0.0**，已进入发布封板阶段：不再新增功能，只处理稳定性、测试、安全和发布文档。

本仓库是可公开展示的独立快照，不包含私有开发历史、真实密钥、运行数据或内部交接材料。后续公开版本会从私有主仓库中经过安全审查后同步。

## V1 能力

CareerAgent 支持六类求职任务：

| Intent | 能力 |
|---|---|
| `career_profile` | 求职背景竞争力诊断 |
| `career_match` | 岗位方向匹配 |
| `career_jd` | 具体职位 JD 分析 |
| `career_resume` | 简历诊断与优化 |
| `career_interview` | 笔试与面试准备 |
| `career_planning` | 求职行动与能力补强规划 |

系统共加载 8 个正式 Skill：6 个 Career Skill、1 个 General Skill 和 1 个 Technical Skill。备份文件不会进入运行时加载。

Career 输出必须遵循真实性边界：不虚构经历、职责、技能、证书、数据或成果；未提供信息保持为“尚未确认”。

## 核心架构

```text
用户请求
  -> FastAPI /chat
  -> Redis 工作记忆 + ChromaDB 情景记忆/CareerProfile
  -> IntentRecognizer
  -> AgentOrchestrator
  -> GeneralAgent / TechnicalAgent / CareerAgent
  -> Intent 精确选择 Skill
  -> LLM 回答
  -> 记忆、监控和评测
```

主要目录：

```text
api/          FastAPI 入口和 HTTP 路由
agents/       Agent 实现与路由编排
core/         Intent 识别与 Skill 加载
memory/       Redis + ChromaDB 记忆/CareerProfile
skills/       动态业务规则
mcp/          工具管理和知识库
monitor/      运行监控
evaluation/   意图与对话评测
tests/        V1 自动回归测试
wiki/         详细使用和技术文档
```

## 快速启动

### 1. 准备环境

需要：

- Docker Desktop
- Docker Compose v2
- Anthropic API Key，或支持 Anthropic 协议的 DeepSeek API Key

### 2. 配置 `.env`

从 `.env.example` 创建本地 `.env`，不要将 `.env` 提交到 Git。

Anthropic 示例：

```env
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

DeepSeek Anthropic 兼容接口示例：

```env
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-pro
```

请在本地将密钥填在等号后，不要将密钥发送到聊天、截图或日志中。

### 3. 启动

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
docker compose logs -f echomind
```

停止：

```bash
docker compose down
```

## 验收入口

| 地址 | 用途 |
|---|---|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/health` | 应用健康和 Agent 统计 |
| `http://localhost:8000/skills` | Skill 加载摘要 |
| `http://localhost:8000/monitor` | 监控摘要 |
| `http://localhost:9090` | Prometheus |

V1 验收时，`GET /skills` 应返回：

- `count: 8`
- `errors: []`
- 6 个 Career Skill 均有唯一 `intent`

### `/chat` 示例

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user","message":"请根据我的背景分析求职优势和短板"}'
```

关键返回字段：

- `response`
- `intent`
- `agent_type`
- `review_required`
- `latency_ms`
- `knowledge_used`

## 本地测试

Windows 虚拟环境：

```powershell
.\.venv-win\Scripts\python.exe -m unittest discover -s tests -v
```

差异格式检查：

```bash
git diff --check
```

内置意图和对话评测可通过 Swagger 调用 `POST /eval/run`。

## V1 发布验证

- 6 个 Career Intent 均路由到 CareerAgent。
- 每次只注入一个与 Intent 对应的 Career Skill。
- 长 Skill 的最后一条规则可进入 system prompt，不被默认长度截断。
- CareerProfile 只在检测到新职业信息时更新。
- `.env`、`.idea`、本地 ChromaDB、PDF、ZIP 和备份 Skill 不进入发布提交。
- V1 自动回归测试通过：10/10。
- V1 内置评测通过：11/11。

## 项目文档

- `wiki/完整使用指南.md`：详细部署和操作指南。
- `wiki/Mako完整使用指南.md`：V1 使用说明。
- `Mako_从0到1部署指南.md`：从环境准备到启动验收的部署步骤。

## V1 兼容性说明

公开品牌统一为 **Mako**。以下旧式工程标识在 V1 中有意保留，以兼容已有 Compose 部署、环境配置和持久化数据：

- Docker service、container、image、network 和 volume 中的 `echomind`。
- 已参与部署的 `ECHOMIND_*` 环境变量。

这些标识不代表对外品牌，也不建议在 V1 中强制迁移。API 路径、Redis 工作记忆 key、ChromaDB collection 和 CareerProfile Schema 均保持不变。

## 安全

- `.env` 已被 Git 忽略，不得重新跟踪。
- 如果 API Key 曾出现在 Git 历史中，必须在模型服务商后台撤销并换新。
- 不得将真实用户简历、长期画像或本地 ChromaDB 数据提交到仓库。
