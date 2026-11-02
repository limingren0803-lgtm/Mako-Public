(() => {
  const skills = {
    career_profile: {
      code: "CAREER PROFILE", title: "背景诊断", action: "开始背景诊断",
      description: "整理教育、项目、实习和技能信息，识别已经有证据支持的优势与仍需补充的部分。",
      requestLabel: "你希望重点了解哪部分求职背景",
      placeholder: "例如：请分析我的背景更适合哪些数据分析方向，并指出目前证据不足的部分。",
      inputHint: "建议说明学历、专业、毕业时间、目标地区，以及希望重点判断的方向。",
      uploadDescription: "可上传简历文件或经历清单；提交后将作为本次背景分析输入",
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
      uploadDescription: "可上传简历文件或经历说明；也可以在下方选择系统职位或提供 JD",
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
      placeholder: "上传简历文件，并说明目标岗位和希望调整的部分；也可以直接粘贴简历内容。",
      inputHint: "建议说明目标岗位、希望保留的内容，以及不能改变的事实边界。",
      uploadDescription: "上传 PDF、DOCX、TXT 或 Markdown 简历；也可选择材料库中已保存的简历",
      prepare: ["当前简历文件或已保存简历", "目标岗位或 JD", "可以确认的数据、职责和成果"],
      guide: ["检查经历与目标 JD 的关联", "标出需要补证据的表达", "给出基于原事实的修改建议"],
      output: "结果优先指出事实风险和证据缺口，再给出不改变原事实的表达建议。",
      help: [
        ["简历内容较长", "优先提交与目标岗位最相关的经历，每次聚焦一到两个模块。"],
        ["没有量化数据", "不要补写数字，可以说明实际职责、过程和能够确认的结果。"],
        ["建议与事实不符", "不要采用该建议，补充真实情况后重新分析。"]
      ],
      usesJobContext: false
    },
    career_interview: {
      code: "CAREER INTERVIEW", title: "面试准备", action: "生成准备方案",
      description: "围绕目标岗位和个人真实经历生成准备重点，帮助用户形成可验证、可追问的回答。",
      requestLabel: "你正在准备什么岗位和面试阶段",
      placeholder: "例如：我要面试商业分析实习，请根据 JD 和我的经历整理重点问题。",
      inputHint: "可以说明公司、岗位、面试轮次、预计时间和最担心的问题。",
      uploadDescription: "可上传 JD、简历文件或经历清单，帮助形成针对性准备内容",
      prepare: ["公司、岗位与面试轮次", "目标 JD 和个人简历", "可以深入追问的真实案例"],
      guide: ["识别岗位重点与高概率追问", "从个人经历中选择可用案例", "指出回答中的事实边界和准备缺口"],
      output: "结果会整理准备重点、可能追问和可用案例，不会为你虚构面试经历。",
      help: [
        ["还不知道面试轮次", "先按岗位通用能力准备，确认轮次后再补充针对性内容。"],
        ["没有直接相关经历", "可以提供课程项目、社团或兼职经历，重点核对可迁移能力。"],
        ["问题范围太大", "优先选择一个岗位和一次面试阶段，完成后再扩展。"]
      ],
      usesJobContext: false
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
      usesJobContext: false
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
  const manualJd = document.getElementById("manual-jd");
  const manualJdSource = document.getElementById("manual-jd-source");
  const verifiedJobPanel = document.getElementById("verified-job-panel");
  const manualJdPanel = document.getElementById("manual-jd-panel");
  const jobOptions = document.getElementById("job-options");
  const resultState = document.getElementById("result-state");
  const resultActions = document.getElementById("result-actions");
  const resultActionStatus = document.getElementById("result-action-status");
  const completionToast = document.getElementById("analysis-complete-toast");
  let completionToastTimer = null;
  let activeSkill = "career_profile";
  let fileText = "";
  let temporaryFiles = [], missingAttachments = [];
  let preparingFiles = false;
  let materialReview = null;
  let conversationId = null;
  let retryChatRequest = null;
  let activeTask = null;
  let jobsLoaded = false;
  let loadingJobs = false;
  const jobs = new Map();
  const drafts = new Map();
  const retainedDrafts = new Map();
  const retainedFields = ["request", "manual-jd", "manual-jd-source", "evidence-detail", "job-query", "job-age", "job-mode"];
  let contextVersion = 0;
  let draftChanged = false;
  let pendingSkill = null;
  const resumeSelect = document.getElementById("analysis-resume-select");
  const resumeFileSelect = document.getElementById("analysis-resume-file");
  const resumeStatus = document.getElementById("analysis-resume-status");
  let lastDefaultResumeId = null;
  let resumeChoiceExplicit = false;
  const draftKey = () => `${activeTask?.task.task_id || "independent"}:${activeSkill}`;
  const snapshot = () => ({
    fields: [...document.querySelectorAll('.input-card input:not([type="file"]), .input-card textarea, .input-card select')]
      .filter(node => (node.id || node.name) && node.id !== "job-company-search").map(node => ({id: node.id, name: node.name, value: node.value, checked: node.checked})),
    materials: [...document.querySelectorAll('#personal-material-options input:checked')].map(node => node.value),
    nodes: ["result", "personal-result-sources", "analysis-material-usage", "requirement-list", "task-action-candidates", "job-select", "task-next-actions"].map(id => ({id, children: [...document.getElementById(id).childNodes]})),
    display: ["file-status", "clear-file", "result", "empty-output", "result-actions", "result-state", "result-action-status", "personal-result-sources", "analysis-basis-context", "view-completed-result", "task-result-tools", "task-result-status", "save-task-result", "task-action-candidates", "task-next-actions", "personal-material-picker", "personal-knowledge-hint", "job-status", "requirement-panel"].map(id => {
      const node = document.getElementById(id);
      return {id, hidden: node.hidden, className: node.className, text: node.children.length ? null : node.textContent, disabled: node.disabled};
    }),
    fileText, temporaryFiles, missingAttachments, resumeChoice: resumeSelect.value, resumeChoiceExplicit, resumeFile: resumeFileSelect.value, rawResult: result.dataset.rawText ?? null, responseComplete: result.dataset.responseComplete !== "false", conversationId, retryChatRequest, changed: draftChanged,
    flow: Number(document.querySelector(".flow [aria-current]")?.dataset.flowStep || 1),
    analysis: window.MakoTasks?.analysis(),
    jobs: [...jobs], jobsLoaded, jobOptionsOpen: jobOptions.open
  });
  const rememberDraft = () => { drafts.set(draftKey(), snapshot()); window.MakoContinuity?.schedule(); };
  const portableDrafts = () => {
    const all = new Map(drafts);
    all.set(draftKey(), snapshot());
    const portable = new Map(retainedDrafts);
    all.forEach((draft, key) => {
      const [taskId, skill] = key.split(":");
      const response = draft.analysis?.response?.trim() ? draft.analysis.response : draft.rawResult || draft.nodes.find(node => node.id === "result").children.map(node => node.textContent).join("\n");
      const fields = Object.fromEntries(draft.fields.filter(field => retainedFields.includes(field.id)).map(field => [field.id, field.value]));
      const attachments = [...(draft.temporaryFiles || []).map(item => item.file.name), ...(draft.missingAttachments || [])];
      if (!fields.request && !fields["manual-jd"] && !fields["evidence-detail"] && !draft.fileText && !response && !attachments.length) { if (!retainedDrafts.has(key)) portable.delete(key); return; }
      portable.set(key, {taskId, skill, fields, fileText: draft.fileText, response, responseComplete: draft.responseComplete, attachments,
        requestId: draft.analysis?.request_id || null,
        matchSource: draft.fields.find(field => field.name === "match-source" && field.checked)?.value || "verified",
        materialMode: draft.fields.find(field => field.name === "personal-knowledge-mode" && field.checked)?.value || "auto"});
    });
    return [...portable.values()];
  };
  const restoreRetainedDraft = () => {
    const saved = retainedDrafts.get(draftKey());
    if (!saved) return;
    resetOutput();
    document.getElementById("task-result-tools").hidden = true;
    window.MakoTasks?.restoreAnalysis(null);
    retainedFields.forEach(id => { const node = document.getElementById(id); node.value = saved.fields[id] ?? (node.tagName === "SELECT" ? node.options[0].value : ""); });
    fileText = saved.fileText;
    temporaryFiles = []; missingAttachments = saved.attachments || [];
    renderAttachments();
    fileInput.value = "";
    if (fileText) fileStatus.textContent = "已恢复附件解析文本；原文件未保留。提交前请重新核对。";
    else fileStatus.textContent = missingAttachments.length ? "草稿只保留了附件名称，请重新选择原文件。" : "本份草稿没有临时附件，可按需选择 TXT、Markdown、文本 PDF 或 DOCX。";
    document.querySelector(`input[name="match-source"][value="${saved.matchSource}"]`).checked = true;
    const mode = document.querySelector(`input[name="personal-knowledge-mode"][value="${saved.materialMode}"]`);
    if (!activeTask) { mode.checked = true; mode.dispatchEvent(new Event("change")); }
    // ponytail: independent library/job selections must be reselected after reload; rehydrate only against fresh registries if added later.
    jobSelect.value = ""; requirementList.replaceChildren(); requirementPanel.hidden = true;
    document.getElementById("job-company").value = "";
    closeSourcePicker();
    document.querySelectorAll("#personal-material-options input").forEach(node => { node.checked = false; });
    verifiedJobPanel.hidden = saved.matchSource === "manual";
    manualJdPanel.hidden = !verifiedJobPanel.hidden;
    jobOptions.open = Boolean(saved.fields["manual-jd"] || saved.fields["evidence-detail"]);
    conversationId = null; retryChatRequest = null; draftChanged = true;
    document.getElementById("request-count").textContent = request.value.length;
    document.getElementById("manual-jd-count").textContent = manualJd.value.length;
    const restoredPayload = {response: saved.response, response_complete: saved.responseComplete};
    const restoredState = window.MakoView.analysisState(restoredPayload);
    if (saved.response && restoredState !== "empty") {
      window.MakoView.renderAnalysis(result, restoredPayload, activeSkill === "career_planning");
      markResultReady(restoredState);
      const task = window.MakoTasks.current()?.task;
      if (activeTask && task?.last_analysis_request_id === saved.requestId && task.last_analysis_status === "completed") {
        window.MakoTasks.captureAnalysis({...restoredPayload, request_id: saved.requestId, task_id: task.task_id, task_revision: task.revision, task_analysis_sources: task.last_analysis_sources, action_candidates: [], action_candidates_status: "not_provided"});
        document.getElementById("task-result-status").textContent = "已恢复本机结果副本；请核对后再保存到任务。行动建议需重新分析获取。";
      } else resultActionStatus.textContent = "已恢复本机结果副本，可复制或下载；任务状态或引用可能已有变化，请重新核对。";
    }
    updateFlow(restoredState !== "empty" ? 4 : 2);
    if ((saved.response || saved.requestId) && restoredState === "empty") showEmptyAnalysis();
    document.getElementById("draft-status").textContent = "本机草稿已恢复；独立分析的材料库选择和岗位要求需重新选择。";
    retainedDrafts.delete(draftKey());
  };
  const restoreDraft = draft => {
    result.dataset.responseComplete = String(draft.responseComplete !== false);
    if (draft.rawResult !== null && draft.rawResult !== undefined) result.dataset.rawText = draft.rawResult;
    else delete result.dataset.rawText;
    draft.nodes.forEach(({id, children}) => document.getElementById(id).replaceChildren(...children));
    draft.fields.forEach(field => {
      const node = field.id ? document.getElementById(field.id) : [...document.getElementsByName(field.name)].find(node => node.value === field.value);
      if (node) { node.value = field.value; if (typeof field.checked === "boolean") node.checked = field.checked; }
    });
    closeSourcePicker();
    renderSourceDirectory();
    document.querySelectorAll('#personal-material-options input').forEach(node => { node.checked = draft.materials.includes(node.value); });
    draft.display.forEach(saved => {
      const node = document.getElementById(saved.id);
      node.hidden = saved.hidden; node.className = saved.className;
      if (saved.text !== null) node.textContent = saved.text;
      if (typeof saved.disabled === "boolean") node.disabled = saved.disabled;
    });
    fileText = draft.fileText; fileInput.value = "";
    temporaryFiles = draft.temporaryFiles || []; missingAttachments = draft.missingAttachments || [];
    renderAttachments();
    renderResumeChoice();
    if (draft.resumeFile && [...resumeFileSelect.options].some(option => option.value === draft.resumeFile)) resumeFileSelect.value = draft.resumeFile;
    renderResumeChoice();
    if (draft.resumeChoice && [...resumeSelect.options].some(option => option.value === draft.resumeChoice)) resumeSelect.value = draft.resumeChoice;
    resumeChoiceExplicit = Boolean(draft.resumeChoiceExplicit);
    updateResumeStatus();
    conversationId = draft.conversationId; retryChatRequest = draft.retryChatRequest; draftChanged = draft.changed;
    jobs.clear(); draft.jobs.forEach(([key, value]) => jobs.set(key, value)); jobsLoaded = draft.jobsLoaded;
    jobOptions.open = draft.jobOptionsOpen;
    window.MakoTasks?.restoreAnalysis(draft.analysis);
    window.MakoMaterials?.updateSummary();
    document.getElementById("request-count").textContent = request.value.length;
    document.getElementById("manual-jd-count").textContent = manualJd.value.length;
    verifiedJobPanel.hidden = matchSource() === "manual"; manualJdPanel.hidden = !verifiedJobPanel.hidden;
    updateFlow(draft.flow === 3 ? 2 : draft.flow);
    if ((draft.analysis && window.MakoView.analysisState(draft.analysis) === "empty") || (typeof draft.rawResult === "string" && !draft.rawResult.trim() && !result.hidden)) showEmptyAnalysis();
  };
  const canSwitch = () => {
    if (!preparingFiles && !submit.disabled && !window.MakoTasks?.busy()) return true;
    document.getElementById("draft-status").textContent = "当前操作正在进行，完成后即可切换。";
    return false;
  };
  let analysisControls = [];
  const setAnalyzing = busy => {
    updateFlow(busy ? 3 : !result.hidden ? 4 : 2);
    if (busy) {
      analysisControls = [...document.querySelectorAll('.input-card input, .input-card textarea, .input-card select, .input-card button')].map(node => [node, node.disabled]);
      analysisControls.forEach(([node]) => { node.disabled = true; });
    } else {
      analysisControls.forEach(([node, disabled]) => { node.disabled = disabled; });
      analysisControls = [];
      loadJobsButton.disabled = loadingJobs;
    }
  };
  const userId = `ui_${crypto.randomUUID().replaceAll("-", "")}`;

  const updateFlow = (step) => {
    document.querySelectorAll("[data-flow-step]").forEach(item => {
      item.classList.toggle("current", Number(item.dataset.flowStep) === step);
      item.classList.toggle("complete", Number(item.dataset.flowStep) < step);
      if (Number(item.dataset.flowStep) === step) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
  };

  let stopWaiting = () => {};
  const setSubmitStatus = (message = "", state = "") => {
    stopWaiting();
    if (state === "busy") stopWaiting = window.MakoView.wait(submitStatus, message);
    else submitStatus.textContent = message;
    submitStatus.className = `status-message${state ? ` ${state}` : ""}`;
  };

  const markInputChanged = () => {
    updateFlow(2);
  };

  const updateResumeStatus = () => {
    const value = resumeSelect.value;
    if (temporaryFiles.length && !resumeFileSelect.value) resumeStatus.textContent = "请先确认这批附件里有没有简历，再选本次使用的版本。";
    else if (!value) resumeStatus.textContent = "请选定这次使用哪份简历；未选中的简历不会进入分析。";
    else if (value === "none") resumeStatus.textContent = activeTask && !activeTask.task.resume_material_id ? "此任务尚未固定简历，本次不使用库内简历。若要沿用旧版，请先在任务中明确选定。" : "本次不使用简历；经历、项目等补充材料仍按上方设置处理。";
    else if (value.startsWith("temporary:")) resumeStatus.textContent = "这份附件仅用于本次分析，不会替换材料库中的当前简历。";
    else resumeStatus.textContent = activeTask ? "沿用当前任务选定的简历；若要更换库内版本，请先调整任务上下文。" : "本次使用所选库内简历，不会改变材料库中的当前简历。";
  };

  const renderResumeChoice = ({reset = false, resetFile = false} = {}) => {
    if (reset) resumeChoiceExplicit = false;
    const old = resumeSelect.value;
    const oldFile = resetFile ? "" : resumeFileSelect.value;
    const resumes = window.MakoMaterials?.availableResumes() || [];
    const mode = activeTask?.task.personal_knowledge_mode || document.querySelector('input[name="personal-knowledge-mode"]:checked')?.value || "auto";
    const pinned = activeTask?.task.resume_material_id || null;
    const current = activeTask ? resumes.find(item => item.material_id === pinned) : window.MakoMaterials?.currentResume();
    resumeSelect.replaceChildren();
    const attachments = temporaryFiles.map(item => item.file.name);
    resumeFileSelect.replaceChildren(new Option("请确认这些附件中有没有简历", ""), new Option("没有简历，都是 JD 或其他材料", "none"));
    attachments.forEach(name => resumeFileSelect.appendChild(new Option(name, name)));
    resumeFileSelect.value = [...resumeFileSelect.options].some(option => option.value === oldFile) ? oldFile : "";
    document.getElementById("analysis-resume-file-label").hidden = !attachments.length;
    resumeFileSelect.hidden = !attachments.length;
    if (attachments.length) resumeSelect.appendChild(new Option("请选择本次使用的简历", ""));
    if (mode !== "off") {
      const choices = activeTask ? resumes.filter(item => item.material_id === pinned) : resumes;
      choices.forEach(item => resumeSelect.appendChild(new Option(`${item.title}${item.material_id === current?.material_id ? " · 当前选用" : ""}（材料库）`, `library:${item.material_id}`)));
    }
    if (attachments.includes(resumeFileSelect.value)) resumeSelect.appendChild(new Option(`${resumeFileSelect.value}（仅本次附件）`, `temporary:${resumeFileSelect.value}`));
    resumeSelect.appendChild(new Option("本次不使用简历", "none"));
    const preferred = mode !== "off" && current ? `library:${current.material_id}` : "none";
    resumeSelect.value = !reset && [...resumeSelect.options].some(option => option.value === old) ? old : attachments.length ? "" : preferred;
    const structuredMatch = activeSkill === "career_match" && !activeTask && matchSource() === "verified" && Boolean(selectedJob());
    document.getElementById("analysis-resume-choice").hidden = structuredMatch;
    document.getElementById("verified-resume-boundary").hidden = !structuredMatch;
    updateResumeStatus();
    window.MakoToolPage?.summarize();
  };

  const chosenResume = () => {
    const value = resumeSelect.value;
    if (temporaryFiles.length && !resumeFileSelect.value) throw new Error("请先确认本次附件中哪份是简历；没有简历也可以明确选择“没有简历”。");
    const markedFile = resumeFileSelect.value !== "none" ? resumeFileSelect.value : null;
    if (markedFile && temporaryFiles.filter(item => item.file.name === markedFile && item.preview).length !== 1) throw new Error("本次简历附件不可用，或存在同名附件。请核对后重新选择。");
    if (!value) throw new Error("请先选择本次使用哪份简历，或明确选择不使用简历。");
    if (activeTask && !activeTask.task.resume_material_id && value === "none" && activeTask.references.personal_materials?.some(reference => activeTask.task.personal_material_ids.includes(reference.material_id) && reference.material?.category === "resume")) throw new Error("这项旧任务曾把简历放在补充材料中。请先编辑任务，明确选定简历后再分析，避免无提示地遗漏原版本。");
    if (value === "none") return {resume_source: "none", ...(markedFile ? {temporary_resume_filename: markedFile} : {})};
    if (value.startsWith("library:")) {
      const materialId = value.slice(8);
      if (!window.MakoMaterials.availableResumes().some(item => item.material_id === materialId)) throw new Error("所选简历当前不可用，请重新选择。");
      if (activeTask && activeTask.task.resume_material_id !== materialId) throw new Error("当前任务的简历已变化，请返回任务调整后重试。");
      return {resume_source: "library", resume_material_id: materialId, ...(markedFile ? {temporary_resume_filename: markedFile} : {})};
    }
    const filename = value.slice(10);
    if (filename !== markedFile) throw new Error("本次附件简历选择已变化，请重新核对。");
    return {resume_source: "temporary", temporary_resume_filename: filename};
  };

  const resetOutput = (message = "开始分析后，结果会显示在这里。") => {
    hideCompletionToast();
    delete result.dataset.rawText;
    delete result.dataset.responseComplete;
    selectResultTab("conclusions");
    document.getElementById("view-completed-result").hidden = true;
    result.replaceChildren();
    result.hidden = true;
    emptyOutput.hidden = false;
    emptyOutput.textContent = message;
    resultActions.hidden = true;
    resultActionStatus.textContent = "";
    resultState.textContent = "等待材料";
    window.MakoMaterials?.clearSources();
    document.getElementById("analysis-material-usage").replaceChildren();
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
    if (activeSkill === "career_match") markInputChanged();
    renderResumeChoice();
    setSubmitStatus();
  };

  const updateSkill = (name) => {
    activeSkill = name;
    const skill = skills[name];
    document.getElementById("skill-code").textContent = "当前分析";
    document.getElementById("skill-title").textContent = skill.title;
    document.getElementById("skill-description").textContent = skill.description;
    document.getElementById("request-label").textContent = skill.requestLabel;
    document.getElementById("request-hint").textContent = skill.inputHint;
    document.getElementById("upload-description").textContent = skill.uploadDescription;
    renderHelp(skill);
    request.placeholder = skill.placeholder;
    submit.textContent = skill.action;
    nav.querySelectorAll("button").forEach(button => {
      button.classList.toggle("active", button.dataset.skill === name);
      if (button.dataset.skill === name) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    structuredMatch.hidden = name !== "career_match";
    jobOptions.hidden = !skill.usesJobContext;
    jobOptions.open = false;
    setSubmitStatus();
    resetOutput();
    updateFlow(1);
    if (activeTask) jobOptions.hidden = true;
    renderResumeChoice();
  };

  const openTask = item => {
    rememberDraft();
    contextVersion++;
    activeTask = item;
    updateSkill(item.task.career_intent);
    document.getElementById("task-context-rail").hidden = false;
    document.getElementById("task-context-goal").textContent = item.task.goal;
    const track = item.references.track?.track;
    document.getElementById("task-context-job").textContent = track ? `${track.company_name} · ${track.title}` : item.references.reviewed_job ? "系统已核验职位" : "未绑定";
    document.getElementById("task-context-job-scope").textContent = track?.source_kind === "manual_jd" ? "使用用户提供 JD" : `近 ${item.task.job_max_age_days || 30} 天 · ${item.task.job_data_mode === "official_links_if_missing" ? "不足时提供官网入口" : "仅已核验"}`;
    document.getElementById("task-context-materials").textContent = item.task.personal_knowledge_mode === "off" ? "本任务不使用" : item.task.personal_knowledge_mode === "selected" ? `指定 ${item.task.personal_material_ids.length} 份` : "自动查找相关内容";
    document.getElementById("task-context-resume").textContent = item.references.resume?.material?.title || (item.task.resume_material_id ? "所选简历当前不可用" : "未指定");
    document.getElementById("task-context-stage").textContent = skills[item.task.career_intent].title;
    window.MakoView.route(document.getElementById("analysis-task-route"), item.task);
    const draft = drafts.get(draftKey());
    restoreDraft(draft || emptyDraft);
    renderResumeChoice({reset: !draft || !draft.resumeChoiceExplicit});
    renderTaskConsent(item);
    document.getElementById("personal-knowledge-choice").hidden = true;
    document.getElementById("personal-material-picker").hidden = true;
    document.getElementById("personal-knowledge-hint").hidden = true;
    jobOptions.hidden = true;
    document.getElementById("draft-status").textContent = "当前任务的输入与结果按阶段分别保留；本机续接状态见下方，正式结果请保存到任务。";
    document.getElementById("request").focus();
    window.MakoContinuity?.navigate();
  };

  const openIndependent = name => {
    rememberDraft(); contextVersion++;
    activeTask = null;
    updateSkill(name);
    const draft = drafts.get(draftKey());
    restoreDraft(draft || emptyDraft);
    renderResumeChoice({reset: !draft || !draft.resumeChoiceExplicit});
    document.getElementById("task-context-rail").hidden = true;
    renderTaskConsent(null);
    window.MakoMaterials?.updateSummary();
    document.getElementById("task-result-tools").hidden = true;
    document.getElementById("personal-knowledge-choice").hidden = false;
    document.getElementById("draft-status").textContent = "独立分析 · 各工具的草稿分别保留；需要刷新后续接时，可在下方开启本机保留。";
    if (name === "career_match" && !jobsLoaded && matchSource() === "verified") loadWorkspaceJobs();
    if (!drafts.has(draftKey())) jobOptions.open = false;
    restoreRetainedDraft();
    window.MakoContinuity?.navigate();
  };

  window.MakoApp = Object.freeze({openTask, canSwitch, portableDrafts, restoreRetained: restoreRetainedDraft,
    position: () => ({skill: activeSkill, taskId: activeTask?.task.task_id || null}),
    resumeIndependent: skill => { openIndependent(skill); window.MakoWorkspace.showSkill(); },
    retain: items => items.forEach(item => retainedDrafts.set(`${item.taskId}:${item.skill}`, item)),
    forgetRetained: () => retainedDrafts.clear()
  });

  const responseMessage = payload => payload?.error?.message || payload?.detail || "请求未完成";

  const readResponse = async response => {
    if (response.status === 429) {
      throw new Error("当前请求较多，请稍等片刻后重试。你的输入内容已保留。");
    }
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error("服务返回了无法识别的响应，请稍后重试。");
    }
    return response.json();
  };

  const selectedJob = () => jobs.get(jobSelect.value);

  const loadWorkspaceJobs = async () => {
    const version = contextVersion;
    loadingJobs = true;
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
      if (document.getElementById("job-company").value) params.set("source_id", document.getElementById("job-company").value);
      const response = await fetch(`/v2/workspace/jobs?${params}`);
      const payload = await readResponse(response);
      if (!response.ok) throw new Error(responseMessage(payload));
      if (version !== contextVersion) return;
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
      if (version !== contextVersion) return;
      jobStatus.textContent = `${error.message || "岗位列表暂时不可用"} 可以切换到自行提供 JD，当前输入不会丢失。`;
      jobStatus.classList.add("error");
    } finally {
      loadingJobs = false;
      loadJobsButton.disabled = submit.disabled;
    }
  };

  const loadRequirements = async () => {
    const version = contextVersion;
    const selectedKey = jobSelect.value;
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
      if (version !== contextVersion || selectedKey !== jobSelect.value) return;
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
      if (version !== contextVersion || selectedKey !== jobSelect.value) return;
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

  const showEmptyAnalysis = () => {
    const message = "本次未返回可用的分析正文，请重试。输入与材料选择已保留。";
    resetOutput(message);
    window.MakoTasks?.restoreAnalysis(null);
    setSubmitStatus(message, "error");
    resultState.textContent = "需要重试";
    updateFlow(2);
  };
  function hideCompletionToast() {
    clearTimeout(completionToastTimer);
    completionToast.classList.remove("is-visible");
    completionToastTimer = setTimeout(() => { completionToast.hidden = true; }, 200);
  }
  const showCompletionToast = state => {
    clearTimeout(completionToastTimer);
    document.getElementById("analysis-complete-title").textContent = state === "partial" ? "回答未完成" : "分析完成";
    document.getElementById("analysis-complete-message").textContent = state === "partial" ? "已返回的部分可查看，输入仍保留，可核对后重试。" : "结果与下一步已经准备好。";
    completionToast.hidden = false;
    const mark = completionToast.querySelector(".analysis-complete-mark");
    mark.getAnimations().forEach(animation => animation.cancel());
    mark.textContent = state === "partial" ? "!" : "✓";
    if (state !== "partial") window.MakoView.feedback(mark);
    requestAnimationFrame(() => completionToast.classList.add("is-visible"));
  };
  const markResultReady = (state = "complete", notify = false) => {
    selectResultTab("conclusions");
    document.getElementById("view-completed-result").hidden = false;
    emptyOutput.hidden = true;
    result.hidden = false;
    resultActions.hidden = false;
    result.dataset.responseComplete = String(state !== "partial");
    resultState.textContent = state === "partial" ? "回答未完成" : "分析完成";
    document.getElementById("view-completed-result").textContent = state === "partial" ? "回答未完成 · 查看已返回内容" : "分析已完成 · 查看结果与下一步";
    resultActionStatus.textContent = "";
    if (notify) showCompletionToast(state);
    window.MakoContinuity?.schedule();
  };

  const clearCurrentInput = () => {
    if (!canSwitch()) return;
    if ((draftChanged || !result.hidden) && !window.confirm("清空当前工具的输入和页面结果？已经保存到任务的内容不受影响。")) return;
    draftChanged = false;
    drafts.delete(draftKey());
    retainedDrafts.delete(draftKey());
    conversationId = null; retryChatRequest = null;
    document.getElementById("task-result-tools").hidden = true;
    window.MakoTasks?.restoreAnalysis(null);
    request.value = "";
    document.getElementById("request-count").textContent = "0";
    fileInput.value = "";
    fileText = "";
    temporaryFiles = []; missingAttachments = []; renderAttachments();
    renderResumeChoice({reset: true, resetFile: true});
    clearFile.hidden = true;
    fileStatus.textContent = "支持 TXT、Markdown、文本 PDF、DOCX，每份最多 10 MB；可查看解析预览，不自动保存。";
    fileStatus.classList.remove("error");
    evidenceDetail.value = "";
    manualJd.value = "";
    manualJdSource.value = "";
    document.getElementById("manual-jd-count").textContent = "0";
    jobQuery.value = "";
    jobSelect.value = "";
    requirementPanel.hidden = true;
    requirementList.replaceChildren();
    const verifiedSource = document.querySelector('input[name="match-source"][value="verified"]');
    if (verifiedSource) verifiedSource.checked = true;
    const automaticKnowledge = document.querySelector('input[name="personal-knowledge-mode"][value="auto"]');
    if (automaticKnowledge) automaticKnowledge.checked = true;
    document.getElementById("personal-material-picker").hidden = true;
    document.getElementById("personal-knowledge-hint").textContent = "Mako 会自动查找相关内容；如果没有达到相关性要求，本次分析不会引用个人材料。";
    if (activeSkill === "career_match") updateMatchSource();
    setSubmitStatus();
    resetOutput();
    updateFlow(1);
    request.focus();
    window.MakoContinuity?.schedule();
  };

  const renderStructuredResult = (payload, skill) => {
    delete result.dataset.rawText;
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
    markInputChanged();
    renderResumeChoice();
    loadRequirements();
  });
  requirementList.addEventListener("input", markInputChanged);
  document.getElementById("job-age").addEventListener("change", () => {
    markInputChanged();
    jobsLoaded = false;
    if (activeSkill === "career_match") loadWorkspaceJobs();
  });
  document.getElementById("job-mode").addEventListener("change", markInputChanged);

  manualJd.addEventListener("input", () => {
    document.getElementById("manual-jd-count").textContent = manualJd.value.length;
    markInputChanged();
  });
  manualJdSource.addEventListener("input", markInputChanged);

  nav.addEventListener("click", event => {
    const button = event.target.closest("button[data-skill]");
    if (!button) return;
    if (!canSwitch()) { event.stopImmediatePropagation(); return; }
    if (button.dataset.skill === activeSkill) {
      nav.querySelectorAll("button").forEach(item => item.classList.toggle("active", item === button));
      return;
    }
    if (activeTask) {
      pendingSkill = button.dataset.skill;
      document.getElementById("skill-context-description").textContent = `进入${skills[pendingSkill].title}，是否继续为“${activeTask.task.goal}”准备？沿用会更新当前任务阶段。`;
      document.getElementById("skill-context-status").textContent = "";
      document.getElementById("skill-context-dialog").showModal();
      return;
    }
    if (button.dataset.skill !== activeSkill) openIndependent(button.dataset.skill);
  });
  document.getElementById("skill-context-independent").addEventListener("click", () => {
    openIndependent(pendingSkill);
    document.getElementById("skill-context-dialog").close();
  });
  document.getElementById("skill-context-continue").addEventListener("click", async event => {
    event.target.disabled = true;
    document.getElementById("skill-context-independent").disabled = true;
    try {
      await window.MakoTasks.continueWith(pendingSkill);
      document.getElementById("skill-context-dialog").close();
    } catch (error) { document.getElementById("skill-context-status").textContent = error.message || "阶段切换失败，当前输入仍保留。"; }
    finally { event.target.disabled = false; document.getElementById("skill-context-independent").disabled = false; }
  });
  document.querySelector('.input-card').addEventListener("input", () => { draftChanged = true; });
  window.addEventListener("beforeunload", event => {
    const retained = window.MakoContinuity?.flush();
    if (!retained && (draftChanged || [...drafts.values()].some(draft => draft.changed))) { event.preventDefault(); event.returnValue = ""; }
  });

  request.addEventListener("input", () => {
    document.getElementById("request-count").textContent = request.value.length;
    markInputChanged();
  });

  evidenceDetail.addEventListener("input", markInputChanged);


  document.getElementById("clear-input").addEventListener("click", clearCurrentInput);
  document.getElementById("restart-flow").addEventListener("click", clearCurrentInput);

  document.getElementById("copy-result").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(result.dataset.rawText ?? result.innerText.trim());
      resultActionStatus.textContent = "结果已复制。";
    } catch (_) {
      resultActionStatus.textContent = "浏览器未允许复制，请手动选择结果文本。";
    }
  });

  document.getElementById("download-result").addEventListener("click", () => {
    const blob = new Blob([result.dataset.rawText ?? result.innerText.trim()], {type: "text/plain;charset=utf-8"});
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

  const renderAttachments = () => {
    const target = document.getElementById("attachment-previews"); target.replaceChildren();
    if (fileText) { const details = window.MakoView.node("details"); details.append(window.MakoView.node("summary", "核对已恢复的附件文本"), window.MakoView.node("p", fileText)); target.append(details); }
    if (missingAttachments.length) target.append(window.MakoView.node("p", `原文件未保留，请重新选择：${missingAttachments.join("、")}。也可移除附件后继续。`, "task-reference-warning"));
    temporaryFiles.forEach((item, index) => {
      const section = window.MakoView.node("section", "", "attachment-preview");
      section.append(window.MakoView.node("h3", item.file.name), window.MakoView.node("p", `${item.file.name.split(".").pop().toUpperCase()} · ${(item.file.size / 1024).toFixed(1)} KB · ${item.preview ? "预览就绪" : preparingFiles ? "正在准备预览" : "预览失败，需要重试或移除"}`, "hint"));
      if (item.preview) {
        const details = window.MakoView.node("details"); details.append(window.MakoView.node("summary", `查看解析节选 · 共 ${item.preview.character_count} 字 / ${item.preview.section_count} 处`));
        details.append(window.MakoView.node("p", "仅展示前 5 处的部分文本，不是完整附件。请结合原文件核对。", "hint"));
        item.preview.excerpts.forEach(excerpt => { details.append(window.MakoView.node("b", excerpt.locator_label), window.MakoView.node("p", excerpt.text)); });
        item.preview.warnings.forEach(value => details.append(window.MakoView.node("p", value, "task-reference-warning")));
        section.append(details);
      } else section.append(window.MakoView.node("p", item.error || "尚未完成预览", "task-reference-warning"));
      const remove = window.MakoView.node("button", "移除此附件", "text-button"); remove.type = "button"; remove.disabled = preparingFiles;
      remove.addEventListener("click", () => { if (!canSwitch()) return; temporaryFiles = temporaryFiles.filter((_, offset) => offset !== index); retryChatRequest = null; renderAttachments(); renderResumeChoice({resetFile: true}); markInputChanged(); window.MakoContinuity?.schedule(); });
      section.append(remove);
      const save = window.MakoView.node("button", item.preview ? "另存到个人材料库（可选）" : "重新预览", "text-button"); save.type = "button"; save.disabled = preparingFiles;
      save.addEventListener("click", () => {
        if (!canSwitch()) return;
        if (!item.preview) return readFile(temporaryFiles.map(value => value.file));
        rememberDraft(); window.MakoWorkspace.showPage("materials"); document.getElementById("return-to-analysis").hidden = false;
        window.MakoMaterials.preview(item.file);
      });
      section.append(save); target.append(section);
    });
    clearFile.hidden = !temporaryFiles.length && !missingAttachments.length && !fileText;
  };
  const readFile = async selected => {
    const files = Array.from(selected || []);
    if (!files.length || fileInput.disabled || !canSwitch()) return;
    const version = ++contextVersion;
    fileStatus.classList.remove("error");
    if (files.length > 5 || files.some(file => !["txt", "md", "pdf", "docx"].includes(file.name.split(".").pop().toLowerCase()) || file.size > 10 * 1024 * 1024)) {
      fileInput.value = "";
      fileStatus.textContent = "请选择 1–5 份 TXT、Markdown、文本 PDF 或 DOCX，每份不超过 10 MB。不支持扫描件或 OCR。";
      fileStatus.classList.add("error");
      return;
    }
    fileText = ""; missingAttachments = []; retryChatRequest = null;
    temporaryFiles = files.map(file => ({file, preview: null, fingerprint: null}));
    renderResumeChoice({resetFile: true});
    markInputChanged(); preparingFiles = true; setAnalyzing(true); renderAttachments();
    const stop = window.MakoView.wait(fileStatus, "正在发送附件并等待解析预览…");
    try {
      for (const item of temporaryFiles) {
        try {
          const bytes = await item.file.arrayBuffer();
          item.fingerprint = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(value => value.toString(16).padStart(2, "0")).join("");
          const body = new FormData(); body.append("file", item.file);
          item.preview = await window.MakoWorkspace.fetch("/materials/preview", {method: "POST", body});
        } catch (error) { item.error = window.MakoMaterials.friendlyError(error); }
      }
      if (version !== contextVersion) return;
      const ready = temporaryFiles.filter(item => item.preview).length;
      fileStatus.textContent = `已读取 ${ready} / ${files.length} 份附件的解析预览。${ready === files.length ? "请核对原文件与节选，再确认本次分析。" : "未通过的附件需重试或移除后才能分析。"}`;
      fileStatus.classList.toggle("error", ready !== files.length);
      if (ready === files.length) window.MakoView.feedback(fileStatus);
      window.MakoContinuity?.schedule();
    } finally { stop(); preparingFiles = false; setAnalyzing(false); renderAttachments(); if (temporaryFiles.length) document.getElementById("reference-options").open = true; }
  };
  fileInput.addEventListener("change", () => readFile(fileInput.files));
  window.MakoView.upload(fileInput, readFile, message => { fileStatus.textContent = message; fileStatus.classList.add("error"); });

  clearFile.addEventListener("click", () => {
    contextVersion++;
    fileInput.value = "";
    fileText = "";
    temporaryFiles = []; missingAttachments = []; retryChatRequest = null; renderAttachments();
    renderResumeChoice({resetFile: true});
    clearFile.hidden = true;
    fileStatus.textContent = "本次附件已移除，可重新选择 TXT、Markdown、文本 PDF 或 DOCX。";
    fileStatus.classList.remove("error");
    markInputChanged();
  });

  resumeSelect.addEventListener("change", () => { resumeChoiceExplicit = true; updateResumeStatus(); window.MakoToolPage?.summarize(); markInputChanged(); });
  resumeFileSelect.addEventListener("change", () => { renderResumeChoice({reset: resumeFileSelect.value !== "none"}); markInputChanged(); });
  document.querySelectorAll('input[name="personal-knowledge-mode"]').forEach(input => input.addEventListener("change", () => renderResumeChoice({reset: true})));
  document.addEventListener("mako:materials-updated", () => {
    const currentId = window.MakoMaterials?.currentResume()?.material_id || null;
    const changed = currentId !== lastDefaultResumeId;
    lastDefaultResumeId = currentId;
    renderResumeChoice({reset: changed && !resumeChoiceExplicit});
    if (changed) markInputChanged();
  });
  document.addEventListener("DOMContentLoaded", async () => { await window.MakoMaterials.load({quiet: true}); renderResumeChoice(); });

  submit.addEventListener("click", async () => {
    if (submit.disabled || preparingFiles || window.MakoTasks?.busy()) return;
    setSubmitStatus();
    const currentTask = activeTask ? window.MakoTasks.current() || activeTask : null;
    let personalSelection;
    if (currentTask) {
      personalSelection = {mode: currentTask.task.personal_knowledge_mode, ids: currentTask.task.personal_material_ids};
    } else {
      try {
        personalSelection = window.MakoMaterials.selection();
      } catch (error) {
        setSubmitStatus(error.message, "error");
        return;
      }
    }
    const manualMatch = !activeTask && activeSkill === "career_match" && matchSource() === "manual";
    if (missingAttachments.length || temporaryFiles.some(item => !item.preview)) {
      setSubmitStatus("请先重新选择、完成预览或移除未就绪的附件。", "error"); return;
    }
    if (!request.value.trim() && !fileText.trim() && !temporaryFiles.length && !evidenceDetail.value.trim() && !manualJd.value.trim() && !(personalSelection.mode === "selected" && personalSelection.ids.length) && !resumeSelect.value.startsWith("library:")) {
      setSubmitStatus("请填写问题、经历材料或目标 JD。", "error");
      return;
    }
    if (manualMatch && !manualJd.value.trim()) {
      setSubmitStatus("已选择自行提供 JD，请粘贴完整职位描述。", "error");
      return;
    }
    const skill = skills[activeSkill];
    const job = !activeTask && activeSkill === "career_match" && !manualMatch ? selectedJob() : null;
    if (job && temporaryFiles.length) { setSubmitStatus("逐项岗位匹配暂不接收临时附件。请取消目标岗位选择，使用常规方向分析；或使用已保存的个人材料。", "error"); return; }
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
      if (evidence.length > 20 || evidence.reduce((total, item) => total + item.length, 0) > 20000) {
        setSubmitStatus("本次经历材料超过 20 项或 20000 字符，请缩短后重试。", "error");
        return;
      }
      const missingTerms = requirementIds.filter(item => !requirementTerms[item].length);
      if (missingTerms.length) {
        setSubmitStatus("请为选中的岗位要求填写 JD 原文中的核对关键词。", "error");
        return;
      }
      setAnalyzing(true);
      setSubmitStatus("正在逐项核对，请不要重复提交。", "busy");
      try {
        const selectedRequirements = [...requirementList.querySelectorAll("input:checked")]
          .map(input => input.closest(".requirement-option")?.querySelector("label span")?.textContent || "")
          .filter(Boolean);
        const personalHits = (await window.MakoMaterials.search([request.value.trim(), ...selectedRequirements].filter(Boolean).join("\n"))).filter(hit => hit.category !== "resume");
        const usedHits = [];
        let evidenceCharacters = evidence.reduce((total, item) => total + item.length, 0);
        personalHits.forEach(hit => {
          const value = `个人材料 ${hit.title}（${hit.locator_label}）：${hit.excerpt}`;
          if (evidence.length < 20 && evidenceCharacters + value.length <= 20000) {
            evidence.push(value);
            evidenceCharacters += value.length;
            usedHits.push(hit);
          }
        });
        if (!evidence.length) throw new Error("逐项匹配需要填写已确认经历，或选择一份相关的非简历补充材料。整份简历可在常规方向分析中使用。");
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
        window.MakoMaterials.renderSources(usedHits, usedHits.length > 0, personalSelection.mode);
        markResultReady("complete", true);
        setSubmitStatus("逐项匹配完成。", "success");
        updateFlow(4);
      } catch (error) {
        setSubmitStatus(`${error.message || "服务暂时不可用"} 输入内容已保留，可以检查后重新提交。`, "error");
        resultState.textContent = "需要处理";
      } finally {
        setAnalyzing(false);
      }
      return;
    }
    let resumeChoice;
    try { resumeChoice = chosenResume(); }
    catch (error) { document.getElementById("reference-options").open = true; setSubmitStatus(error.message, "error"); return; }
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
    setAnalyzing(true);
    setSubmitStatus("分析请求已发送，等待服务返回…", "busy");
    try {
      const analysisRequest = {
        message,
        ...resumeChoice,
        user_id: userId,
        conv_id: conversationId,
        career_intent: activeSkill,
        memory_mode: currentTask ? "conversation" : "none",
        ...(currentTask ? {
          task_id: currentTask.task.task_id,
          task_revision: currentTask.task.revision,
          include_action_candidates: true
        } : {
          job_max_age_days: Number(document.getElementById("job-age").value),
          job_data_mode: document.getElementById("job-mode").value,
          ...(skill.usesJobContext && document.getElementById("job-company").value ? {job_source_ids: [document.getElementById("job-company").value]} : {}),
          personal_knowledge_mode: personalSelection.mode,
          personal_material_ids: personalSelection.ids
        })
      };
      // A lost response may already have advanced the task revision. Recover that exact request instead of launching a new analysis.
      const {task_revision: taskRevision, ...sameRequest} = analysisRequest;
      const signature = JSON.stringify({request: sameRequest, taskContext: currentTask ? [currentTask.task.goal, currentTask.task.track_id, currentTask.task.job_version_id, currentTask.task.personal_knowledge_mode, currentTask.task.personal_material_ids, currentTask.task.personal_material_confirmations, currentTask.task.job_max_age_days, currentTask.task.job_data_mode] : null, files: temporaryFiles.map(item => ({name: item.file.name, sha256: item.fingerprint}))});
      const recovering = retryChatRequest?.body === signature && retryChatRequest.uncertain;
      if (recovering && Date.now() - retryChatRequest.startedAt >= 290000) throw new Error("上次请求结果未明，且已超出可复用时间。请先返回任务检查结果；需要重新分析时，可清空本页后重新准备。");
      if (currentTask && !recovering) {
        const fresh = await window.MakoTasks.refresh(currentTask.task.task_id);
        renderTaskConsent(fresh);
        if (fresh.task.revision !== taskRevision || fresh.task.career_intent !== activeSkill) throw new Error("任务已更新，请返回任务核对当前阶段与上下文后再分析。");
        if (taskConsent(fresh).supported && taskConsent(fresh).required && !taskConsent(fresh).valid) throw new Error("任务材料尚未确认或已经变化，请先核对材料列表并确认。");
      }
      const body = recovering ? retryChatRequest.payload : JSON.stringify(analysisRequest);
      const idempotencyKey = recovering
        ? retryChatRequest.key
        : `chat_${crypto.randomUUID().replaceAll("-", "")}`;
      retryChatRequest = {body: signature, payload: body, key: idempotencyKey, startedAt: recovering ? retryChatRequest.startedAt : Date.now(), uncertain: false};
      const multipart = new FormData();
      if (temporaryFiles.length) { multipart.append("payload", body); temporaryFiles.forEach(item => multipart.append("files", item.file)); }
      const payload = await window.MakoWorkspace.fetch(temporaryFiles.length ? "/analyze/files" : "/analyze", {
        method: "POST",
        headers: {...(temporaryFiles.length ? {} : {"Content-Type": "application/json"}), "Idempotency-Key": idempotencyKey},
        body: temporaryFiles.length ? multipart : body
      });
      retryChatRequest = null;
      const analysisState = window.MakoView.analysisState(payload);
      if (analysisState === "empty") {
        showEmptyAnalysis();
        if (currentTask) { const fresh = await window.MakoTasks.refresh(currentTask.task.task_id); renderTaskConsent(fresh); }
        return;
      }
      conversationId = payload.conv_id;
      result.replaceChildren();
      window.MakoView.renderAnalysis(result, payload, activeSkill === "career_planning");
      const meta = document.createElement("div");
      meta.className = "result-meta";
      meta.textContent = `处理板块：${skill.title} · 请求编号：${payload.request_id}${payload.conversation_persisted === false ? " · 临时分析，未写入对话记忆" : ""}`;
      result.appendChild(meta);
      window.MakoMaterials.renderSources(payload.personal_knowledge_sources, payload.personal_knowledge_used, personalSelection.mode);
      if (window.MakoView.renderBasis(document.getElementById("analysis-material-usage"), payload)) document.getElementById("analysis-basis-context").textContent = "以下为服务返回的材料采用账目与来源。已采用表示内容进入了本次分析上下文，请继续核对结论是否有充分依据。";
      if (activeTask) {
        currentTask.task.revision = Math.max(currentTask.task.revision, payload.task_revision);
        window.MakoTasks.captureAnalysis(payload);
      }
      markResultReady(analysisState, true);
      setSubmitStatus(analysisState === "partial" ? "回答未完成；已返回内容和当前输入仍保留，核对后可以重试。" : recovering ? "已找回上次请求的结果，请核对当前任务状态。" : "分析完成。", analysisState === "partial" ? "" : "success");
      updateFlow(4);
    } catch (error) {
      const emptyResponse = error.status === 502 && error.message === "模型未返回可用内容，请重试";
      if (emptyResponse) showEmptyAnalysis();
      if (retryChatRequest) { if (!emptyResponse && (!error.status || [502, 504].includes(error.status))) retryChatRequest.uncertain = true; else retryChatRequest = null; }
      // Failed analysis also advances the server revision; preserve the draft while refreshing it.
      if (currentTask) { const refreshed = await window.MakoTasks.refresh(currentTask.task.task_id).catch(() => null); if (refreshed) renderTaskConsent(refreshed); }
      setSubmitStatus(`${error.message || "服务暂时不可用"} 输入内容已保留，可以检查后重新提交。`, "error");
      resultState.textContent = "需要处理";
    } finally {
      setAnalyzing(false);
      if (materialReview) renderTaskConsent(materialReview);
    }
  });

  const taskConsent = item => {
    const task = item?.task;
    const selectedRequired = task?.personal_knowledge_mode === "selected" && task.personal_material_ids.length > 0;
    const resumeRequired = Boolean(task?.resume_material_id);
    const required = selectedRequired || resumeRequired;
    const supported = Array.isArray(task?.personal_material_confirmations);
    const materials = (task?.personal_material_ids || []).map(id => item.references.personal_materials?.find(ref => ref.material_id === id));
    const resume = resumeRequired ? item.references.resume : null;
    const unavailable = materials.some(ref => !ref?.material || ref.status !== "current") || (resumeRequired && (!resume?.material || resume.status !== "current"));
    const selectedValid = !selectedRequired || (supported && task.personal_material_confirmations.length === task.personal_material_ids.length && materials.every(ref => task.personal_material_confirmations.some(saved => saved.material_id === ref.material_id && saved.revision === ref.material.revision && saved.content_sha256 === ref.material.content_sha256)));
    const confirmedResume = task?.resume_material_confirmation;
    const resumeValid = !resumeRequired || Boolean(resume?.material && confirmedResume?.material_id === resume.material.material_id && confirmedResume.revision === resume.material.revision && confirmedResume.content_sha256 === resume.material.content_sha256);
    const valid = Boolean(required && supported && !unavailable && selectedValid && resumeValid);
    return {required, supported, valid, unavailable, materials, resume};
  };
  const renderTaskConsent = item => {
    materialReview = item;
    const state = taskConsent(item), section = document.getElementById("task-material-consent");
    section.hidden = !item || !state.required;
    const list = document.getElementById("task-material-consent-list"); list.replaceChildren();
    state.materials.forEach((ref, index) => list.append(window.MakoView.node("li", `${ref?.material?.title || item.task.personal_material_ids[index]} · ${!ref || ref.status !== "current" ? "当前不可用" : state.valid ? "已确认" : "请核对当前版本"}`)));
    if (state.resume) list.prepend(window.MakoView.node("li", `${state.resume.material?.title || "所选简历"} · ${state.resume.status !== "current" ? "当前不可用" : state.valid ? "已确认" : "请核对当前版本"}`));
    const count = state.materials.length + Number(Boolean(state.resume));
    document.getElementById("task-material-consent-status").textContent = state.valid ? `沿用当前任务已确认的 ${count} 份材料，无需重复确认这些版本。` : !state.supported ? "此任务尚未提供材料版本确认信息，本次仍需核对输入。" : state.unavailable ? "部分材料已停用、删除或不可检索，请返回任务调整材料选择。" : "首次使用或材料已更新，请核对列表后确认这些版本用于当前任务。";
    const button = document.getElementById("reconfirm-task-materials"); button.hidden = !state.supported || !state.required || state.valid;
    button.disabled = state.unavailable || submit.disabled;
  };
  const materialSignature = item => JSON.stringify((item?.references.personal_materials || []).filter(ref => item.task.personal_material_ids.includes(ref.material_id) || ref.material_id === item.task.resume_material_id).map(ref => [ref.material_id, ref.status, ref.material?.revision, ref.material?.content_sha256]));
  document.getElementById("reconfirm-task-materials").addEventListener("click", async () => {
    if (!materialReview || !canSwitch()) return;
    const reviewed = materialReview, signature = materialSignature(reviewed);
    setAnalyzing(true);
    try {
      const fresh = await window.MakoTasks.refresh(reviewed.task.task_id);
      renderTaskConsent(fresh);
      if (fresh.task.revision !== reviewed.task.revision || materialSignature(fresh) !== signature) { setSubmitStatus("任务或材料再次发生变化，请核对更新后的列表再确认。", "error"); return; }
      if (taskConsent(fresh).unavailable) return;
      await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(fresh.task.task_id)}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({revision: fresh.task.revision, personal_material_ids: fresh.task.personal_material_ids, resume_material_id: fresh.task.resume_material_id})});
      const updated = await window.MakoTasks.refresh(fresh.task.task_id); activeTask = updated; renderTaskConsent(updated);
      setSubmitStatus("当前材料版本已确认，可以继续分析。", "success");
    } catch (error) { setSubmitStatus(`${error.message || "材料确认未完成"}，可核对后重试。`, "error"); }
    finally { setAnalyzing(false); renderTaskConsent(materialReview); }
  });
  const selectResultTab = name => {
    document.getElementById("output-card").dataset.resultView = name;
    document.querySelectorAll("#result-tabs button").forEach(tab => {
      const selected = tab.id === `${name}-tab`;
      tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1;
    });
  };
  const resultNarrow = window.matchMedia("(max-width: 620px)");
  const syncResultPanels = () => document.querySelectorAll(".result-panel").forEach(panel => {
    if (resultNarrow.matches) { panel.setAttribute("role", "tabpanel"); panel.tabIndex = 0; }
    else { panel.removeAttribute("role"); panel.removeAttribute("tabindex"); }
  });
  resultNarrow.addEventListener("change", syncResultPanels);
  syncResultPanels();
  document.getElementById("result-tabs").addEventListener("click", event => {
    const tab = event.target.closest("[role=tab]");
    if (tab) selectResultTab(tab.id.replace("-tab", ""));
  });
  document.getElementById("result-tabs").addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const name = event.key === "Home" ? "conclusions" : event.key === "End" ? "basis" : document.getElementById("conclusions-tab").getAttribute("aria-selected") === "true" ? "basis" : "conclusions";
    selectResultTab(name); document.getElementById(`${name}-tab`).focus();
  });
  const focusResult = () => {
    hideCompletionToast();
    const output = document.getElementById("output-card"); output.tabIndex = -1; output.focus();
    output.scrollIntoView({block: "start", behavior: "instant"});
  };
  document.getElementById("view-completed-result").addEventListener("click", focusResult);
  document.getElementById("analysis-complete-view").addEventListener("click", focusResult);
  document.getElementById("analysis-complete-dismiss").addEventListener("click", hideCompletionToast);
  document.getElementById("open-material-library").addEventListener("click", () => {
    if (!canSwitch()) return;
    rememberDraft(); window.MakoWorkspace.showPage("materials");
    document.getElementById("return-to-analysis").hidden = false;
  });
  document.getElementById("return-to-analysis").addEventListener("click", () => {
    if (!canSwitch()) return;
    window.MakoWorkspace.showSkill();
    document.getElementById("personal-knowledge-hint").textContent = activeTask ? "材料已保存后，请返回任务调整绑定材料，再核对本次输入。" : "在下方选择希望参考的材料，再核对本次输入。";
    document.getElementById("return-to-analysis").hidden = true;
  });
  const sourceSelect = document.getElementById("job-company");
  const sourceSearch = document.getElementById("job-company-search");
  const sourceList = document.getElementById("job-company-options");
  const sourceStatus = document.getElementById("job-company-status");
  let sourcesLoading = false, sourcesRead = false, sourceOptions = [], sourceMatches = [], sourceActive = -1;
  const normalizeSourceTerm = value => value.normalize("NFKC").toLocaleLowerCase().replace(/[\s._-]+/g, "");
  const sourceLabel = source => source.data_status === "verified_local_data" ? `近 30 天有 ${source.verified_job_count} 个已核验岗位` : "仅提供官方招聘入口";
  const currentSourceLabel = () => sourceSelect.selectedOptions[0]?.textContent || "全部来源";
  const closeSourcePicker = () => {
    sourceList.hidden = true;
    sourceSearch.setAttribute("aria-expanded", "false");
    sourceSearch.removeAttribute("aria-activedescendant");
    sourceSearch.value = sourceSelect.value ? currentSourceLabel() : "";
    const source = sourceOptions.find(item => item.source_id === sourceSelect.value);
    sourceStatus.textContent = `当前：${currentSourceLabel()}。${source ? sourceLabel(source) : "输入关键词后从列表选择。"}`;
  };
  const renderSourceOptions = () => {
    const query = normalizeSourceTerm(sourceSearch.value);
    if (sourcesLoading && !sourcesRead) { sourceStatus.textContent = "正在读取官方来源…"; return; }
    sourceMatches = sourceOptions.filter(source => normalizeSourceTerm(`${source.company_name} ${source.company_type || ""} ${source.industry || ""}`).includes(query));
    if (!query) sourceMatches.unshift({source_id: "", company_name: "全部来源"});
    sourceActive = -1;
    sourceSearch.removeAttribute("aria-activedescendant");
    sourceList.replaceChildren();
    sourceMatches.forEach((source, index) => {
      const item = window.MakoView.node("li");
      item.id = `source-option-${index}`; item.dataset.index = index;
      item.setAttribute("role", "option"); item.setAttribute("aria-selected", "false");
      item.append(window.MakoView.node("b", source.company_name), window.MakoView.node("small", source.source_id ? sourceLabel(source) : "按当前岗位时效筛选全部官方来源"));
      sourceList.append(item);
    });
    sourceList.hidden = sourceMatches.length === 0;
    sourceSearch.setAttribute("aria-expanded", String(!sourceList.hidden));
    sourceStatus.textContent = sourceMatches.length ? `${sourceMatches.length} 个选项，按上下键浏览、回车选择。当前：${currentSourceLabel()}` : `未找到匹配的官方来源，请换个关键词。当前：${currentSourceLabel()}`;
  };
  const chooseSource = value => {
    if (sourceSelect.value !== value) { sourceSelect.value = value; sourceSelect.dispatchEvent(new Event("change", {bubbles: true})); }
    closeSourcePicker();
  };
  sourceSearch.addEventListener("focus", () => { sourceSearch.select(); if (!sourcesRead) loadSources(); else renderSourceOptions(); });
  sourceSearch.addEventListener("click", () => { if (sourceList.hidden && sourcesRead) renderSourceOptions(); });
  sourceSearch.addEventListener("input", () => {
    if (!sourceSearch.value && sourceSelect.value) { sourceSelect.value = ""; sourceSelect.dispatchEvent(new Event("change", {bubbles: true})); }
    renderSourceOptions();
  });
  sourceSearch.addEventListener("keydown", event => {
    if (event.isComposing) return;
    if (event.key === "Escape") { event.preventDefault(); closeSourcePicker(); }
    else if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      if (sourceList.hidden) renderSourceOptions();
      if (!sourceMatches.length) return;
      sourceActive = (sourceActive + (event.key === "ArrowDown" ? 1 : sourceActive < 0 ? 0 : -1) + sourceMatches.length) % sourceMatches.length;
      [...sourceList.children].forEach((item, index) => item.setAttribute("aria-selected", String(index === sourceActive)));
      const item = sourceList.children[sourceActive];
      sourceSearch.setAttribute("aria-activedescendant", item.id); item.scrollIntoView({block: "nearest"});
    } else if (event.key === "Enter" && !sourceList.hidden) {
      event.preventDefault(); if (sourceActive >= 0) chooseSource(sourceMatches[sourceActive].source_id);
    }
  });
  sourceSearch.addEventListener("blur", closeSourcePicker);
  sourceList.addEventListener("mousedown", event => event.preventDefault());
  sourceList.addEventListener("click", event => { const item = event.target.closest("[role='option']"); if (item) chooseSource(sourceMatches[Number(item.dataset.index)].source_id); });
  document.getElementById("clear-job-company").addEventListener("click", () => { chooseSource(""); sourceSearch.focus(); renderSourceOptions(); });
  const loadSources = async () => {
    if (sourcesLoading) return;
    sourcesLoading = true;
    const status = document.getElementById("job-source-status");
    const stop = window.MakoView.wait(status, "正在读取官方来源目录…");
    try {
      const response = await fetch("/jobs/sources");
      const payload = await readResponse(response);
      if (!response.ok) throw new Error(responseMessage(payload));
      if (!Array.isArray(payload?.sources) || !payload.sources.every(source => source && typeof source.source_id === "string" && source.source_id.trim() && typeof source.company_name === "string" && source.company_name.trim())) throw new Error("官方来源目录格式不正确");
      const select = document.getElementById("job-company"), selected = select.value;
      select.replaceChildren(new Option("全部来源", ""));
      payload.sources.forEach(source => {
        select.append(new Option(source.company_name, source.source_id));
      });
      select.value = payload.sources.some(source => source.source_id === selected) ? selected : "";
      sourceOptions = payload.sources; sourcesRead = true;
      if (selected !== select.value) select.dispatchEvent(new Event("change", {bubbles: true}));
      if (document.activeElement === sourceSearch) renderSourceOptions(); else closeSourcePicker();
      status.textContent = payload.sources.length ? `已读取 ${payload.sources.length} 个官方来源。查找岗位时使用你选择的时效。` : "当前暂无可用官方来源，可稍后重新读取。";
    } catch (error) { status.textContent = `${error.message || "目录读取失败"}，可重新读取。`; sourceStatus.textContent = status.textContent; }
    finally { stop(); sourcesLoading = false; }
  };
  document.getElementById("choose-job-source").addEventListener("click", loadSources);
  document.getElementById("job-company").addEventListener("change", () => {
    contextVersion++; jobsLoaded = false; jobs.clear(); jobSelect.replaceChildren(new Option("请按当前来源查找岗位", ""));
    requirementList.replaceChildren(); requirementPanel.hidden = true; markInputChanged();
  });
  updateSkill(activeSkill);
  const emptyDraft = snapshot();
})();
