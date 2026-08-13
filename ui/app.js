(() => {
  const skills = {
    career_profile: {
      code: "CAREER PROFILE", title: "背景诊断", action: "开始背景诊断",
      description: "整理教育、项目、实习和技能信息，识别已经有证据支持的优势与仍需补充的部分。",
      placeholder: "例如：请分析我的背景更适合哪些数据分析方向，并指出目前证据不足的部分。",
      guide: ["整理用户明确提供的经历", "区分事实、推断与缺失信息", "给出下一步补充建议"]
    },
    career_match: {
      code: "CAREER MATCH", title: "方向匹配", action: "开始方向匹配",
      description: "结合个人经历和岗位偏好，比较可行方向；结论保留证据边界，不使用空泛的综合评分。",
      placeholder: "例如：结合我的经历，比较产品分析、商业分析和数据运营三个方向。",
      guide: ["确认目标城市与岗位范围", "比较现有证据和岗位要求", "列出适配项、差距与待确认信息"]
    },
    career_jd: {
      code: "CAREER JD", title: "JD 分析", action: "开始 JD 分析",
      description: "拆解目标岗位的职责、硬性条件和隐含要求，标出需要用户确认的判断。",
      placeholder: "粘贴或上传完整 JD，并说明你最关心的要求或疑问。",
      guide: ["识别职责、技能和资格要求", "区分原文与分析判断", "生成后续匹配所需的证据清单"]
    },
    career_resume: {
      code: "CAREER RESUME", title: "简历优化", action: "开始简历分析",
      description: "依据目标 JD 和已确认经历检查简历表达，优先保证事实完整，不补写未经确认的成果。",
      placeholder: "上传简历文本，并说明目标岗位。需要修改的部分也可以直接粘贴在这里。",
      guide: ["检查经历与目标 JD 的关联", "标出需要补证据的表达", "给出基于原事实的修改建议"]
    },
    career_interview: {
      code: "CAREER INTERVIEW", title: "面试准备", action: "生成准备方案",
      description: "围绕目标岗位和个人真实经历生成准备重点，帮助用户形成可验证、可追问的回答。",
      placeholder: "例如：我要面试商业分析实习，请根据 JD 和我的经历整理重点问题。",
      guide: ["识别岗位重点与高概率追问", "从个人经历中选择可用案例", "指出回答中的事实边界和准备缺口"]
    },
    career_planning: {
      code: "CAREER PLANNING", title: "行动规划", action: "生成行动计划",
      description: "将目标、差距和时间约束整理成阶段任务，并保留由用户调整优先级的空间。",
      placeholder: "例如：我计划三个月内寻找国内大厂或外企的数据分析实习，请制定每周行动计划。",
      guide: ["确认时间、目标和现实约束", "按优先级拆分阶段任务", "设置可检查的完成标准"]
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

  const updateSkill = (name) => {
    activeSkill = name;
    const skill = skills[name];
    document.getElementById("skill-code").textContent = skill.code;
    document.getElementById("skill-title").textContent = skill.title;
    document.getElementById("skill-description").textContent = skill.description;
    document.getElementById("skill-guide").innerHTML = skill.guide.map(item => `<li>${item}</li>`).join("");
    request.placeholder = skill.placeholder;
    submit.textContent = skill.action;
    nav.querySelectorAll("button").forEach(button => button.classList.toggle("active", button.dataset.skill === name));
    structuredMatch.hidden = name !== "career_match";
    if (name === "career_match" && !jobsLoaded) loadWorkspaceJobs();
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
        : "当前筛选条件下没有近期已核验岗位，可调整范围或使用常规方向分析。";
      jobsLoaded = true;
    } catch (error) {
      jobStatus.textContent = error.message || "岗位列表暂时不可用";
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
  jobQuery.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadWorkspaceJobs();
    }
  });
  jobSelect.addEventListener("change", loadRequirements);
  document.getElementById("job-age").addEventListener("change", () => {
    jobsLoaded = false;
    if (activeSkill === "career_match") loadWorkspaceJobs();
  });

  nav.addEventListener("click", event => {
    const button = event.target.closest("button[data-skill]");
    if (button) updateSkill(button.dataset.skill);
  });

  request.addEventListener("input", () => {
    document.getElementById("request-count").textContent = request.value.length;
    if (request.value.trim()) updateFlow(2);
  });

  document.getElementById("confirm-input").addEventListener("change", event => {
    updateFlow(event.target.checked ? 3 : 2);
  });

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    fileText = "";
    clearFile.hidden = true;
    fileStatus.classList.remove("error");
    if (!file) return;
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
      updateFlow(2);
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
  });

  submit.addEventListener("click", async () => {
    submitStatus.classList.remove("error");
    if (!request.value.trim() && !fileText.trim() && !evidenceDetail.value.trim()) {
      submitStatus.textContent = "请填写问题或上传材料。";
      submitStatus.classList.add("error");
      return;
    }
    if (!document.getElementById("confirm-input").checked) {
      submitStatus.textContent = "请先确认本次输入材料。";
      submitStatus.classList.add("error");
      return;
    }
    const skill = skills[activeSkill];
    const job = activeSkill === "career_match" ? selectedJob() : null;
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
        submitStatus.textContent = "请至少保留一项需要核对的岗位要求。";
        submitStatus.classList.add("error");
        return;
      }
      if (!evidence.length) {
        submitStatus.textContent = "逐项匹配需要填写已确认经历或上传材料。";
        submitStatus.classList.add("error");
        return;
      }
      if (evidence.length > 20 || evidence.reduce((total, item) => total + item.length, 0) > 20000) {
        submitStatus.textContent = "本次经历材料超过 20 项或 20000 字符，请缩短后重试。";
        submitStatus.classList.add("error");
        return;
      }
      const missingTerms = requirementIds.filter(item => !requirementTerms[item].length);
      if (missingTerms.length) {
        submitStatus.textContent = "请为选中的岗位要求填写 JD 原文中的核对关键词。";
        submitStatus.classList.add("error");
        return;
      }
      submit.disabled = true;
      submitStatus.textContent = "正在逐项核对…";
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
        emptyOutput.hidden = true;
        result.hidden = false;
        renderStructuredResult(payload, skill);
        submitStatus.textContent = "逐项匹配完成";
        updateFlow(4);
        document.getElementById("output-card").scrollIntoView({behavior: "smooth", block: "start"});
      } catch (error) {
        submitStatus.textContent = error.message || "服务暂时不可用";
        submitStatus.classList.add("error");
      } finally {
        submit.disabled = false;
      }
      return;
    }
    const material = fileText.trim() ? `\n\n用户上传材料：\n${fileText.trim()}` : "";
    const message = `[${skill.title}]\n${request.value.trim() || skill.placeholder}${material}`;
    if (message.length > 20000) {
      submitStatus.textContent = "输入总长度超过 20000 字符，请缩短问题或材料。";
      submitStatus.classList.add("error");
      return;
    }
    submit.disabled = true;
    submitStatus.textContent = "正在分析…";
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
      emptyOutput.hidden = true;
      result.hidden = false;
      result.textContent = payload.response;
      const meta = document.createElement("div");
      meta.className = "result-meta";
      meta.textContent = `处理板块：${skill.title} · 请求编号：${payload.request_id}`;
      result.appendChild(meta);
      submitStatus.textContent = "分析完成";
      updateFlow(4);
      document.getElementById("output-card").scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) {
      submitStatus.textContent = error.message || "服务暂时不可用";
      submitStatus.classList.add("error");
    } finally {
      submit.disabled = false;
    }
  });
})();
