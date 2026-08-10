# Mako

AI Career Intelligence System

Mako 是一个面向求职场景的多 Agent 系统，重点服务计划回国参加校招、实习或社会招聘的留学生。系统把用户的教育背景、项目经历、目标岗位和历史对话组织成可复用的 CareerProfile，并根据任务选择岗位匹配、JD 分析、简历优化、面试准备或求职规划能力。

当前稳定版本为 v1.5.0。仓库包含可运行代码、公开基线测试和本地部署文档。

## 适用场景

- 梳理海外教育和项目经历，识别适合国内招聘市场的岗位方向；
- 对照具体 JD 分析经历匹配度、证据缺口和准备优先级；
- 在不虚构经历和成果的前提下优化简历表达；
- 围绕目标岗位准备笔试、面试和阶段性求职计划；
- 查询本地已验证的企业官方职位记录，并保留来源链接和更新时间。

Mako 不补写用户没有提供的经历、职责、技能、证书、数据或成果。缺失信息保持为“尚未确认”，需要时再向用户追问。

## 核心能力

| Intent | 处理内容 |
|---|---|
| `career_profile` | 求职背景与竞争力诊断 |
| `career_match` | 岗位方向和在招职位匹配 |
| `career_jd` | 具体职位 JD 分析 |
| `career_resume` | 简历诊断与定向优化 |
| `career_interview` | 笔试、面试与复盘准备 |
| `career_planning` | 求职行动与能力补强规划 |

## 工程实现

| 模块 | 实现 |
|---|---|
| Agent | GeneralAgent、TechnicalAgent、CareerAgent |
| Skills | 6 个 Career Skills，另有 General 和 Technical Skill |
| 用户画像 | Structured CareerProfile、schema-guided extraction、conservative merge |
| 画像更新 | 只在检测到新增职业信息时异步更新 |
| 工作记忆 | Redis Working Memory |
| 长期记忆 | ChromaDB Episodic Memory 与跨会话画像复用 |
| 能力加载 | Dynamic SkillManager，按 Intent 注入单个 Career Skill |
| 知识检索 | RAG knowledge retrieval、文档版本与回滚 |
| 职位情报 | 官方来源验证、JobPosting 标准化、版本与状态管理 |
| 可观测性 | `/monitor`、Prometheus、evaluation |
| 回答可靠性 | 完整性检测、一次有界续写和质量状态返回 |
| API 契约 | Request ID、结构化错误、职位来源和安全验证摘要 |
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

职位情报链路与聊天请求分离：

```text
企业官方招聘站点
  -> 来源登记与管理员审批
  -> 网络和内容安全检查
  -> 站点适配与 JobPosting 标准化
  -> SQLite 版本及生命周期登记
  -> CareerAgent 本地检索
  -> /chat 返回使用状态与官方来源
```

聊天过程中不会实时访问招聘网站。CareerAgent 只读取已经验证并保存在本地的职位记录，因此官网临时不可用不会阻塞普通对话，也不会把未经检查的页面内容直接送入模型。

## 官方职位情报

默认目录只收录能够确认企业归属的招聘网站：

| 企业 | 官方招聘域名 | v1.5 状态 |
|---|---|---|
| 腾讯 | `hr.tencent.com` | 已登记并完成公开页面结构核验；暂不自动解析 |
| 华为 | `career.huawei.com` | 已登记并完成公开页面结构核验；暂不自动解析 |
| 字节跳动 | `jobs.bytedance.com` | 已登记并完成公开页面结构核验；暂不自动解析 |
| 美团 | `zhaopin.meituan.com` | 已登记并完成公开页面结构核验；暂不自动解析 |
| 百度 | `talent.baidu.com` | 支持公开列表映射；单页结果按不完整快照处理 |

默认目录不包含社交平台、招聘聚合站、论坛或来源不明的网站。获取过程检查 HTTPS、允许域名、DNS 和实际连接地址、重定向、robots 规则、响应类型、内容大小及常见指令注入特征。无法可靠解析的页面会保留旧数据，不尝试绕过登录、验证码或访问限制。

`JobPosting` 记录企业、职位、地点、职责、要求、招聘类型、发布时间、有效期、更新时间和官方链接。内容哈希用于识别变化；发生有效更新时保留历史版本。职位状态分为 `active`、`inactive` 和 `expired`，只有经过确认的完整快照才能停用本次没有出现的职位。

`career_match` 和 `career_jd` 可以检索本地有效职位。返回结果会区分官网事实与分析建议，并通过 `job_data_used` 和 `job_sources` 说明是否使用了职位数据及其来源。

## 快速启动

环境要求：Docker Desktop、Docker Compose v2，以及 Anthropic API Key 或支持 Anthropic 协议的兼容服务密钥。

```bash
cp .env.example .env
docker compose up -d --build
```

在本地 `.env` 中填写服务地址、模型名和 API Key，同时设置随机的 `REDIS_PASSWORD` 和至少 32 个字符的 `MAKO_ADMIN_API_KEY`。`.env` 已被 Git 忽略。

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

完整的环境准备和部署步骤见 [Mako 从 0 到 1 部署指南](Mako_从0到1部署指南.md)。

## 调用示例

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user","message":"我准备回国求职，主修信息系统，有数据分析实习经历，适合关注哪些岗位？"}'
```

响应中的关键字段包括：

- `response`
- `intent`
- `agent_type`
- `review_required`
- `latency_ms`
- `knowledge_used`
- `job_data_used`
- `job_sources`
- `request_id`
- `response_complete`
- `continuation_used`
- `quality_flags`

当模型输出因 token 上限或结构未闭合而可能中断时，Mako 最多执行一次有界续写。调用方可以根据完整性和质量字段决定是否重试或转入人工检查。

## 验证

v1.5.0 发布前完成了以下验证：

| 检查项 | 结果 |
|---|---|
| 完整确定性回归 | 108/108 通过 |
| Python syntax / import | 通过 |
| Python 依赖审计 | 未发现已知漏洞 |
| Docker Compose config | 通过 |
| Docker image build | 通过 |
| Docker 服务健康检查 | 5/5 healthy，重启次数为 0 |
| 应用、Nginx、ChromaDB、Prometheus 在线检查 | HTTP 200 |
| 职位登记库跨容器恢复 | 通过 |

公开仓库的 CI 会运行公开基线回归、依赖审计、Python 编译检查、Compose 配置检查和凭据模式扫描。

本地运行公开基线测试：

```powershell
.\.venv-win\Scripts\python.exe -m unittest discover -s tests -v
```

## 已知边界

- 百度公开列表的完整分页方式尚未确认，单页结果不会触发批量停用；
- 腾讯、华为、字节跳动和美团当前没有可验证的自动职位刷新能力；
- 职位信息反映最近一次成功更新时的官网状态，投递前仍需打开返回的官方链接确认；
- `/chat` 和 `/search` 尚未实现终端用户身份系统，公网多用户部署需要额外的身份层和 TLS。

这些限制保留在文档中，是为了让职位建议的来源、时效和适用范围可以被检查。

## 目录结构

```text
agents/       Agent 实现与编排
api/          FastAPI 入口和 HTTP 路由
core/         Intent、CareerProfile、职位模型与 Skill 加载
memory/       Redis 与 ChromaDB 记忆层
skills/       动态业务规则
mcp/          工具管理、知识库和职位适配器
monitor/      运行监控
evaluation/   意图与对话评测
tests/        公开基线回归与安全边界测试
tools/        持久化备份和恢复验证工具
```

## 数据兼容性

v1.5.0 保持现有 API 路径、Redis key、ChromaDB collection 和 CareerProfile Schema 不变。Redis、ChromaDB、Prometheus、Nginx 与知识登记库继续使用现有 volume 名称和挂载路径；职位表在既有 SQLite registry 中增量创建。

## 项目文档

- [Mako 从 0 到 1 部署指南](Mako_从0到1部署指南.md)
- [Mako v1.5.0 发布说明](RELEASE_NOTES_v1.5.0.md)
- [Mako v1.4.0 发布说明](RELEASE_NOTES_v1.4.0.md)
- [Mako v1.3.0 发布说明](RELEASE_NOTES_v1.3.0.md)
- [Mako v1.2.0 发布说明](RELEASE_NOTES_v1.2.0.md)
- [Security Guide](SECURITY.md)

## 安全边界

- 管理、调试、知识库、职位刷新和评测接口使用独立的 `X-Admin-Key`；
- 应用、Redis、ChromaDB 和 Prometheus 的直连端口默认仅绑定本机；
- 外部招聘内容作为不可信事实背景处理，不能修改 Agent 身份、系统规则或工具权限。
