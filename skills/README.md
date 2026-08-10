# Mako Skills 文档

Mako 启动时从 `MAKO_SKILLS_DIR` 读取 Skills，并在匹配用户请求时注入到对应 Agent 的 system prompt。现有部署仍可使用 `ECHOMIND_SKILLS_DIR` 作为兼容配置。Skills 用于封装不同 Agent 的任务规范、处理边界、输出要求与领域知识。

当前内置三类 Skills：

```text
skills/general_assistant/SKILL.md         # 通用请求：咨询、澄清、简单任务和能力分流
skills/technical_support/SKILL.md         # 技术支持：故障排查、接口错误、部署配置和安全边界
```

## Skill 文件格式

推荐每个 Skill 使用独立目录，并将主文件命名为 `SKILL.md`：

```text
skills/<skill_name>/SKILL.md
```

文件顶部使用简单 front matter：

```markdown
---
name: 技术支持处理规范
description: 适用于 TechnicalAgent 的故障排查和升级处理规范
keywords: 报错,错误,接口,API,部署,超时,500,401,日志
agents: technical
enabled: true
---
```

字段说明：

- `name`：Skill 展示名称，会出现在注入给模型的 prompt 中。
- `description`：简短说明，方便 `/skills` 接口排查。
- `keywords`：触发关键词，用户消息命中后才注入；多个关键词用英文逗号或中文逗号分隔均可。
- `agents`：适用 Agent，可填 `general`、`technical`、`career`，多个值用逗号分隔。
- `enabled`：是否启用，支持 `true/false`。

## 编写要求

- 重要规则放在文档前半部分，因为过长内容会按 prompt 预算截断。
- 一类 Skill 只描述一类职责，不同 Skill 应保持职责边界清晰，不要把技术、职业求职和通用请求规则混在一个文件里。
- 必须包含“角色定位”“处理流程”“升级条件”“禁止事项”等稳定章节。
- 对用户隐私、支付、密码、验证码、API Key、Token 等敏感信息必须写明禁止收集或禁止公开。
- 对无法保证的事项使用保守措辞，例如“通常”“预计”“需要核验后确认”。
- 对于信息不足、能力边界或需要进一步确认的场景，应明确说明限制和下一步处理方式。

## 热加载

修改 Skill 文件后，不需要重启服务，调用：

```bash
curl -X POST http://localhost:8000/skills/reload
```

查看加载结果和解析错误：

```bash
curl http://localhost:8000/skills
```
