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
  let activeSkill = "career_profile";
  let fileText = "";
  let conversationId = null;
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
    updateFlow(1);
  };

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
    if (!request.value.trim() && !fileText.trim()) {
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
      const payload = await response.json();
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
