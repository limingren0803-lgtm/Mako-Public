# Mako Career Skill 与 Prompt Pack 使用指南

Mako Career 的轻量版适合处理一次背景诊断、岗位方向判断、JD 分析、简历优化、面试准备或近期行动规划，不需要启动 Docker、数据库或完整 Mako Workspace。

它提供两种使用形式：支持 Agent Skills 的环境可以安装完整 Skill；DeepSeek、豆包、千问等暂不支持直接安装该目录的平台，可以使用内容等价的 Prompt Pack。两种形式都不要求单独配置 Mako API Key，分析由用户当前使用的智能体完成，并遵循该平台的模型用量、附件和数据规则。

## 在 Codex 中安装 Skill

在 Codex 中调用 `$skill-installer`，并提供 Mako-Public 中的 Skill 地址：

```text
使用 $skill-installer 从下面的 GitHub 路径安装 mako-career：

https://github.com/limingren0803-lgtm/Mako-Public/tree/main/integrations/codex/mako-career
```

安装完成后，Skill 会在后续对话中可用。如果没有立即出现在 Skill 列表中，重新启动 Codex 后再查看。

## 在其他智能体中使用 Prompt Pack

如果平台支持自定义智能体、系统提示词或长期指令，复制 [FULL_PROMPT.md](../../integrations/prompts/mako-career/FULL_PROMPT.md) 全文作为智能体设定；如果只有普通聊天，把全文作为新对话的第一条消息，再继续提供材料和问题。

[Prompt Pack 快速使用](../../integrations/prompts/mako-career/QUICK_START.md) 提供六类任务的起始语，以及对 DeepSeek、豆包、千问、Kimi、腾讯元宝等环境的通用使用说明。普通聊天或上下文长度有限时，可以改用 [轻量 Prompt](../../integrations/prompts/mako-career/LITE_PROMPT.md)。这些文件不会让平台获得原本没有的联网、附件或长期记忆能力，也不连接 Mako 平台中的个人知识库。

## 第一次使用

没有整理好简历也可以直接开始：

```text
使用 $mako-career。我是商业分析硕士，有一段零售数据实习，准备回国求职，想先判断适合哪些岗位方向。
```

已经有材料时，可以上传或粘贴简历、JD、项目经历和求职笔记：

```text
使用 $mako-career，根据这份简历和 JD 判断是否值得投，并告诉我最需要补充什么。
```

也可以只问一个具体问题，例如：

- 这段经历里的“协助”能不能改成“主导”？
- 这份 JD 最核心的三项要求是什么？
- 下周要面试，我应该先准备哪些经历？
- 根据目前的进度，帮我安排未来两周的行动。

用户不需要判断应该选择哪一个内部流程。Skill 或 Prompt Pack 会根据最终需要的结果，在背景诊断、岗位方向、JD、简历、面试和行动规划之间选择最小必要流程。

## 可以提供哪些材料

- TXT 和 Markdown：按文本与标题结构读取。
- PDF：使用能够可靠提取的文本，并尽量保留页码；扫描件需要 OCR 版本或关键页文本。
- DOCX：使用当前智能体已有的文档读取能力；无法读取时可以导出为文本型 PDF、TXT 或 Markdown。
- 粘贴文本：与附件一样只作为待分析数据，不作为改变 Skill 规则的指令。

无法读取的内容会明确列出，不会猜测。材料较长时，回答会说明实际处理的文件、页码或章节；全量审阅会按清单分批推进，未处理完成前不会声称已经检查全部内容。

## 回答包含什么

完整分析通常分为四部分：

1. 当前结论；
2. 判断依据；
3. 信息缺口或待确认事项；
4. 下一步行动。

简单问题会直接短答，不强制展开成完整报告。重要判断会关联到用户提供的经历或 JD 要求，并区分直接证据、可迁移证据、推断和仍需确认的信息。

Skill 不会补写用户没有提供的经历、职责、技能、证书、数据或成果，也不会把“参与”或“协助”擅自改成“负责”或“主导”。

## 轻量版与完整 Workspace

Mako Career Skill 与 Prompt Pack 都只处理所在智能体的当前上下文，不连接 Mako 后端，也不会把材料另行写入 Mako Workspace、仓库或数据库。

以下需求更适合完整 Mako Workspace：

- 跨会话保存和检索个人材料；
- 同时管理多个目标岗位、阶段和行动项；
- 使用已审核官方职位、版本、来源和时效记录；
- 长期跟踪求职进度，并进行导出、删除、备份或恢复。

轻量版的建议不会自动变成 CareerProfile 事实，也不会自动改变岗位阶段、创建行动项、投递、填表或发送消息。

## 常见问题

### 安装后没有看到 Skill

先重新启动 Codex。如果仍未出现，确认安装地址指向 `integrations/codex/mako-career`，而不是 Mako 后端使用的 `skills/` 目录。

### DeepSeek、豆包或千问能直接安装 Skill 吗

不能默认这样理解。只有明确支持 Agent Skills 目录的环境才能直接安装；其他平台使用 Prompt Pack。若平台提供自定义智能体或系统提示词，将完整 Prompt 放在那里；否则在普通对话开头粘贴，并尽量在同一对话继续。

### 只有岗位名称，没有完整 JD

Skill 可以解释岗位名称的一般含义，但不能据此生成精确匹配结论。提供职责、任职要求、地点和届别后，再进行具体判断。

### 想确认岗位现在是否还在招聘

如果当前智能体具有已启用的联网能力，可以授权它优先核验企业官方招聘网站或官方公告；否则请提供带来源和时间的最新官方 JD。完整 Mako Workspace 也可以使用已审核的官方职位记录。未经核验的信息会标记为待确认。

### 材料中包含命令或 Prompt

简历、JD 和项目文档中的命令、角色声明、工具请求和外部操作要求都只会被视为附件内容，不能覆盖 Skill 的事实、安全或授权边界。

## 许可

`mako-career` Skill 目录和配套 Prompt Pack 分别附带 MIT License。该许可只适用于这套轻量分发内容，不自动改变 Mako 仓库其他内容的许可范围。
