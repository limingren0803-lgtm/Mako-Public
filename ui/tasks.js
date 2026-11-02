(() => {
  const intentLabels = {
    career_profile: "背景诊断", career_match: "方向匹配", career_jd: "JD 分析",
    career_resume: "简历优化", career_interview: "面试准备", career_planning: "行动规划"
  };
  const state = {items: [], overviewItems: [], tracks: [], materials: [], currentResumeId: null, selectedId: null, current: null, analysis: null, retryCreate: null, editingId: null};
  let busy = false;
  const list = document.getElementById("task-list");
  const detail = document.getElementById("task-detail");
  const dialog = document.getElementById("task-dialog");
  const status = document.getElementById("task-form-status");
  const message = document.getElementById("task-message");
  const setMessage = (value = "", kind = "") => {
    message.textContent = value;
    message.className = `workspace-message${kind ? ` ${kind}` : ""}`;
  };
  const text = (tag, value, className = "") => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const taskView = id => state.items.find(item => item.task.task_id === id);
  const referenceLabel = item => {
    const track = item.references.track?.track;
    if (track) return `${track.company_name} · ${track.title}`;
    if (item.references.reviewed_job) return "系统已核验职位";
    return "未绑定岗位";
  };
  const materialLabel = task => task.personal_knowledge_mode === "off"
    ? "本任务不使用"
    : task.personal_knowledge_mode === "selected"
      ? `指定 ${task.personal_material_ids.length} 份`
      : "自动查找相关内容";
  const jobScopeLabel = item => item.references.track?.track?.source_kind === "manual_jd"
    ? "使用用户提供 JD"
    : `近 ${item.task.job_max_age_days || 30} 天 · ${item.task.job_data_mode === "official_links_if_missing" ? "不足时提供官网入口" : "仅已核验"}`;
  const actionButton = (label, operation, className = "secondary") => {
    const node = text("button", label, className);
    node.type = "button";
    node.dataset.taskOperation = operation;
    return node;
  };

  const renderList = () => {
    const filter = document.getElementById("task-status-filter").value;
    const items = state.items.filter(item => !filter || item.task.status === filter);
    list.replaceChildren();
    if (!items.length) return list.appendChild(text("p", filter === "archived" ? "还没有归档任务。" : "这里还没有任务。选择一个目标开始。", "task-list-empty"));
    items.forEach(item => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `task-list-item${item.task.task_id === state.selectedId ? " active" : ""}`;
      button.dataset.taskId = item.task.task_id;
      button.append(text("b", item.task.goal), text("span", `${intentLabels[item.task.career_intent]} · ${referenceLabel(item)}`));
      list.appendChild(button);
    });
  };

  const loadOverview = async () => {
    const target = document.getElementById("dashboard-focus");
    target.setAttribute("aria-busy", "true");
    try {
      const payload = await window.MakoWorkspace.fetch("/tasks?status=active&limit=200");
      state.overviewItems = payload.items;
      const item = state.overviewItems[0];
      target.replaceChildren();
      const copy = text("div", "", "dashboard-focus-copy");
      if (item) copy.append(text("p", "继续你的求职准备", "eyebrow"));
      copy.append(text("h2", item ? item.task.goal : "让每一次准备，\n都有下一步。"));
      copy.append(text("p", item ? `${intentLabels[item.task.career_intent]} · ${referenceLabel(item)}` : "选定目标，带上经历和材料。Mako 帮你把分析、简历与面试接在一起。", "dashboard-focus-description"));
      const controls = text("div", "", "dashboard-focus-actions");
      const start = text("button", item ? `继续${intentLabels[item.task.career_intent]} →` : "开始第一个求职任务 →", "primary");
      start.type = "button";
      if (item) start.dataset.dashboardContinue = item.task.task_id;
      else start.dataset.dashboardCreate = "";
      const browse = text("button", "查看所有任务", "text-button");
      browse.type = "button"; browse.dataset.showPage = "tasks";
      controls.append(start, browse); copy.append(controls);
      const finn = document.createElement("img");
      finn.src = "assets/finn-office.png?v=2"; finn.alt = ""; finn.width = 220; finn.height = 220;
      target.append(copy, finn);
      const footer = text("div", "", "dashboard-focus-footer");
      footer.append(text("span", item ? materialLabel(item.task) : "先确定目标，再选择工具"), text("span", `${state.overviewItems.length} 个进行中任务`));
      target.append(footer);
    } catch (error) {
      target.replaceChildren(text("h2", "任务暂时没有读到"), text("p", "已有记录不会改变，请稍后重试。"));
      const retry = text("button", "重新读取", "primary"); retry.type = "button";
      retry.addEventListener("click", loadOverview); target.append(retry);
    } finally { target.removeAttribute("aria-busy"); }
  };

  const renderDetail = () => {
    const item = taskView(state.selectedId);
    detail.replaceChildren();
    detail.parentElement.dataset.empty = String(!item);
    if (!item) {
      const welcome = document.createElement("div");
      welcome.className = "task-welcome";
      const introduction = document.createElement("header");
      introduction.className = "welcome-heading";
      const copy = document.createElement("div");
      copy.append(text("p", "从一个具体目标开始", "eyebrow"), text("h2", "这次求职，先解决哪件事？"), text("p", "选择目标，带上岗位与材料。每次分析之后，继续由你决定下一步。"));
      const finn = document.createElement("img");
      finn.src = "assets/finn-graduate.png";
      finn.alt = "";
      finn.width = 144;
      finn.height = 144;
      introduction.append(copy, finn);
      const choices = document.createElement("div");
      choices.className = "task-goal-choices";
      const goals = ["了解我的优势与缺口", "找到适合的岗位方向", "看懂一个具体 JD", "改好准备投递的简历", "准备即将到来的面试", "安排近期求职行动"];
      Object.entries(intentLabels).forEach(([intent, label], index) => {
        const button = actionButton("", "create", "task-goal-choice");
        button.dataset.intent = intent;
        button.append(text("span", String(index + 1).padStart(2, "0"), "goal-number"), text("b", goals[index]), text("small", label), text("span", "↗", "goal-arrow"));
        choices.appendChild(button);
      });
      const route = document.createElement("ol");
      route.className = "welcome-route";
      ["带上岗位与材料", "确认后开始分析", "决定下一步行动"].forEach(label => route.appendChild(text("li", label)));
      welcome.append(introduction, choices, route);
      detail.appendChild(welcome);
      return;
    }
    const task = item.task;
    const heading = document.createElement("div");
    heading.className = "task-detail-heading";
    const title = document.createElement("div");
    title.append(text("p", task.status === "active" ? "进行中" : "已归档", "eyebrow"), text("h2", task.goal));
    heading.append(title);

    const context = document.createElement("dl");
    context.className = "task-context-grid";
    const resume = item.references.resume?.material || state.materials.find(material => material.material_id === task.resume_material_id);
    [["目标岗位", referenceLabel(item)], ["岗位范围", jobScopeLabel(item)], ["简历", resume?.title || (task.resume_material_id ? "所选简历当前不可用" : "未指定")], ["补充材料", materialLabel(task)]].forEach(([label, value]) => {
      const cell = document.createElement("div");
      cell.append(text("dt", label), text("dd", value));
      context.appendChild(cell);
    });
    const warning = [];
    if (item.references.track?.status === "unavailable") warning.push("绑定的目标岗位已不可用");
    if (item.references.reviewed_job?.status === "updated") warning.push("绑定的官方职位已有新版本，本任务仍保留原版本");
    const unavailable = item.references.personal_materials?.filter(value => value.status !== "current").length || 0;
    if (unavailable) warning.push(`${unavailable} 份引用材料当前不可用`);
    if (task.resume_material_id && item.references.resume?.status && item.references.resume.status !== "current") warning.push("所选简历已变化，请重新核对");
    if (!task.resume_material_id && item.references.personal_materials?.some(reference => task.personal_material_ids.includes(reference.material_id) && reference.material?.category === "resume")) warning.push("这项旧任务把简历列在补充材料中。继续分析前，请编辑任务并单独选定简历");

    const preparation = document.createElement("section");
    preparation.className = "task-route-section";
    preparation.dataset.routeNumber = "01";
    const preparationHeading = document.createElement("div");
    preparationHeading.className = "task-section-heading";
    preparationHeading.append(text("h3", "岗位与材料"));
    if (task.status === "active") preparationHeading.append(actionButton("调整任务上下文", "edit", "text-button"));
    preparation.append(preparationHeading, context);
    if (warning.length) preparation.append(text("p", warning.join("；"), "task-reference-warning"));

    const stage = document.createElement("section");
    stage.className = "task-route-section current-stage";
    stage.dataset.routeNumber = "02";
    const stageHeading = document.createElement("div");
    stageHeading.className = "task-section-heading";
    const stageTitle = document.createElement("div");
    const analysisStatus = task.last_analysis_status === "not_started" ? "尚未分析" : task.last_analysis_status === "completed" ? "上次分析已完成" : "上次分析未完成";
    stageTitle.append(text("p", `当前阶段 · ${analysisStatus}`, "eyebrow"), text("h3", intentLabels[task.career_intent]));
    stageHeading.append(stageTitle);
    if (task.status === "active") stageHeading.append(actionButton("继续当前阶段", "continue", "primary"));
    const saved = document.createElement("details");
    saved.className = "task-saved-result";
    saved.open = true;
    saved.append(text("summary", task.saved_analysis_text ? `查看已保存的分析${intentLabels[task.saved_analysis_intent] ? ` · ${intentLabels[task.saved_analysis_intent]}` : ""}` : "本阶段的结果如何保留"));
    const savedContent = text("div");
    window.MakoView.renderResult(savedContent, task.saved_analysis_text || "还没有保存结果。分析完成后由你决定是否保留。", task.saved_analysis_intent === "career_planning");
    saved.append(savedContent);
    stage.append(stageHeading, saved);

    const next = document.createElement("section");
    next.className = "task-route-section";
    next.dataset.routeNumber = "03";
    next.append(text("h3", "下一步"), text("p", task.status === "active" ? "沿用当前岗位与材料，选择需要继续准备的内容。" : "任务已归档，已保存的结果仍可查看和导出。", "hint"));
    const actions = document.createElement("div");
    actions.className = "task-detail-actions";
    if (task.status === "active") {
      item.next_intents.forEach(intent => {
        const button = actionButton(`继续到${intentLabels[intent]}`, "advance");
        button.dataset.intent = intent;
        actions.appendChild(button);
      });
    }
    actions.append(actionButton("查看今日行动", "actions", "text-button"));
    next.append(actions);
    const management = document.createElement("details");
    management.className = "task-management";
    management.append(text("summary", "任务管理"));
    if (task.status === "active") management.append(actionButton("归档任务", "archive", "text-button"));
    management.append(actionButton("删除任务", "delete", "text-button danger-text"));
    next.append(management);
    const studio = text("div", "", "task-studio");
    studio.append(preparation, stage, next);
    const route = document.createElement("ol");
    window.MakoView.route(route, task);
    detail.append(heading, route, studio);
  };

  const load = async ({quiet = false} = {}) => {
    if (!quiet) detail.setAttribute("aria-busy", "true");
    try {
      const filter = document.getElementById("task-status-filter").value;
      const suffix = filter ? `?status=${filter}&limit=200` : "?limit=200";
      const payload = await window.MakoWorkspace.fetch(`/tasks${suffix}`);
      state.items = payload.items;
      if (state.selectedId && !taskView(state.selectedId)) state.selectedId = null;
      if (!state.selectedId && state.items.length) state.selectedId = state.items[0].task.task_id;
      renderList();
      renderDetail();
      if (!quiet) setMessage();
    } catch (error) {
      setMessage(`${error.message || "任务读取失败"}。当前输入不会丢失，可以稍后重试。`, "error");
    } finally {
      detail.removeAttribute("aria-busy");
    }
  };

  const renderDialogMaterials = (editing = null) => {
    const picker = document.getElementById("task-material-picker");
    picker.replaceChildren();
    const available = state.materials.filter(item => item.status === "active" && item.index_status === "ready" && (item.category !== "resume" || editing?.task.personal_material_ids.includes(item.material_id)));
    if (!available.length) return picker.appendChild(text("p", "当前没有可用材料，可以先选择自动查找或不使用。", "hint"));
    available.forEach(material => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = material.material_id;
      label.append(input, text("span", material.title));
      picker.appendChild(label);
    });
  };

  const updateJobScopeVisibility = () => {
    const trackId = document.getElementById("task-track").value;
    const manual = state.tracks.find(item => item.track.track_id === trackId)?.track.source_kind === "manual_jd";
    document.getElementById("task-job-scope-fields").hidden = manual;
    document.getElementById("task-job-scope-hint").hidden = manual;
  };

  const openDialog = async (preset = {}) => {
    const editing = preset.task || null;
    state.editingId = editing?.task.task_id || null;
    document.getElementById("task-form").reset();
    if (preset.intent) document.getElementById("task-intent").value = preset.intent;
    document.getElementById("task-material-picker").hidden = true;
    status.textContent = "正在读取可用岗位和材料…";
    status.className = "status-message";
    document.querySelector("#task-dialog h2").textContent = editing ? "调整任务上下文" : "新建求职任务";
    document.getElementById("save-task").textContent = editing ? "保存并继续" : "创建并开始";
    document.getElementById("task-intent").disabled = Boolean(editing);
    dialog.showModal();
    try {
      const [tracks, materials] = await Promise.all([
        window.MakoWorkspace.fetch("/tracks?limit=200"),
        window.MakoWorkspace.fetch("/materials?status=active&limit=200")
      ]);
      state.tracks = tracks.items;
      state.materials = materials.items;
      state.currentResumeId = materials.current_resume_material_id || null;
      const resumeSelect = document.getElementById("task-resume");
      resumeSelect.replaceChildren(new Option("暂不使用简历", ""));
      state.materials.filter(item => item.category === "resume" && item.status === "active" && item.index_status === "ready").forEach(item => resumeSelect.appendChild(new Option(`${item.title}${item.material_id === state.currentResumeId ? " · 当前简历" : ""}`, item.material_id)));
      const select = document.getElementById("task-track");
      select.replaceChildren(new Option("暂不绑定岗位", ""));
      state.tracks.forEach(item => select.appendChild(new Option(`${item.track.company_name} · ${item.track.title}`, item.track.track_id)));
      renderDialogMaterials(editing);
      if (editing) {
        document.getElementById("task-goal").value = editing.task.goal;
        document.getElementById("task-intent").value = editing.task.career_intent;
        select.value = editing.task.track_id || "";
        document.getElementById("task-job-age").value = String(editing.task.job_max_age_days || 30);
        document.getElementById("task-job-mode").value = editing.task.job_data_mode || "verified_only";
        const mode = editing.task.personal_knowledge_mode;
        if (editing.task.resume_material_id && !state.materials.some(item => item.material_id === editing.task.resume_material_id && item.category === "resume" && item.status === "active" && item.index_status === "ready")) resumeSelect.appendChild(new Option("原简历当前不可用，请重新选择", editing.task.resume_material_id));
        resumeSelect.value = editing.task.resume_material_id || "";
        document.querySelector(`input[name="task-material-mode"][value="${mode}"]`).checked = true;
        document.getElementById("task-material-picker").hidden = mode !== "selected";
        editing.task.personal_material_ids.forEach(id => {
          const input = document.querySelector(`#task-material-picker input[value="${CSS.escape(id)}"]`);
          if (input) input.checked = true;
        });
      } else {
        resumeSelect.value = state.currentResumeId || "";
        if (preset.trackId) select.value = preset.trackId;
        if (preset.materialId) {
          document.querySelector('input[name="task-material-mode"][value="selected"]').checked = true;
          document.getElementById("task-material-picker").hidden = false;
          const input = document.querySelector(`#task-material-picker input[value="${CSS.escape(preset.materialId)}"]`);
          if (input) input.checked = true;
        }
      }
      updateJobScopeVisibility();
      resumeSelect.disabled = document.querySelector('input[name="task-material-mode"]:checked')?.value === "off";
      status.textContent = "";
    } catch (error) {
      status.textContent = error.message || "上下文读取失败";
      status.className = "status-message error";
    }
  };

  const createTask = async () => {
    const goal = document.getElementById("task-goal").value.trim();
    if (!goal) throw new Error("请说明这次要求职任务要解决的问题");
    const mode = document.querySelector('input[name="task-material-mode"]:checked')?.value || "auto";
    const materialIds = [...document.querySelectorAll("#task-material-picker input:checked")].map(input => input.value);
    const resumeId = mode === "off" ? null : document.getElementById("task-resume").value || null;
    if (resumeId && !state.materials.some(item => item.material_id === resumeId && item.category === "resume" && item.status === "active" && item.index_status === "ready")) throw new Error("所选简历当前不可用，请重新选择或暂不使用简历");
    if (mode === "selected" && !materialIds.length) throw new Error("选择指定材料时，请至少勾选一份可用材料");
    const payload = {
      goal,
      career_intent: document.getElementById("task-intent").value,
      track_id: document.getElementById("task-track").value || null,
      job_max_age_days: Number(document.getElementById("task-job-age").value),
      job_data_mode: document.getElementById("task-job-mode").value,
      personal_knowledge_mode: mode,
      personal_material_ids: mode === "selected" ? materialIds : [],
      resume_material_id: resumeId
    };
    if (state.editingId) {
      const current = taskView(state.editingId);
      if (!current) throw new Error("任务状态已变化，请关闭后重新打开");
      const updated = await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(state.editingId)}`, {
        method: "PATCH", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({...payload, revision: current.task.revision, career_intent: current.task.career_intent})
      });
      const index = state.items.findIndex(item => item.task.task_id === state.editingId);
      state.items[index] = updated;
      state.current = updated;
      dialog.close();
      renderList();
      renderDetail();
      return openInSkill(updated);
    }
    const body = JSON.stringify(payload);
    const key = state.retryCreate?.body === body ? state.retryCreate.key : `task_${crypto.randomUUID().replaceAll("-", "")}`;
    state.retryCreate = {body, key};
    const created = await window.MakoWorkspace.fetch("/tasks", {method: "POST", headers: {"Content-Type": "application/json", "Idempotency-Key": key}, body});
    state.retryCreate = null;
    state.selectedId = created.task.task_id;
    document.getElementById("task-status-filter").value = "active";
    dialog.close();
    await load({quiet: true});
    openInSkill(taskView(state.selectedId));
  };

  const openInSkill = item => {
    if (!item || !window.MakoApp.canSwitch()) return;
    window.MakoWorkspace.showSkill();
    window.MakoApp.openTask(item);
    state.current = item;
    window.MakoApp.restoreRetained();
    window.MakoContinuity?.navigate();
  };

  const refreshCurrent = async taskId => {
    const item = await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(taskId)}`);
    const index = state.items.findIndex(value => value.task.task_id === taskId);
    if (index >= 0) state.items[index] = item;
    else state.items.unshift(item);
    if (state.current?.task.task_id === taskId) state.current = item;
    renderList();
    renderDetail();
    return item;
  };

  const restoreAnalysis = value => {
    state.analysis = value && window.MakoView.analysisState(value) !== "empty" ? value : null;
    if (!state.analysis) document.getElementById("task-result-tools").hidden = true;
  };
  const captureAnalysis = payload => {
    if (!state.current || payload.task_id !== state.current.task.task_id) return;
    state.current.task.revision = Math.max(state.current.task.revision, payload.task_revision);
    restoreAnalysis(payload);
    if (!state.analysis) return;
    const tools = document.getElementById("task-result-tools");
    const candidates = document.getElementById("task-action-candidates");
    tools.hidden = false;
    document.getElementById("save-task-result").disabled = false;
    document.getElementById("save-task-result").textContent = "保存到当前任务";
    const next = document.getElementById("task-next-actions");
    next.replaceChildren();
    const review = text("button", "返回任务，继续下一步", "secondary"); review.type = "button";
    review.addEventListener("click", () => window.MakoWorkspace.showPage("tasks"));
    const plan = text("button", "查看行动日程", "secondary"); plan.type = "button";
    plan.addEventListener("click", () => window.MakoWorkspace.showPage("actions"));
    next.append(review, plan);
    if (payload.action_candidates_status === "invalid") {
      const manual = text("button", "自己添加下一步行动", "secondary"); manual.type = "button";
      manual.addEventListener("click", () => window.MakoWorkspace.newAction());
      next.append(manual);
    }
    document.getElementById("task-result-status").textContent = payload.action_candidates_status === "invalid"
      ? "结果尚未保存；这次未能整理出可勾选的行动。分析正文仍可保存，你也可以自己添加下一步。"
      : "结果尚未保存。";
    candidates.replaceChildren();
    candidates.hidden = payload.action_candidates_status !== "valid" || !payload.action_candidates.length;
    if (!candidates.hidden) {
      candidates.append(text("h3", "应用到工作台"), text("p", "选择后先加入待确认行动；可修改内容、日期和优先级，再确认进入计划。"));
      payload.action_candidates.forEach((candidate, index) => {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = String(index);
        label.append(input, text("span", candidate.title), text("small", `${candidate.reason} · 完成标准：${candidate.completion_criteria}`));
        candidates.appendChild(label);
      });
      candidates.appendChild(actionButton("加入待确认行动", "accept-suggestions", "secondary"));
    }
  };

  const saveAnalysis = async () => {
    if (!state.current || !state.analysis || !window.MakoApp.canSwitch()) return;
    if (window.MakoView.analysisState(state.analysis) === "partial" && !window.confirm("这次回答未完成。只保留已返回的正文与来源，仍要保存到当前任务吗？")) return;
    const button = document.getElementById("save-task-result");
    button.disabled = true;
    busy = true;
    const payload = state.analysis;
    try {
      const saved = await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(payload.task_id)}/saved-analysis`, {
        method: "PUT", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({revision: state.current.task.revision, confirmation: "SAVE_ANALYSIS_TO_TASK", request_id: payload.request_id, analysis_text: payload.response?.trim() ? payload.response : payload.conclusion, sources: payload.task_analysis_sources})
      });
      state.current = saved;
      document.getElementById("task-result-status").textContent = `已保存到任务“${saved.task.goal}”，可返回任务继续下一步。`;
      button.textContent = "已保存";
      await refreshCurrent(payload.task_id);
    } catch (error) {
      button.disabled = false;
      await refreshCurrent(state.current.task.task_id).catch(() => null);
      document.getElementById("task-result-status").textContent = `${error.message || "结果保存失败"} 已重新读取任务状态。`;
    } finally { busy = false; }
  };

  const acceptSuggestions = async () => {
    if (!state.current || !state.analysis || !window.MakoApp.canSwitch()) return;
    const checked = [...document.querySelectorAll("#task-action-candidates input:checked")].map(input => state.analysis.action_candidates[Number(input.value)]);
    if (!checked.length) return document.getElementById("task-result-status").textContent = "请先选择需要保留的行动建议。";
    busy = true;
    try {
      const body = JSON.stringify({task_revision: state.current.task.revision, suggestions: checked});
      await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(state.current.task.task_id)}/action-suggestions`, {method: "POST", headers: {"Content-Type": "application/json", "Idempotency-Key": `suggest_${state.analysis.request_id}`}, body});
      document.getElementById("task-action-candidates").hidden = true;
      document.getElementById("task-result-status").textContent = `已加入 ${checked.length} 项待确认行动。`;
      const arrange = text("button", "去安排行动日期 →", "primary"); arrange.type = "button";
      arrange.addEventListener("click", () => window.MakoWorkspace.showSuggestedActions());
      document.getElementById("task-next-actions").prepend(arrange);
      await refreshCurrent(state.current.task.task_id);
    } catch (error) {
      await refreshCurrent(state.current.task.task_id).catch(() => null);
      document.getElementById("task-result-status").textContent = `${error.message || "行动建议保存失败"} 已重新读取任务状态。`;
    } finally { busy = false; }
  };

  const updateIntent = async (item, intent) => {
    if (!window.MakoApp.canSwitch()) return;
    busy = true;
    let updated;
    try { updated = await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(item.task.task_id)}`, {
      method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({revision: item.task.revision, career_intent: intent})
    });
    } finally { busy = false; }
    const index = state.items.findIndex(value => value.task.task_id === item.task.task_id);
    if (index >= 0) state.items[index] = updated;
    openInSkill(updated);
  };

  const handleOperation = async target => {
    if (!window.MakoApp.canSwitch()) return;
    if (target.dataset.taskOperation === "create") return openDialog({intent: target.dataset.intent});
    if (target.dataset.taskOperation === "actions") return window.MakoWorkspace.showPage("actions");
    const item = taskView(state.selectedId);
    if (!item) return;
    const operation = target.dataset.taskOperation;
    if (operation === "continue") return openInSkill(item);
    if (operation === "edit") return openDialog({task: item});
    if (operation === "advance") return updateIntent(item, target.dataset.intent);
    if (operation === "archive") {
      await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(item.task.task_id)}/archive`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({revision: item.task.revision})});
      state.selectedId = null;
      return load({quiet: true});
    }
    if (operation === "delete") {
      const impact = await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(item.task.task_id)}/deletion-impact`);
      const note = impact.action_references ? `，${impact.action_references} 项行动会保留但不再关联此任务` : "";
      if (!window.confirm(`删除任务“${item.task.goal}”${note}。岗位和个人材料不会删除，是否继续？`)) return;
      await window.MakoWorkspace.fetch(`/tasks/${encodeURIComponent(item.task.task_id)}?revision=${item.task.revision}&confirmation=DELETE_CAREER_TASK`, {method: "DELETE"});
      state.selectedId = null;
      return load({quiet: true});
    }
  };

  document.getElementById("open-task-dialog").addEventListener("click", () => openDialog());
  document.getElementById("task-status-filter").addEventListener("change", () => load());
  document.getElementById("task-track").addEventListener("change", updateJobScopeVisibility);
  document.querySelectorAll('input[name="task-material-mode"]').forEach(input => input.addEventListener("change", () => {
    document.getElementById("task-material-picker").hidden = input.value !== "selected" || !input.checked;
    document.getElementById("task-resume").disabled = input.checked && input.value === "off";
  }));
  document.getElementById("task-material-picker").addEventListener("change", event => {
    const checked = document.querySelectorAll("#task-material-picker input:checked");
    if (checked.length <= 20) return;
    event.target.checked = false;
    status.textContent = "每个任务最多指定 20 份个人材料。";
    status.className = "status-message error";
  });
  document.getElementById("task-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (event.submitter?.value === "cancel") { state.editingId = null; return dialog.close(); }
    const button = document.getElementById("save-task");
    button.disabled = true;
    status.textContent = "正在创建任务…";
    try { await createTask(); } catch (error) { status.textContent = error.message || "任务创建失败"; status.className = "status-message error"; } finally { button.disabled = false; }
  });
  list.addEventListener("click", event => {
    const target = event.target.closest("[data-task-id]");
    if (!target) return;
    state.selectedId = target.dataset.taskId;
    renderList();
    renderDetail();
  });
  detail.addEventListener("click", event => {
    const target = event.target.closest("[data-task-operation]");
    if (target) handleOperation(target).catch(async error => {
      await load({quiet: true}).catch(() => null);
      setMessage(`${error.message || "任务操作失败"} 已重新读取最新任务。`, "error");
    });
  });
  document.getElementById("save-task-result").addEventListener("click", saveAnalysis);
  document.getElementById("task-action-candidates").addEventListener("click", event => {
    if (event.target.closest('[data-task-operation="accept-suggestions"]')) acceptSuggestions();
  });
  document.getElementById("back-to-task").addEventListener("click", () => window.MakoWorkspace.showPage("tasks"));
  document.getElementById("export-tasks").addEventListener("click", async () => {
    try {
      const payload = await window.MakoWorkspace.fetch("/tasks/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: "application/json;charset=utf-8"}));
      const link = document.createElement("a");
      link.href = url; link.download = `mako-career-tasks-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
      setMessage("求职任务已导出。", "success");
    } catch (error) {
      setMessage(error.message || "任务导出失败", "error");
    }
  });

  document.getElementById("dashboard-focus").addEventListener("click", event => {
    if (event.target.closest("[data-dashboard-create]")) return openDialog();
    const control = event.target.closest("[data-dashboard-continue]");
    if (!control) return;
    const item = state.overviewItems.find(value => value.task.task_id === control.dataset.dashboardContinue);
    if (!item) return;
    state.selectedId = item.task.task_id;
    document.getElementById("task-status-filter").value = "active";
    openInSkill(item);
  });
  window.MakoTasks = Object.freeze({busy: () => busy, analysis: () => state.analysis, restoreAnalysis, continueWith: intent => updateIntent(state.current, intent), refresh: refreshCurrent, load, loadOverview, captureAnalysis, current: () => state.current, openCreate: preset => openDialog(preset),
    selected: () => state.selectedId,
    resume: async (id, skill) => {
      const item = await refreshCurrent(id);
      if (skill && (item.task.status !== "active" || item.task.career_intent !== skill)) throw new Error("任务阶段或状态已变化，旧草稿仍保留。请先查看任务，再选择对应阶段。");
      state.selectedId = id;
      renderList(); renderDetail();
      if (skill) openInSkill(item);
    }
  });
  if (!document.querySelector('[data-page="tasks"]').hidden) load().catch(() => null);
  if (!document.querySelector('[data-page="overview"]').hidden) loadOverview();
})();
