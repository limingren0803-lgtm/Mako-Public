(() => {
  const skills = {
    career_profile: {
      code: "CAREER PROFILE", title: "背景诊断", action: "开始背景诊断",
      description: "整理教育、项目、实习和技能信息，识别已经有证据支持的优势与仍需补充的部分。",
      requestLabel: "你希望重点了解哪部分求职背景",
      placeholder: "例如：请分析我的背景更适合哪些数据分析方向，并指出目前证据不足的部分。",
      inputHint: "建议说明学历、专业、毕业时间、目标地区，以及希望重点判断的方向。",
      uploadDescription: "可上传简历文本或经历清单；提交后将作为本次背景分析输入",
      prepare: ["教育背景与预计毕业时间", "项目、实习和技能经历", "目标城市、行业或岗位方向"],
      guide: ["整理用户明确提供的经历", "区分事实、推断与缺失信息", "给出下一步补充建议"],
      output: "结果会区分已有优势、证据不足和仍需确认的信息，不会补写你没有提供的经历。",
      help: [
        ["经历不完整怎么办", "先提交能够确认的内容，结果会列出仍需补充的信息。"],
        ["暂时没有明确目标", "可以先说明专业、经历和城市偏好，让 Mako 比较几个可行方向。"],
        ["信息写错了", "修改输入并重新提交；本次页面不会自动把修改写入长期画像。"]
      ],
      usesJobContext: false
    },
    career_match: {
      code: "CAREER MATCH", title: "方向匹配", action: "开始方向匹配",
      description: "结合个人经历和岗位偏好，比较可行方向；结论保留证据边界，不使用空泛的综合评分。",
      requestLabel: "你希望比较哪些方向或岗位",
      placeholder: "例如：结合我的经历，比较产品分析、商业分析和数据运营三个方向。",
      inputHint: "可以填写目标城市、行业、岗位类型和不考虑的方向，帮助缩小范围。",
      uploadDescription: "可上传简历文本或经历说明；也可以在下方选择系统职位或提供 JD",
      prepare: ["个人经历和已确认技能", "目标城市、行业与岗位偏好", "系统职位或完整目标 JD"],
      guide: ["确认目标城市与岗位范围", "比较现有证据和岗位要求", "列出适配项、差距与待确认信息"],
      output: "系统职位支持按审核过的 JD 原文逐项核对；自行提供 JD 时给出本次方向分析和证据缺口。",
      help: [
        ["没有找到目标岗位", "调整关键词或时效范围；也可以切换到“自行提供 JD”。"],
        ["岗位没有结构化要求", "该岗位仍可用于常规方向分析，但暂不提供逐项状态。"],
        ["职位信息可能过期", "查看最近核验时间，并在投递前打开官方链接确认。"]
      ],
      usesJobContext: true
    },
    career_jd: {
      code: "CAREER JD", title: "JD 分析", action: "开始 JD 分析",
      description: "拆解目标岗位的职责、硬性条件和隐含要求，标出需要用户确认的判断。",
      requestLabel: "你希望重点拆解 JD 的哪些部分",
      placeholder: "粘贴或上传完整 JD，并说明你最关心的要求或疑问。",
      inputHint: "可以关注硬性条件、核心职责、关键词、潜在追问或与你经历的差距。",
      uploadDescription: "建议上传完整 JD；也可以同时提供个人经历用于对照",
      prepare: ["完整职位名称与 JD 原文", "最希望确认的要求", "用于对照的个人经历（选填）"],
      guide: ["识别职责、技能和资格要求", "区分原文与分析判断", "生成后续匹配所需的证据清单"],
      output: "结果会保留 JD 原文与分析判断的边界，并指出需要个人证据才能确认的项目。",
      help: [
        ["JD 只有很短一段", "提交现有内容即可；缺失的职责或要求会被标记为无法判断。"],
        ["只有职位链接", "当前不会自动访问链接，请从官方页面复制 JD 原文后提交。"],
        ["岗位要求写得模糊", "说明你最关心的问题，Mako 会区分明确条件与需要进一步确认的内容。"]
      ],
      usesJobContext: true
    },
    career_resume: {
      code: "CAREER RESUME", title: "简历优化", action: "开始简历分析",
      description: "依据目标 JD 和已确认经历检查简历表达，优先保证事实完整，不补写未经确认的成果。",
      requestLabel: "你希望检查或调整哪部分简历",
      placeholder: "上传简历文本，并说明目标岗位。需要修改的部分也可以直接粘贴在这里。",
      inputHint: "建议说明目标岗位、希望保留的内容，以及不能改变的事实边界。",
      uploadDescription: "上传简历文本；如果有目标 JD，也可以放在同一文件中并标明分段",
      prepare: ["当前简历文本", "目标岗位或 JD", "可以确认的数据、职责和成果"],
      guide: ["检查经历与目标 JD 的关联", "标出需要补证据的表达", "给出基于原事实的修改建议"],
      output: "结果优先指出事实风险和证据缺口，再给出不改变原事实的表达建议。",
      help: [
        ["简历内容较长", "优先提交与目标岗位最相关的经历，每次聚焦一到两个模块。"],
        ["没有量化数据", "不要补写数字，可以说明实际职责、过程和能够确认的结果。"],
        ["建议与事实不符", "不要采用该建议，补充真实情况后重新分析。"]
      ],
      usesJobContext: true
    },
    career_interview: {
      code: "CAREER INTERVIEW", title: "面试准备", action: "生成准备方案",
      description: "围绕目标岗位和个人真实经历生成准备重点，帮助用户形成可验证、可追问的回答。",
      requestLabel: "你正在准备什么岗位和面试阶段",
      placeholder: "例如：我要面试商业分析实习，请根据 JD 和我的经历整理重点问题。",
      inputHint: "可以说明公司、岗位、面试轮次、预计时间和最担心的问题。",
      uploadDescription: "可上传 JD、简历文本或经历清单，帮助形成针对性准备内容",
      prepare: ["公司、岗位与面试轮次", "目标 JD 和个人简历", "可以深入追问的真实案例"],
      guide: ["识别岗位重点与高概率追问", "从个人经历中选择可用案例", "指出回答中的事实边界和准备缺口"],
      output: "结果会整理准备重点、可能追问和可用案例，不会为你虚构面试经历。",
      help: [
        ["还不知道面试轮次", "先按岗位通用能力准备，确认轮次后再补充针对性内容。"],
        ["没有直接相关经历", "可以提供课程项目、社团或兼职经历，重点核对可迁移能力。"],
        ["问题范围太大", "优先选择一个岗位和一次面试阶段，完成后再扩展。"]
      ],
      usesJobContext: true
    },
    career_planning: {
      code: "CAREER PLANNING", title: "行动规划", action: "生成行动计划",
      description: "将目标、差距和时间约束整理成阶段任务，并保留由用户调整优先级的空间。",
      requestLabel: "你希望在什么时间内完成什么求职目标",
      placeholder: "例如：我计划三个月内寻找国内大厂或外企的数据分析实习，请制定每周行动计划。",
      inputHint: "建议说明截止时间、每周可投入时间、当前进度和需要优先解决的短板。",
      uploadDescription: "可上传现有求职计划、岗位清单或阶段复盘记录",
      prepare: ["目标岗位和时间节点", "当前进度与每周可用时间", "希望优先补强的能力或材料"],
      guide: ["确认时间、目标和现实约束", "按优先级拆分阶段任务", "设置可检查的完成标准"],
      output: "结果会按优先级和时间拆分任务，用户可以根据现实变化调整顺序。",
      help: [
        ["目标还不明确", "先建立两到三个候选方向，并把方向确认作为第一阶段任务。"],
        ["计划无法按时完成", "补充新的时间约束，重新调整范围和优先级。"],
        ["任务太多不知道先做什么", "说明最近的截止时间，优先处理影响投递的必要材料。"]
      ],
      usesJobContext: true
    }
  };

  const nav = document.getElementById("skill-nav");
  const request = document.getElementById("request");
  const fileInput = document.getElementById("material-file");
  const fileStatus = document.getElementById("file-status");
  const clearFile = document.getElementById("clear-file");
  const submit = document.getElementById("submit");
  const submitStatus = document.getElementById("submit-status");
  const result = document.getElementById("result");
  const emptyOutput = document.getElementById("empty-output");
  const structuredMatch = document.getElementById("structured-match");
  const jobQuery = document.getElementById("job-query");
  const loadJobsButton = document.getElementById("load-jobs");
  const jobSelect = document.getElementById("job-select");
  const jobStatus = document.getElementById("job-status");
  const requirementPanel = document.getElementById("requirement-panel");
  const requirementList = document.getElementById("requirement-list");
  const evidenceDetail = document.getElementById("evidence-detail");
  const confirmInput = document.getElementById("confirm-input");
  const manualJd = document.getElementById("manual-jd");
  const manualJdSource = document.getElementById("manual-jd-source");
  const verifiedJobPanel = document.getElementById("verified-job-panel");
  const manualJdPanel = document.getElementById("manual-jd-panel");
  const jobOptions = document.getElementById("job-options");
  const resultState = document.getElementById("result-state");
  const resultActions = document.getElementById("result-actions");
  const resultActionStatus = document.getElementById("result-action-status");
  let activeSkill = "career_profile";
  let fileText = "";
  let conversationId = null;
  let jobsLoaded = false;
  const jobs = new Map();
  const userId = `ui_${crypto.randomUUID().replaceAll("-", "")}`;

  const updateFlow = (step) => {
    document.querySelectorAll("[data-flow-step]").forEach(item => {
      item.classList.toggle("current", Number(item.dataset.flowStep) === step);
    });
  };

  const setSubmitStatus = (message = "", state = "") => {
    submitStatus.textContent = message;
    submitStatus.className = `status-message${state ? ` ${state}` : ""}`;
  };

  const invalidateConfirmation = () => {
    if (confirmInput.checked) confirmInput.checked = false;
    updateFlow(2);
  };

  const resetOutput = (message = "完成材料确认后，结果会显示在这里。") => {
    result.replaceChildren();
    result.hidden = true;
    emptyOutput.hidden = false;
    emptyOutput.textContent = message;
    resultActions.hidden = true;
    resultActionStatus.textContent = "";
    resultState.textContent = "等待材料";
  };

  const renderList = (target, items, ordered = false) => {
    const list = document.createElement(ordered ? "ol" : "ul");
    items.forEach(value => {
      const item = document.createElement("li");
      item.textContent = value;
      list.appendChild(item);
    });
    target.replaceChildren(...list.children);
  };

  const renderHelp = skill => {
    document.getElementById("guide-skill").textContent = skill.title;
    renderList(document.getElementById("skill-prepare"), skill.prepare);
    renderList(document.getElementById("skill-guide"), skill.guide, true);
    document.getElementById("skill-output").textContent = skill.output;
    const help = document.getElementById("skill-help");
    help.replaceChildren();
    skill.help.forEach(([question, answer]) => {
      const item = document.createElement("section");
      item.className = "help-item";
      const title = document.createElement("b");
      title.textContent = question;
      const detail = document.createElement("p");
      detail.textContent = answer;
      item.append(title, detail);
      help.appendChild(item);
    });
  };

  const matchSource = () => document.querySelector('input[name="match-source"]:checked')?.value || "verified";

  const updateMatchSource = () => {
    const manual = matchSource() === "manual";
    verifiedJobPanel.hidden = manual;
    manualJdPanel.hidden = !manual;
    if (!manual && !jobsLoaded) loadWorkspaceJobs();
    if (manual && manualJd.value.trim()) updateFlow(2);
    if (activeSkill === "career_match") invalidateConfirmation();
    setSubmitStatus();
  };

  const updateSkill = (name) => {
    activeSkill = name;
    const skill = skills[name];
    document.getElementById("skill-code").textContent = skill.code;
    document.getElementById("skill-title").textContent = skill.title;
    document.getElementById("skill-description").textContent = skill.description;
    document.getElementById("request-label").textContent = skill.requestLabel;
    document.getElementById("request-hint").textContent = skill.inputHint;
    document.getElementById("upload-description").textContent = skill.uploadDescription;
    renderHelp(skill);
    request.placeholder = skill.placeholder;
    submit.textContent = skill.action;
    nav.querySelectorAll("button").forEach(button => button.classList.toggle("active", button.dataset.skill === name));
    structuredMatch.hidden = name !== "career_match";
    jobOptions.hidden = !skill.usesJobContext;
    jobOptions.open = name === "career_match";
    if (name === "career_match") updateMatchSource();
    confirmInput.checked = false;
    setSubmitStatus();
    resetOutput();
    updateFlow(1);
  };

  const responseMessage = payload => payload?.error?.message || payload?.detail || "请求未完成";

  const readResponse = async response => {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error("服务返回了无法识别的响应，请稍后重试。");
    }
    return response.json();
  };

  const selectedJob = () => jobs.get(jobSelect.value);

  const loadWorkspaceJobs = async () => {
    loadJobsButton.disabled = true;
    jobStatus.classList.remove("error");
    jobStatus.textContent = "正在读取已核验岗位…";
    requirementPanel.hidden = true;
    requirementList.replaceChildren();
    try {
      const params = new URLSearchParams({
        max_age_days: document.getElementById("job-age").value,
        limit: "50"
      });
      if (jobQuery.value.trim()) params.set("query", jobQuery.value.trim());
      const response = await fetch(`/v2/workspace/jobs?${params}`);
      const payload = await readResponse(response);
      if (!response.ok) throw new Error(responseMessage(payload));
      jobs.clear();
      jobSelect.replaceChildren(new Option("未选择，使用常规方向分析", ""));
      payload.items.forEach(item => {
        const key = `${item.job_id}|${item.job_version_id}`;
        jobs.set(key, item);
        const location = item.locations.length ? ` · ${item.locations.join(" / ")}` : "";
        const state = item.match_ready ? "" : " · 暂无结构化要求";
        const option = new Option(`${item.company_name} · ${item.title}${location}${state}`, key);
        option.disabled = !item.match_ready;
        jobSelect.appendChild(option);
      });
      const readyCount = payload.items.filter(item => item.match_ready).length;
      jobStatus.textContent = payload.count
        ? `找到 ${payload.count} 个近期岗位，其中 ${readyCount} 个有可确认的 JD 原文条目。`
        : "当前筛选条件下没有近期已核验岗位，可调整范围、切换到自行提供 JD，或使用常规方向分析。";
      jobsLoaded = true;
    } catch (error) {
      jobStatus.textContent = `${error.message || "岗位列表暂时不可用"} 可以切换到自行提供 JD，当前输入不会丢失。`;
      jobStatus.classList.add("error");
    } finally {
      loadJobsButton.disabled = false;
    }
  };

  const loadRequirements = async () => {
    requirementPanel.hidden = true;
    requirementList.replaceChildren();
    const job = selectedJob();
    if (!job) return;
    jobStatus.textContent = "正在读取岗位要求…";
    try {
      const age = document.getElementById("job-age").value;
      const url = `/v2/workspace/jobs/${encodeURIComponent(job.job_id)}/versions/${encodeURIComponent(job.job_version_id)}/requirements?max_age_days=${age}`;
      const response = await fetch(url);
      const payload = await readResponse(response);
      if (!response.ok) throw new Error(responseMessage(payload));
      payload.items.forEach(item => {
        const option = document.createElement("div");
        option.className = "requirement-option";
        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = item.requirement_id;
        checkbox.checked = true;
        const text = document.createElement("span");
        text.textContent = item.text;
        label.append(checkbox, text);
        const termLabel = document.createElement("label");
        termLabel.className = "term-label";
        termLabel.textContent = "用于核对的关键词";
        const terms = document.createElement("input");
        terms.id = `terms-${item.requirement_id.replaceAll(":", "-")}`;
        termLabel.htmlFor = terms.id;
        terms.type = "text";
        terms.className = "term-input";
        terms.dataset.requirementId = item.requirement_id;
        terms.maxLength = 1000;
        terms.placeholder = "填写 JD 原文中的技能或条件，用顿号分隔";
        terms.value = item.normalized_terms.join("、");
        if (item.extraction_status === "parsed") {
          terms.readOnly = true;
          termLabel.textContent = "已复核关键词";
        }
        option.append(label, termLabel, terms);
        requirementList.appendChild(option);
      });
      requirementPanel.hidden = payload.count === 0;
      jobStatus.textContent = payload.count
        ? `已载入 ${payload.count} 项 JD 原文条目。请选择本次要核对的项目，并补充原文中的关键词。`
        : "该岗位当前没有可核对的结构化 JD 条目，请改用常规方向分析。";
    } catch (error) {
      jobStatus.textContent = error.message || "岗位要求暂时不可用";
      jobStatus.classList.add("error");
    }
  };

  const evidenceItems = (...values) => {
    const items = [];
    values.filter(Boolean).forEach(value => {
      let current = "";
      value.split(/\r?\n/).map(line => line.trim()).filter(Boolean).forEach(line => {
        if (line.length > 4000) {
          if (current) items.push(current);
          current = "";
          for (let offset = 0; offset < line.length; offset += 4000) items.push(line.slice(offset, offset + 4000));
        } else if (!current || current.length + line.length + 1 <= 4000) {
          current = current ? `${current}\n${line}` : line;
        } else {
          items.push(current);
          current = line;
        }
      });
      if (current) items.push(current);
    });
    return items;
  };

  const markResultReady = () => {
    emptyOutput.hidden = true;
    result.hidden = false;
    resultActions.hidden = false;
    resultState.textContent = "分析完成";
    resultActionStatus.textContent = "";
  };

  const clearCurrentInput = () => {
    request.value = "";
    document.getElementById("request-count").textContent = "0";
    fileInput.value = "";
    fileText = "";
    clearFile.hidden = true;
    fileStatus.textContent = "当前支持 UTF-8 编码的 .txt、.md，文本不超过 15000 字符。PDF 与 DOCX 暂未接入。";
    fileStatus.classList.remove("error");
    evidenceDetail.value = "";
    manualJd.value = "";
    manualJdSource.value = "";
    document.getElementById("manual-jd-count").textContent = "0";
    confirmInput.checked = false;
    jobQuery.value = "";
    jobSelect.value = "";
    requirementPanel.hidden = true;
    requirementList.replaceChildren();
    const verifiedSource = document.querySelector('input[name="match-source"][value="verified"]');
    if (verifiedSource) verifiedSource.checked = true;
    if (activeSkill === "career_match") updateMatchSource();
    setSubmitStatus();
    resetOutput();
    updateFlow(1);
    request.focus();
  };

  const renderStructuredResult = (payload, skill) => {
    const statusText = {met: "已覆盖", partial: "部分覆盖", gap: "存在差距", unknown: "待补充", not_applicable: "不适用"};
    result.replaceChildren();
    const heading = document.createElement("div");
    heading.className = "result-heading";
    const title = document.createElement("h3");
    title.textContent = `${payload.company_name} · ${payload.title}`;
    const source = document.createElement("a");
    source.href = payload.source_url;
    source.target = "_blank";
    source.rel = "noreferrer";
    source.textContent = "查看官方岗位";
    heading.append(title, source);
    const summary = document.createElement("div");
    summary.className = "match-summary";
    [["已覆盖", payload.summary.met], ["部分覆盖", payload.summary.partial], ["存在差距", payload.summary.gap], ["待补充", payload.summary.unknown]].forEach(([label, count]) => {
      const item = document.createElement("div");
      const value = document.createElement("strong");
      value.textContent = count;
      const name = document.createElement("span");
      name.textContent = label;
      item.append(value, name);
      summary.appendChild(item);
    });
    const list = document.createElement("div");
    list.className = "match-items";
    payload.items.forEach(item => {
      const article = document.createElement("article");
      article.className = `match-item status-${item.decision.status}`;
      const badge = document.createElement("span");
      badge.className = "status-badge";
      badge.textContent = statusText[item.decision.status] || item.decision.status;
      const requirement = document.createElement("h4");
      requirement.textContent = item.requirement.text;
      const reason = document.createElement("p");
      reason.textContent = item.decision.reason;
      article.append(badge, requirement, reason);
      if (item.decision.questions_to_confirm.length) {
        const questions = document.createElement("ul");
        item.decision.questions_to_confirm.forEach(value => {
          const question = document.createElement("li");
          question.textContent = value;
          questions.appendChild(question);
        });
        article.appendChild(questions);
      }
      list.appendChild(article);
    });
    const meta = document.createElement("div");
    meta.className = "result-meta";
    meta.textContent = `处理板块：${skill.title} · 本次使用 ${payload.evidence_count} 项已确认材料 · 结果未写入长期画像`;
    result.append(heading, summary, list, meta);
  };

  loadJobsButton.addEventListener("click", loadWorkspaceJobs);
  document.querySelectorAll('input[name="match-source"]').forEach(input => input.addEventListener("change", updateMatchSource));
  jobQuery.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadWorkspaceJobs();
    }
  });
  jobSelect.addEventListener("change", () => {
    invalidateConfirmation();
    loadRequirements();
  });
  requirementList.addEventListener("input", invalidateConfirmation);
  document.getElementById("job-age").addEventListener("change", () => {
    invalidateConfirmation();
    jobsLoaded = false;
    if (activeSkill === "career_match") loadWorkspaceJobs();
  });
  document.getElementById("job-mode").addEventListener("change", invalidateConfirmation);

  manualJd.addEventListener("input", () => {
    document.getElementById("manual-jd-count").textContent = manualJd.value.length;
    invalidateConfirmation();
  });
  manualJdSource.addEventListener("input", invalidateConfirmation);

  nav.addEventListener("click", event => {
    const button = event.target.closest("button[data-skill]");
    if (button) updateSkill(button.dataset.skill);
  });

  request.addEventListener("input", () => {
    document.getElementById("request-count").textContent = request.value.length;
    invalidateConfirmation();
  });

  evidenceDetail.addEventListener("input", invalidateConfirmation);

  confirmInput.addEventListener("change", event => {
    updateFlow(event.target.checked ? 3 : 2);
  });

  document.getElementById("clear-input").addEventListener("click", clearCurrentInput);
  document.getElementById("restart-flow").addEventListener("click", clearCurrentInput);

  document.getElementById("copy-result").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(result.innerText.trim());
      resultActionStatus.textContent = "结果已复制。";
    } catch (_) {
      resultActionStatus.textContent = "浏览器未允许复制，请手动选择结果文本。";
    }
  });

  document.getElementById("download-result").addEventListener("click", () => {
    const blob = new Blob([result.innerText.trim()], {type: "text/plain;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `mako-${activeSkill}-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    resultActionStatus.textContent = "结果已下载。";
  });

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    fileText = "";
    clearFile.hidden = true;
    fileStatus.classList.remove("error");
    if (!file) return;
    invalidateConfirmation();
    const suffix = file.name.split(".").pop().toLowerCase();
    if (!["txt", "md"].includes(suffix) || file.size > 64 * 1024) {
      fileInput.value = "";
      fileStatus.textContent = "文件未读取：请使用不超过 64 KB 的 UTF-8 TXT 或 Markdown 文件。";
      fileStatus.classList.add("error");
      return;
    }
    try {
      const bytes = await file.arrayBuffer();
      fileText = new TextDecoder("utf-8", {fatal: true}).decode(bytes);
      if (fileText.length > 15000) {
        throw new Error("文件文本超过 15000 字符");
      }
      fileStatus.textContent = `${file.name} · ${Math.ceil(file.size / 1024)} KB · 已读取，提交后发送给 Mako`;
      clearFile.hidden = false;
      invalidateConfirmation();
    } catch (_) {
      fileStatus.textContent = "文件读取失败，请检查文件后重试。";
      fileStatus.classList.add("error");
    }
  });

  clearFile.addEventListener("click", () => {
    fileInput.value = "";
    fileText = "";
    clearFile.hidden = true;
    fileStatus.textContent = "当前支持 UTF-8 编码的 .txt、.md，文本不超过 15000 字符。PDF 与 DOCX 暂未接入。";
    invalidateConfirmation();
  });

  submit.addEventListener("click", async () => {
    setSubmitStatus();
    const manualMatch = activeSkill === "career_match" && matchSource() === "manual";
    if (!request.value.trim() && !fileText.trim() && !evidenceDetail.value.trim() && !manualJd.value.trim()) {
      setSubmitStatus("请填写问题、经历材料或目标 JD。", "error");
      return;
    }
    if (manualMatch && !manualJd.value.trim()) {
      setSubmitStatus("已选择自行提供 JD，请粘贴完整职位描述。", "error");
      return;
    }
    if (!confirmInput.checked) {
      setSubmitStatus("请先检查并确认本次输入材料。", "error");
      return;
    }
    const skill = skills[activeSkill];
    const job = activeSkill === "career_match" && !manualMatch ? selectedJob() : null;
    if (job) {
      const requirementIds = [...requirementList.querySelectorAll("input:checked")].map(item => item.value);
      const requirementTerms = {};
      requirementIds.forEach(requirementId => {
        const input = requirementList.querySelector(`.term-input[data-requirement-id="${CSS.escape(requirementId)}"]`);
        requirementTerms[requirementId] = (input?.value || "")
          .split(/[,，、;；\n]+/)
          .map(value => value.trim())
          .filter(Boolean);
      });
      const evidence = evidenceItems(evidenceDetail.value, fileText);
      if (!requirementIds.length) {
        setSubmitStatus("请至少保留一项需要核对的岗位要求。", "error");
        return;
      }
      if (!evidence.length) {
        setSubmitStatus("逐项匹配需要填写已确认经历或上传材料。", "error");
        return;
      }
      if (evidence.length > 20 || evidence.reduce((total, item) => total + item.length, 0) > 20000) {
        setSubmitStatus("本次经历材料超过 20 项或 20000 字符，请缩短后重试。", "error");
        return;
      }
      const missingTerms = requirementIds.filter(item => !requirementTerms[item].length);
      if (missingTerms.length) {
        setSubmitStatus("请为选中的岗位要求填写 JD 原文中的核对关键词。", "error");
        return;
      }
      submit.disabled = true;
      setSubmitStatus("正在逐项核对，请不要重复提交。", "busy");
      try {
        const url = `/v2/workspace/jobs/${encodeURIComponent(job.job_id)}/versions/${encodeURIComponent(job.job_version_id)}/match`;
        const response = await fetch(url, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            requirement_ids: requirementIds,
            requirement_terms: requirementTerms,
            evidence,
            material_confirmed: true,
            job_max_age_days: Number(document.getElementById("job-age").value)
          })
        });
        const payload = await readResponse(response);
        if (!response.ok) throw new Error(responseMessage(payload));
        renderStructuredResult(payload, skill);
        markResultReady();
        setSubmitStatus("逐项匹配完成。", "success");
        updateFlow(4);
        document.getElementById("output-card").scrollIntoView({behavior: "smooth", block: "start"});
      } catch (error) {
        setSubmitStatus(`${error.message || "服务暂时不可用"} 输入内容已保留，可以检查后重新提交。`, "error");
        resultState.textContent = "需要处理";
      } finally {
        submit.disabled = false;
      }
      return;
    }
    const material = fileText.trim() ? `\n\n用户上传材料：\n${fileText.trim()}` : "";
    const experience = activeSkill === "career_match" && evidenceDetail.value.trim()
      ? `\n\n用户确认的相关经历：\n${evidenceDetail.value.trim()}`
      : "";
    let source = "";
    if (manualMatch && manualJdSource.value.trim()) {
      try {
        const parsed = new URL(manualJdSource.value.trim());
        if (parsed.protocol !== "https:") throw new Error();
        source = `\n官方职位链接（仅作本次材料来源标记，不访问）：${parsed.href}`;
      } catch (_) {
        setSubmitStatus("官方职位链接需要使用完整的 HTTPS 地址，或将该项留空。", "error");
        return;
      }
    }
    const jd = manualMatch
      ? `\n\n用户自行提供的目标 JD（仅用于本次请求）：\n${manualJd.value.trim()}${source}`
      : "";
    const question = request.value.trim() || `请完成本次${skill.title}，并明确区分已有事实、分析判断和待确认信息。`;
    const message = `[${skill.title}]\n${question}${jd}${experience}${material}`;
    if (message.length > 20000) {
      setSubmitStatus("输入总长度超过 20000 字符，请缩短问题、JD 或经历材料。", "error");
      return;
    }
    submit.disabled = true;
    setSubmitStatus("正在分析，请不要重复提交。", "busy");
    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          message,
          user_id: userId,
          conv_id: conversationId,
          job_max_age_days: Number(document.getElementById("job-age").value),
          job_data_mode: document.getElementById("job-mode").value
        })
      });
      const payload = await readResponse(response);
      if (!response.ok) throw new Error(payload?.error?.message || "请求未完成");
      conversationId = payload.conv_id;
      result.replaceChildren();
      result.textContent = payload.response;
      const meta = document.createElement("div");
      meta.className = "result-meta";
      meta.textContent = `处理板块：${skill.title} · 请求编号：${payload.request_id}`;
      result.appendChild(meta);
      markResultReady();
      setSubmitStatus("分析完成。", "success");
      updateFlow(4);
      document.getElementById("output-card").scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) {
      setSubmitStatus(`${error.message || "服务暂时不可用"} 输入内容已保留，可以检查后重新提交。`, "error");
      resultState.textContent = "需要处理";
    } finally {
      submit.disabled = false;
    }
  });

  updateSkill(activeSkill);
})();
