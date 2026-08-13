# Mako

AI Career Intelligence System

Mako 是一个面向求职场景的多 Agent 系统，重点服务计划回国参加校招、实习或社会招聘的留学生。系统把用户的教育背景、项目经历、目标岗位和历史对话组织成可复用的 CareerProfile，并根据任务选择岗位匹配、JD 分析、简历优化、面试准备或求职规划能力。

当前稳定版本为 v2.0.0。仓库包含可运行代码、公开基线测试和本地部署文档。

## 求职工作台

Mako 提供面向求职用户的 Web 工作台，将六项 Career Skill 分为背景诊断、方向匹配、JD 分析、简历优化、面试准备和行动规划。每个板块采用一致的四步流程：选择功能、提供材料、确认输入、查看结果。

工作台支持直接输入问题，也可以读取 UTF-8 编码的 `.txt` 或 `.md` 材料，用于提交简历文本、JD 或经历说明。文件文本随本次请求处理，不会作为知识文档导入。当前页面未接入 PDF、DOCX、用户账户或管理接口。

方向匹配板块可以读取本地已审核、仍在用户所选时效窗口内的职位，并展示经过审核的官方 JD 职责或要求。用户选择本次需要核对的条目和关键词，再确认自己的材料；结果按“已覆盖、部分覆盖、存在差距、待补充、不适用”逐项展示，不生成缺少解释依据的综合分数。材料和匹配结果仅用于当前请求，不写入 CareerProfile、Redis、ChromaDB 或长期证据库。

![Mako 求职工作台](docs/images/mako-workspace.png)

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
| 职位情报 | 23 家官方来源目录、JobPosting 标准化、审核、时效、用户来源选择与数据状态 |
| V2 匹配 | 已审核 JD 要求、用户确认材料、逐项证据状态与请求级结果 |
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
  -> 来源登记与安全检查
  -> 网络和内容安全检查
  -> 站点适配与 JobPosting 标准化
  -> 待审核版本
  -> SQLite 当前版本、历史与时效状态
  -> CareerAgent 按用户选择的核验窗口检索
  -> /chat 返回使用状态与官方来源
```

聊天过程中不会实时访问招聘网站。CareerAgent 只读取已经验证并保存在本地的职位记录，因此官网临时不可用不会阻塞普通对话，也不会把未经检查的页面内容直接送入模型。

## 官方职位情报

默认目录只收录能够确认企业归属的招聘网站，当前覆盖 23 家企业：

| 行业 | 企业 |
|---|---|
| 互联网与数字平台 | 腾讯、字节跳动、美团、百度、阿里巴巴 |
| 通信与智能硬件 | 华为、小米、OPPO、vivo、联想、中兴、大疆 |
| 汽车与新能源 | 比亚迪 |
| 金融 | 中国工商银行、招商银行 |
| 软件、云服务与企业软件 | Microsoft、SAP |
| 工业与智能制造 | Siemens |
| 消费品 | P&G、Unilever |
| 专业服务 | Deloitte、EY |
| 跨国金融服务 | HSBC |

来源目录用于建立企业覆盖面，页面级接入则按官网结构和数据边界逐步验证。百度、SAP 和 Microsoft 分别代表国内互联网、企业软件和跨国科技企业的公开页面接入案例，用于验证从官方页面解析、版本管理、审核到 CareerAgent 检索的完整流程。

每个来源记录官方招聘域名、入口、行业、招聘渠道、支持等级和核验日期。`GET /jobs/sources` 提供只读目录，并支持按行业和支持等级筛选；返回结果按“当前有已核验职位数据”和“当前仅提供官方招聘入口”汇总企业。目录中的企业可以通过受保护接口导入人工核验的结构化 JD；官方页面提供受支持的公开职位结构时，也可以按指定 URL 导入。

默认目录不包含社交平台、招聘聚合站、论坛或来源不明的网站。获取过程检查 HTTPS、允许域名、DNS 和实际连接地址、重定向、robots 规则、响应类型、内容大小及常见指令注入特征。来源进入目录不代表该站点已经具备自动分页或批量刷新能力，默认自动获取保持关闭。无法可靠解析的页面会保留旧数据，不尝试绕过登录、验证码或访问限制。

`JobPosting` 记录企业、职位、地点、职责、要求、招聘类型、发布时间、有效期、更新时间和官方链接。新职位或发生变化的版本先进入待审核状态，不会在审核前替换当前有效版本。内容哈希用于识别变化，审核结果和历史版本保存在 SQLite 中。管理员可以使用受限的批量接口一次导入或审核最多 50 条职位；整批数据会在写入或应用决定前完成校验。

职位根据最近核验时间和官网有效期标记为 `fresh`、`aging`、`stale` 或 `expired`。`career_match` 和 `career_jd` 可以检索本地有效职位；求职用户可通过 `/chat` 的 `job_max_age_days` 为当前请求选择 1–90 天的核验窗口，默认 30 天。扩大范围时会同时显示最近核验时间和时效状态，expired 职位始终排除。

`job_source_ids` 允许用户为单次请求选择最多 5 个官方来源。`job_data_mode` 可以选择仅使用本地已核验职位，或在数据不足时返回已登记的官方招聘入口。官方入口只作为目录信息，不会被解释为具体在招职位，也不会把 `job_data_used` 标记为 true。

返回结果会区分官网事实与分析建议，并通过 `job_data_used`、`job_sources`、`job_max_age_days`、`job_source_ids`、`job_data_mode` 和 `job_source_options` 说明职位数据的使用范围。来源选项会显示当前是否存在可检索数据、可用操作、岗位数量和最近核验时间。这些选择只作用于当前请求，不写入 CareerProfile 或 Memory。

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
| `http://localhost/mako/` | Mako 求职工作台 |
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
  -d '{"user_id":"demo-user","job_max_age_days":30,"job_source_ids":["src_cn_tencent","src_cn_baidu"],"job_data_mode":"official_links_if_missing","message":"我准备回国求职，主修信息系统，有数据分析实习经历，适合关注哪些岗位？"}'
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
- `job_max_age_days`
- `job_source_ids`
- `job_data_mode`
- `job_source_options`
- `request_id`
- `response_complete`
- `continuation_used`
- `quality_flags`

当模型输出因 token 上限或结构未闭合而可能中断时，Mako 最多执行一次有界续写。调用方可以根据完整性和质量字段决定是否重试或转入人工检查。

## 验证

v2.0.0 公开版本完成了以下验证：

| 检查项 | 结果 |
|---|---|
| 公开基线回归 | 133/133 通过 |
| Python syntax / import | 通过 |
| Python 依赖审计 | 未发现已知漏洞 |
| Docker Compose config | 通过 |
| V2 请求级岗位匹配与权限边界 | 通过 |

公开仓库的 CI 会运行公开基线回归、依赖审计、Python 编译检查、Compose 配置检查和凭据模式扫描。

本地运行公开基线测试：

```powershell
.\.venv-win\Scripts\python.exe -m unittest discover -s tests -v
```

## 已知边界

- 不同企业官网采用不同的数据呈现方式。以百度为例，公开列表的完整分页方式尚未确认，因此单页结果不会触发批量停用；
- 来源目录用于建立覆盖面，尚未验证的站点不会启用自动分页或批量刷新；
- 职位信息反映最近一次成功核验时的官网状态；扩大检索窗口会增加旧记录，投递前仍需打开返回的官方链接确认；
- `/chat` 和 `/search` 尚未实现终端用户身份系统，公网多用户部署需要额外的身份层和 TLS。
- V2 工作台只展示具备已审核结构化 JD 条目的岗位；其他有效岗位仍可通过常规方向匹配使用；
- 请求级材料不会跨会话保存，PDF、DOCX、账户体系和跨设备恢复尚未开放。

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
ui/           求职工作台、交互脚本和品牌图标
```

## 数据兼容性

v2.0.0 保持现有 API 路径、Redis key、ChromaDB collection、CareerProfile Schema 和知识登记库结构不变。Redis、ChromaDB、Prometheus、Nginx 与知识登记库继续使用现有 volume 名称和挂载路径。V2 新增独立的证据登记路径；普通工作台请求不会写入该登记库，也不会改变既有聊天与记忆行为。

## 项目文档

- [Mako 从 0 到 1 部署指南](Mako_从0到1部署指南.md)
- [Mako v2.0.0 发布说明](RELEASE_NOTES_v2.0.0.md)
- [Mako v1.9.0 发布说明](RELEASE_NOTES_v1.9.0.md)
- [Mako v1.8.0 发布说明](RELEASE_NOTES_v1.8.0.md)
- [Mako v1.7.0 发布说明](RELEASE_NOTES_v1.7.0.md)
- [Mako v1.6.0 发布说明](RELEASE_NOTES_v1.6.0.md)
- [Mako v1.5.0 发布说明](RELEASE_NOTES_v1.5.0.md)
- [Mako v1.4.0 发布说明](RELEASE_NOTES_v1.4.0.md)
- [Mako v1.3.0 发布说明](RELEASE_NOTES_v1.3.0.md)
- [Mako v1.2.0 发布说明](RELEASE_NOTES_v1.2.0.md)
- [Security Guide](SECURITY.md)

## 安全边界

- 管理、调试、知识库、职位刷新和评测接口使用独立的 `X-Admin-Key`；
- 应用、Redis、ChromaDB 和 Prometheus 的直连端口默认仅绑定本机；
- 外部招聘内容作为不可信事实背景处理，不能修改 Agent 身份、系统规则或工具权限。
