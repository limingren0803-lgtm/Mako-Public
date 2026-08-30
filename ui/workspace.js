(() => {
  const WORKSPACE_API = "/v2/workspace";
  const stageLabels = {
    watching: "关注中",
    preparing: "准备中",
    applied: "已投递",
    interviewing: "面试中",
    closed: "已结束"
  };
  const statusLabels = {
    suggested: "待确认",
    todo: "待完成",
    completed: "已完成",
    cancelled: "已取消"
  };
  const priorityLabels = {high: "高优先级", medium: "中优先级", low: "低优先级"};
  const closedReasonLabels = {
    not_applied: "未投递",
    rejected: "未通过",
    user_withdrew: "主动放弃",
    offer_received: "获得 Offer",
    other: "其他"
  };
  const viewCopy = {
    overview: ["今天先完成真正影响进度的事", "目标岗位、判断依据和下一步行动集中在这里，六项分析结果不再停留在一次对话里。"],
    tracks: ["每个目标岗位都有一条清楚的进度线", "保留职位来源、当前阶段和关联行动，避免在不同分析板块之间重复整理同一份 JD。"],
    actions: ["把分析结果变成可以完成的下一步", "每项行动都说明完成标准，由你决定何时开始、完成或重新打开。"],
    materials: ["让个人材料在需要时提供依据", "材料先预览、再保存；后续分析只使用你启用且达到相关性要求的内容。"]
  };

  const state = {
    sessionReady: false,
    tracks: [],
    actions: [],
    summary: null,
    reviewedJobs: new Map(),
    selectedTrackId: null,
    editingActionId: null,
    retryTrackCreate: null,
    retryActionCreate: null
  };

  const workspaceView = document.getElementById("career-workspace-view");
  const skillView = document.getElementById("skill-workspace-view");
  const workspaceNav = document.getElementById("workspace-nav");
  const skillNav = document.getElementById("skill-nav");
  const workspaceMessage = document.getElementById("workspace-message");
  const sessionState = document.getElementById("workspace-session-state");
  const trackDialog = document.getElementById("track-dialog");
  const actionDialog = document.getElementById("action-dialog");

  const setMessage = (message = "", kind = "") => {
    workspaceMessage.textContent = message;
    workspaceMessage.className = `workspace-message${kind ? ` ${kind}` : ""}`;
  };

  const responseMessage = payload => {
    if (typeof payload?.detail === "string") return payload.detail;
    if (typeof payload?.detail?.message === "string") return payload.detail.message;
    if (Array.isArray(payload?.detail)) return payload.detail[0]?.msg || "输入内容不符合要求";
    return payload?.error?.message || "请求未完成";
  };

  const readPayload = async response => {
    if (response.status === 204) return null;
    const type = response.headers.get("content-type") || "";
    if (!type.includes("application/json")) throw new Error("服务返回了无法识别的响应");
    return response.json();
  };

  const startSession = async () => {
    const response = await fetch(`${WORKSPACE_API}/session`, {
      method: "POST",
      credentials: "same-origin"
    });
    await readPayload(response);
    if (!response.ok) throw new Error("本地工作区会话未能建立");
    state.sessionReady = true;
    sessionState.textContent = "本地工作区已连接";
    sessionState.className = "session-state ready";
  };

  const workspaceFetch = async (path, options = {}, retry = true) => {
    if (!state.sessionReady) await startSession();
    const response = await fetch(`${WORKSPACE_API}${path}`, {
      credentials: "same-origin",
      ...options,
      headers: {Accept: "application/json", ...(options.headers || {})}
    });
    if (response.status === 401 && retry) {
      state.sessionReady = false;
      await startSession();
      return workspaceFetch(path, options, false);
    }
    const payload = await readPayload(response);
    if (response.status === 409) {
      await loadWorkspaceData({quiet: true});
      throw new Error("数据已在其他窗口发生变化，已重新加载最新内容。请确认后重试。");
    }
    if (!response.ok) throw new Error(responseMessage(payload));
    return payload;
  };

  window.MakoWorkspace = Object.freeze({fetch: workspaceFetch, ensureSession: startSession});

  const textElement = (tag, text, className = "") => {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    return element;
  };

  const button = (label, operation, id, className = "mini-button") => {
    const element = document.createElement("button");
    element.type = "button";
    element.className = className;
    element.textContent = label;
    element.dataset.operation = operation;
    element.dataset.id = id;
    return element;
  };

  const emptyState = (number, title, detail) => {
    const container = document.createElement("div");
    container.className = "workspace-empty";
    container.append(textElement("span", number), textElement("h3", title), textElement("p", detail));
    return container;
  };

  const trackById = trackId => state.tracks.find(item => item.track.track_id === trackId)?.track;
  const actionById = actionId => state.actions.find(item => item.action_id === actionId);
  const trackLabel = trackId => {
    const track = trackById(trackId);
    return track ? `${track.company_name} · ${track.title}` : "通用行动";
  };

  const formatDate = value => {
    if (!value) return "未设置";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("zh-CN", {month: "short", day: "numeric"}).format(date);
  };

  const formatDateTimeLocal = value => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  };

  const actionCard = action => {
    const article = document.createElement("article");
    article.className = "action-row";
    article.dataset.priority = action.priority;
    article.dataset.status = action.status;

    let mainOperation = "edit";
    let mainSymbol = "·";
    let mainLabel = "查看行动";
    if (action.status === "todo") {
      mainOperation = "complete";
      mainSymbol = "✓";
      mainLabel = "标记完成";
    } else if (action.status === "completed" || action.status === "cancelled") {
      mainOperation = "reopen";
      mainSymbol = "↺";
      mainLabel = "重新打开";
    } else if (action.status === "suggested") {
      mainOperation = "edit";
      mainSymbol = "?";
      mainLabel = "检查建议";
    }
    const check = button(mainSymbol, mainOperation, action.action_id, "action-check");
    check.setAttribute("aria-label", mainLabel);

    const content = document.createElement("div");
    content.className = "action-content";
    content.appendChild(textElement("h3", action.title));
    content.appendChild(textElement("p", `完成标准：${action.completion_criteria}`));
    if (action.reason) content.appendChild(textElement("p", `为什么做：${action.reason}`, "action-reason"));

    const meta = document.createElement("div");
    meta.className = "action-meta";
    meta.append(
      textElement("span", statusLabels[action.status] || action.status),
      textElement("span", priorityLabels[action.priority] || action.priority),
      textElement("span", action.due_at ? `截止 ${formatDate(action.due_at)}` : "无截止时间"),
      textElement("span", trackLabel(action.track_id))
    );
    content.appendChild(meta);

    if (action.source_ref) {
      const trace = document.createElement("div");
      trace.className = "source-trace";
      trace.textContent = `依据：${action.source_ref.label}${action.source_ref.excerpt ? ` · ${action.source_ref.excerpt}` : ""}`;
      content.appendChild(trace);
    }

    const actions = document.createElement("div");
    actions.className = "row-actions";
    if (action.status === "suggested") {
      actions.append(button("检查并加入", "edit", action.action_id), button("不采用", "cancel", action.action_id));
    } else {
      actions.appendChild(button("编辑", "edit", action.action_id));
      if (action.status === "todo") actions.appendChild(button("取消", "cancel", action.action_id));
      if (["completed", "cancelled"].includes(action.status)) actions.appendChild(button("重新打开", "reopen", action.action_id));
      actions.appendChild(button("删除", "delete", action.action_id, "mini-button danger"));
    }
    article.append(check, content, actions);
    return article;
  };

  const renderActionCollection = (target, actions, emptyTitle, emptyDetail) => {
    target.replaceChildren();
    if (!actions.length) {
      target.appendChild(emptyState("✓", emptyTitle, emptyDetail));
      return;
    }
    actions.forEach(action => target.appendChild(actionCard(action)));
  };

  const renderSummary = () => {
    if (!state.summary) return;
    const activeTracks = Object.entries(state.summary.stage_counts)
      .filter(([stage]) => stage !== "closed")
      .reduce((total, [, count]) => total + count, 0);
    document.getElementById("summary-priority-count").textContent = state.summary.today_priority.length;
    document.getElementById("summary-due-count").textContent = state.summary.due_within_7_days.length;
    document.getElementById("summary-track-count").textContent = activeTracks;
    document.getElementById("summary-action-count").textContent = state.actions.length;

    renderActionCollection(
      document.getElementById("overview-priority-list"),
      state.summary.today_priority,
      "今天还没有待完成行动",
      "添加目标岗位或行动后，最需要处理的事项会出现在这里。"
    );
    renderActionCollection(
      document.getElementById("overview-history-list"),
      state.actions.filter(item => item.status === "completed").slice(0, 5),
      "还没有已完成的行动",
      "达到完成标准后，行动记录会出现在这里。"
    );

    const stageOverview = document.getElementById("stage-overview");
    stageOverview.replaceChildren();
    Object.entries(stageLabels).forEach(([stage, label]) => {
      const cell = document.createElement("div");
      cell.className = "stage-cell";
      cell.append(textElement("strong", state.summary.stage_counts[stage] || 0), textElement("span", label));
      stageOverview.appendChild(cell);
    });

    const recent = document.getElementById("recent-track-list");
    recent.replaceChildren();
    if (!state.summary.recent_tracks.length) {
      recent.appendChild(emptyState("01", "还没有目标岗位", "从已核验职位或完整 JD 建立第一条岗位进度。"));
    } else {
      state.summary.recent_tracks.forEach(track => {
        const row = document.createElement("div");
        row.className = "compact-track";
        const open = document.createElement("button");
        open.type = "button";
        open.dataset.openTrackId = track.track_id;
        open.textContent = `${track.company_name} · ${track.title}`;
        const stage = textElement("span", stageLabels[track.stage] || track.stage, "stage-pill");
        stage.dataset.stage = track.stage;
        row.append(open, stage);
        recent.appendChild(row);
      });
    }
  };

  const renderTrackOptions = () => {
    const targets = [document.getElementById("action-track"), document.getElementById("action-track-filter")];
    targets.forEach((select, index) => {
      const current = select.value;
      select.replaceChildren(new Option(index === 0 ? "通用行动，不关联岗位" : "全部岗位", ""));
      state.tracks.forEach(({track}) => select.appendChild(new Option(`${track.company_name} · ${track.title}`, track.track_id)));
      if ([...select.options].some(option => option.value === current)) select.value = current;
    });
  };

  const filteredTracks = () => {
    const stage = document.getElementById("track-stage-filter").value;
    return stage ? state.tracks.filter(item => item.track.stage === stage) : state.tracks;
  };

  const renderTracks = () => {
    renderTrackOptions();
    const list = document.getElementById("track-list");
    const items = filteredTracks();
    list.replaceChildren();
    if (!items.length) {
      list.appendChild(emptyState("01", "没有符合条件的岗位", "添加目标岗位或调整阶段筛选。"));
    } else {
      items.forEach(({track, source_state: sourceState}) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = `track-list-item${track.track_id === state.selectedTrackId ? " active" : ""}`;
        item.dataset.trackId = track.track_id;
        const sourceLabel = sourceState.status === "updated" ? "职位已有新版本" : track.source_kind === "reviewed_job" ? "官方职位" : "用户 JD";
        item.append(textElement("h3", `${track.company_name} · ${track.title}`), textElement("p", `${stageLabels[track.stage]} · ${sourceLabel}`));
        list.appendChild(item);
      });
    }
    if (state.selectedTrackId && trackById(state.selectedTrackId)) renderTrackDetail(state.selectedTrackId);
  };

  const renderTrackDetail = trackId => {
    const item = state.tracks.find(value => value.track.track_id === trackId);
    if (!item) return;
    const {track, source_state: sourceState} = item;
    const detail = document.getElementById("track-detail");
    detail.replaceChildren();

    const header = document.createElement("header");
    header.className = "track-detail-header";
    const heading = document.createElement("div");
    heading.append(textElement("h2", track.title), textElement("p", track.company_name));
    const sourcePill = textElement("span", track.source_kind === "reviewed_job" ? "官方已审核职位" : "用户提供 JD", "source-pill");
    header.append(heading, sourcePill);

    const meta = document.createElement("div");
    meta.className = "detail-meta";
    if (track.locations.length) meta.appendChild(textElement("span", track.locations.join(" / ")));
    meta.appendChild(textElement("span", track.deadline ? `报名截止 ${track.deadline}` : "未设置报名截止时间"));
    if (sourceState.status === "updated") meta.appendChild(textElement("span", "官方职位已有新版本，请复核"));
    if (sourceState.last_verified_at) meta.appendChild(textElement("span", `最近核验 ${formatDate(sourceState.last_verified_at)}`));

    const controls = document.createElement("section");
    controls.className = "track-detail-section";
    controls.appendChild(textElement("h3", "更新求职阶段"));
    const controlGrid = document.createElement("div");
    controlGrid.className = "track-controls";
    const stageLabel = document.createElement("label");
    stageLabel.appendChild(textElement("span", "当前阶段"));
    const stage = document.createElement("select");
    stage.id = "detail-track-stage";
    Object.entries(stageLabels).forEach(([value, label]) => stage.appendChild(new Option(label, value)));
    stage.value = track.stage;
    stageLabel.appendChild(stage);
    const deadlineLabel = document.createElement("label");
    deadlineLabel.appendChild(textElement("span", "报名截止时间"));
    const deadline = document.createElement("input");
    deadline.id = "detail-track-deadline";
    deadline.type = "date";
    deadline.value = track.deadline || "";
    deadlineLabel.appendChild(deadline);
    const save = button("保存变化", "save-track-detail", track.track_id, "primary");
    controlGrid.append(stageLabel, deadlineLabel, save);
    controls.appendChild(controlGrid);

    const closeFields = document.createElement("div");
    closeFields.id = "track-close-fields";
    closeFields.className = "form-row";
    closeFields.hidden = track.stage !== "closed";
    const reasonLabel = document.createElement("label");
    reasonLabel.textContent = "结束原因";
    const reason = document.createElement("select");
    reason.id = "detail-closed-reason";
    reason.appendChild(new Option("请选择", ""));
    Object.entries(closedReasonLabels).forEach(([value, label]) => reason.appendChild(new Option(label, value)));
    reason.value = track.closed_reason || "";
    reasonLabel.appendChild(reason);
    const noteLabel = document.createElement("label");
    noteLabel.textContent = "补充说明（选择其他时填写）";
    const note = document.createElement("input");
    note.id = "detail-closed-note";
    note.maxLength = 500;
    note.value = track.closed_reason_note || "";
    noteLabel.appendChild(note);
    closeFields.append(reasonLabel, noteLabel);
    controls.appendChild(closeFields);

    const source = document.createElement("section");
    source.className = "track-detail-section";
    source.appendChild(textElement("h3", "岗位来源"));
    const sourceText = track.source_kind === "reviewed_job"
      ? `创建时使用职位版本 ${track.job_version_id}`
      : "完整 JD 由用户提供，仅保存在本地求职工作区。";
    source.appendChild(textElement("p", sourceText, "hint"));
    if (track.source_url) {
      const link = document.createElement("a");
      link.href = track.source_url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = "打开来源链接";
      source.appendChild(link);
    }

    const requirements = document.createElement("section");
    requirements.className = "track-detail-section";
    requirements.appendChild(textElement("h3", `JD 要求 · ${track.requirement_snapshot.length} 项`));
    if (track.requirement_snapshot.length) {
      const list = document.createElement("ol");
      list.className = "requirement-snapshot";
      track.requirement_snapshot.forEach((requirement, index) => {
        const row = document.createElement("li");
        row.append(textElement("span", String(index + 1).padStart(2, "0")), textElement("div", requirement.text));
        list.appendChild(row);
      });
      requirements.appendChild(list);
    } else {
      requirements.appendChild(textElement("p", "当前没有结构化 JD 要求。仍可以围绕完整 JD 创建行动。", "hint"));
    }

    const related = document.createElement("section");
    related.className = "track-detail-section";
    const relatedHeading = document.createElement("div");
    relatedHeading.className = "workspace-card-heading";
    relatedHeading.append(textElement("h3", "关联行动"), button("添加行动", "add-track-action", track.track_id, "mini-button"));
    related.appendChild(relatedHeading);
    const relatedList = document.createElement("div");
    relatedList.className = "workspace-list";
    renderActionCollection(relatedList, state.actions.filter(action => action.track_id === track.track_id), "还没有关联行动", "从分析结果确认建议，或手动添加下一步。" );
    related.appendChild(relatedList);

    const danger = document.createElement("section");
    danger.className = "track-detail-section";
    danger.append(button("删除目标岗位", "delete-track", track.track_id, "mini-button danger"));
    detail.append(header, meta, controls, source, requirements, related, danger);

    stage.addEventListener("change", () => {
      closeFields.hidden = stage.value !== "closed";
    });
  };

  const filteredActions = () => {
    const status = document.getElementById("action-status-filter").value;
    const trackId = document.getElementById("action-track-filter").value;
    return state.actions.filter(item => (!status || item.status === status) && (!trackId || item.track_id === trackId));
  };

  const renderActions = () => {
    renderActionCollection(
      document.getElementById("action-list"),
      filteredActions(),
      "没有符合条件的行动",
      "调整筛选条件，或添加一个有明确完成标准的行动。"
    );
  };

  const loadWorkspaceData = async ({quiet = false} = {}) => {
    if (!quiet) setMessage("正在读取本地求职进度…");
    try {
      const offset = -new Date().getTimezoneOffset();
      const [tracks, actions, summary] = await Promise.all([
        workspaceFetch("/tracks?limit=200"),
        workspaceFetch("/actions?limit=500"),
        workspaceFetch(`/summary?timezone_offset_minutes=${offset}`)
      ]);
      state.tracks = tracks.items;
      state.actions = actions.items;
      state.summary = summary;
      if (state.selectedTrackId && !trackById(state.selectedTrackId)) state.selectedTrackId = null;
      renderSummary();
      renderTracks();
      renderActions();
      if (!quiet) setMessage();
    } catch (error) {
      sessionState.textContent = "本地工作区连接失败";
      sessionState.className = "session-state error";
      setMessage(`${error.message || "求职工作区暂时不可用"}。六项分析工具仍可继续使用。`, "error");
    }
  };

  const switchWorkspacePage = page => {
    workspaceView.hidden = false;
    skillView.hidden = true;
    document.querySelectorAll(".workspace-page").forEach(section => { section.hidden = section.dataset.page !== page; });
    workspaceNav.querySelectorAll("button").forEach(item => item.classList.toggle("active", item.dataset.workspaceView === page));
    skillNav.querySelectorAll("button").forEach(item => item.classList.remove("active"));
    document.getElementById("workspace-view-title").textContent = viewCopy[page][0];
    document.getElementById("workspace-view-description").textContent = viewCopy[page][1];
    if (page === "actions") renderActions();
    if (page === "tracks") renderTracks();
    if (page === "materials") window.MakoMaterials?.load();
  };

  const switchToSkill = () => {
    workspaceView.hidden = true;
    skillView.hidden = false;
    workspaceNav.querySelectorAll("button").forEach(item => item.classList.remove("active"));
  };

  const loadReviewedJobs = async () => {
    const select = document.getElementById("track-reviewed-job");
    const status = document.getElementById("track-reviewed-status");
    select.disabled = true;
    status.textContent = "正在读取系统内已审核职位…";
    try {
      const response = await fetch("/v2/workspace/jobs?max_age_days=90&limit=50");
      const payload = await readPayload(response);
      if (!response.ok) throw new Error(responseMessage(payload));
      state.reviewedJobs.clear();
      select.replaceChildren(new Option("请选择一个目标岗位", ""));
      payload.items.forEach(job => {
        const key = `${job.job_id}|${job.job_version_id}`;
        state.reviewedJobs.set(key, job);
        const locations = job.locations.length ? ` · ${job.locations.join(" / ")}` : "";
        select.appendChild(new Option(`${job.company_name} · ${job.title}${locations}`, key));
      });
      status.textContent = payload.count ? `找到 ${payload.count} 个近期已审核职位。` : "当前没有符合条件的已审核职位，可以改为自行提供 JD。";
    } catch (error) {
      select.replaceChildren(new Option("职位列表暂时不可用", ""));
      status.textContent = `${error.message || "职位列表读取失败"}，可以改为自行提供 JD。`;
    } finally {
      select.disabled = false;
    }
  };

  const openTrackDialog = () => {
    document.getElementById("track-form").reset();
    document.getElementById("track-reviewed-fields").hidden = false;
    document.getElementById("track-manual-fields").hidden = true;
    document.getElementById("track-form-status").textContent = "";
    trackDialog.showModal();
    if (!state.reviewedJobs.size) loadReviewedJobs();
  };

  const openActionDialog = (action = null, trackId = null) => {
    state.editingActionId = action?.action_id || null;
    document.getElementById("action-form").reset();
    document.getElementById("action-id").value = action?.action_id || "";
    document.getElementById("action-dialog-title").textContent = action?.status === "suggested" ? "检查行动建议" : action ? "编辑行动" : "添加行动";
    const trackSelect = document.getElementById("action-track");
    renderTrackOptions();
    trackSelect.value = action?.track_id || trackId || "";
    trackSelect.disabled = Boolean(action);
    document.getElementById("action-title").value = action?.title || "";
    document.getElementById("action-criteria").value = action?.completion_criteria || "";
    document.getElementById("action-priority").value = action?.priority || "medium";
    document.getElementById("action-due").value = formatDateTimeLocal(action?.due_at);
    const source = document.getElementById("action-source-preview");
    source.hidden = !action?.source_ref;
    source.textContent = action?.source_ref ? `建议依据：${action.source_ref.label}${action.source_ref.excerpt ? ` · ${action.source_ref.excerpt}` : ""}` : "";
    document.getElementById("action-form-status").textContent = "";
    document.getElementById("save-action").textContent = action?.status === "suggested" ? "确认并加入计划" : "保存行动";
    actionDialog.showModal();
  };

  const saveTrack = async () => {
    const status = document.getElementById("track-form-status");
    const sourceKind = document.querySelector('input[name="track-source"]:checked').value;
    let payload;
    if (sourceKind === "reviewed_job") {
      const job = state.reviewedJobs.get(document.getElementById("track-reviewed-job").value);
      if (!job) throw new Error("请选择一个已审核职位");
      payload = {
        source_kind: sourceKind,
        job_id: job.job_id,
        job_version_id: job.job_version_id,
        job_max_age_days: 90,
        deadline: document.getElementById("track-deadline").value || null
      };
    } else {
      const company = document.getElementById("track-company").value.trim();
      const title = document.getElementById("track-title").value.trim();
      const jdText = document.getElementById("track-jd").value.trim();
      if (!company || !title || !jdText) throw new Error("请填写企业、岗位和完整 JD");
      const sourceUrl = document.getElementById("track-source-url").value.trim();
      if (sourceUrl && !sourceUrl.startsWith("https://")) throw new Error("职位链接需要使用完整的 HTTPS 地址");
      payload = {
        source_kind: sourceKind,
        company_name: company,
        title,
        locations: document.getElementById("track-locations").value.split(/[,，、;；]+/).map(value => value.trim()).filter(Boolean),
        jd_text: jdText,
        source_url: sourceUrl || null,
        deadline: document.getElementById("track-deadline").value || null
      };
    }
    status.textContent = "正在保存目标岗位…";
    const requestBody = JSON.stringify(payload);
    const idempotencyKey = state.retryTrackCreate?.body === requestBody
      ? state.retryTrackCreate.key
      : `track_${crypto.randomUUID().replaceAll("-", "")}`;
    state.retryTrackCreate = {body: requestBody, key: idempotencyKey};
    const created = await workspaceFetch("/tracks", {
      method: "POST",
      headers: {"Content-Type": "application/json", "Idempotency-Key": idempotencyKey},
      body: requestBody
    });
    state.retryTrackCreate = null;
    state.selectedTrackId = created.track.track_id;
    trackDialog.close();
    await loadWorkspaceData({quiet: true});
    switchWorkspacePage("tracks");
    setMessage("目标岗位已加入工作区。", "success");
  };

  const saveAction = async () => {
    const title = document.getElementById("action-title").value.trim();
    const criteria = document.getElementById("action-criteria").value.trim();
    if (!title || !criteria) throw new Error("请填写行动内容和完成标准");
    const dueValue = document.getElementById("action-due").value;
    const dueAt = dueValue ? new Date(dueValue).toISOString() : null;
    const current = state.editingActionId ? actionById(state.editingActionId) : null;
    const status = document.getElementById("action-form-status");
    status.textContent = "正在保存行动…";
    if (current) {
      await workspaceFetch(`/actions/${encodeURIComponent(current.action_id)}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          revision: current.revision,
          title,
          completion_criteria: criteria,
          priority: document.getElementById("action-priority").value,
          due_at: dueAt,
          ...(current.status === "suggested" ? {status: "todo"} : {})
        })
      });
    } else {
      const payload = {
        track_id: document.getElementById("action-track").value || null,
        title,
        completion_criteria: criteria,
        priority: document.getElementById("action-priority").value,
        due_at: dueAt
      };
      const requestBody = JSON.stringify(payload);
      const idempotencyKey = state.retryActionCreate?.body === requestBody
        ? state.retryActionCreate.key
        : `action_${crypto.randomUUID().replaceAll("-", "")}`;
      state.retryActionCreate = {body: requestBody, key: idempotencyKey};
      await workspaceFetch("/actions", {
        method: "POST",
        headers: {"Content-Type": "application/json", "Idempotency-Key": idempotencyKey},
        body: requestBody
      });
      state.retryActionCreate = null;
    }
    actionDialog.close();
    await loadWorkspaceData({quiet: true});
    setMessage(current?.status === "suggested" ? "建议已确认并加入行动计划。" : "行动已保存。", "success");
  };

  const patchActionStatus = async (actionId, status) => {
    const action = actionById(actionId);
    if (!action) return;
    await workspaceFetch(`/actions/${encodeURIComponent(actionId)}`, {
      method: "PATCH",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({revision: action.revision, status})
    });
    await loadWorkspaceData({quiet: true});
  };

  const deleteAction = async actionId => {
    const action = actionById(actionId);
    if (!action || !window.confirm(`确定删除“${action.title}”吗？此操作无法撤销。`)) return;
    await workspaceFetch(`/actions/${encodeURIComponent(actionId)}?revision=${action.revision}`, {method: "DELETE"});
    await loadWorkspaceData({quiet: true});
    setMessage("行动已删除。", "success");
  };

  const saveTrackDetail = async trackId => {
    const track = trackById(trackId);
    if (!track) return;
    const stage = document.getElementById("detail-track-stage").value;
    const payload = {
      revision: track.revision,
      stage,
      deadline: document.getElementById("detail-track-deadline").value || null
    };
    if (stage === "closed") {
      const reason = document.getElementById("detail-closed-reason").value;
      if (!reason) throw new Error("请选择岗位结束原因");
      payload.closed_reason = reason;
      if (reason === "other") {
        const note = document.getElementById("detail-closed-note").value.trim();
        if (!note) throw new Error("选择其他原因时，请填写补充说明");
        payload.closed_reason_note = note;
      }
    }
    await workspaceFetch(`/tracks/${encodeURIComponent(trackId)}`, {
      method: "PATCH",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    await loadWorkspaceData({quiet: true});
    setMessage("岗位阶段已更新。", "success");
  };

  const deleteTrack = async trackId => {
    const track = trackById(trackId);
    if (!track) return;
    const impact = await workspaceFetch(`/tracks/${encodeURIComponent(trackId)}/deletion-impact`);
    const detail = impact.actions ? `，并同时删除 ${impact.actions} 项关联行动` : "";
    if (!window.confirm(`确定永久删除“${track.company_name} · ${track.title}”${detail}吗？此操作无法撤销。`)) return;
    await workspaceFetch(`/tracks/${encodeURIComponent(trackId)}?revision=${track.revision}&cascade_actions=true`, {method: "DELETE"});
    state.selectedTrackId = null;
    await loadWorkspaceData({quiet: true});
    setMessage("目标岗位及其关联行动已删除。", "success");
  };

  const handleActionOperation = async (operation, id) => {
    try {
      if (operation === "edit") openActionDialog(actionById(id));
      else if (operation === "complete") await patchActionStatus(id, "completed");
      else if (operation === "reopen") await patchActionStatus(id, "todo");
      else if (operation === "cancel") await patchActionStatus(id, "cancelled");
      else if (operation === "delete") await deleteAction(id);
    } catch (error) {
      setMessage(`${error.message || "行动更新失败"}，页面将重新读取最新状态。`, "error");
      await loadWorkspaceData({quiet: true});
    }
  };

  const handleWorkspaceClick = async event => {
    const openTrack = event.target.closest("[data-open-track]");
    if (openTrack) return openTrackDialog();
    const openAction = event.target.closest("[data-open-action]");
    if (openAction) return openActionDialog();
    const recentTrack = event.target.closest("[data-open-track-id]");
    if (recentTrack) {
      state.selectedTrackId = recentTrack.dataset.openTrackId;
      switchWorkspacePage("tracks");
      renderTracks();
      return;
    }
    const trackItem = event.target.closest("[data-track-id]");
    if (trackItem) {
      state.selectedTrackId = trackItem.dataset.trackId;
      renderTracks();
      return;
    }
    const operationButton = event.target.closest("[data-operation]");
    if (!operationButton) return;
    const {operation, id} = operationButton.dataset;
    try {
      if (operation === "add-track-action") openActionDialog(null, id);
      else if (operation === "save-track-detail") await saveTrackDetail(id);
      else if (operation === "delete-track") await deleteTrack(id);
      else await handleActionOperation(operation, id);
    } catch (error) {
      setMessage(error.message || "操作未完成", "error");
    }
  };

  workspaceNav.addEventListener("click", event => {
    const target = event.target.closest("button[data-workspace-view]");
    if (target) switchWorkspacePage(target.dataset.workspaceView);
  });
  skillNav.addEventListener("click", event => {
    if (event.target.closest("button[data-skill]")) switchToSkill();
  });
  workspaceView.addEventListener("click", handleWorkspaceClick);
  document.getElementById("track-stage-filter").addEventListener("change", renderTracks);
  document.getElementById("action-status-filter").addEventListener("change", renderActions);
  document.getElementById("action-track-filter").addEventListener("change", renderActions);

  document.querySelectorAll('input[name="track-source"]').forEach(input => input.addEventListener("change", () => {
    const manual = input.value === "manual_jd" && input.checked;
    if (!input.checked) return;
    document.getElementById("track-reviewed-fields").hidden = manual;
    document.getElementById("track-manual-fields").hidden = !manual;
  }));

  document.getElementById("track-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (event.submitter?.value === "cancel") return trackDialog.close();
    const save = document.getElementById("save-track");
    save.disabled = true;
    try {
      await saveTrack();
    } catch (error) {
      document.getElementById("track-form-status").textContent = error.message || "目标岗位保存失败";
      document.getElementById("track-form-status").className = "status-message error";
    } finally {
      save.disabled = false;
    }
  });

  document.getElementById("action-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (event.submitter?.value === "cancel") return actionDialog.close();
    const save = document.getElementById("save-action");
    save.disabled = true;
    try {
      await saveAction();
    } catch (error) {
      document.getElementById("action-form-status").textContent = error.message || "行动保存失败";
      document.getElementById("action-form-status").className = "status-message error";
    } finally {
      save.disabled = false;
    }
  });

  document.getElementById("export-workspace").addEventListener("click", async () => {
    try {
      const payload = await workspaceFetch("/export");
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json;charset=utf-8"});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `mako-career-workspace-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage("求职工作区数据已导出。", "success");
    } catch (error) {
      setMessage(error.message || "数据导出失败", "error");
    }
  });

  document.getElementById("clear-workspace").addEventListener("click", async () => {
    try {
      const impact = await workspaceFetch("/deletion-impact");
      if (!impact.tracks && !impact.actions) {
        setMessage("当前工作区没有需要清除的数据。", "success");
        return;
      }
      const confirmed = window.confirm(
        `将永久删除 ${impact.tracks} 个目标岗位和 ${impact.actions} 项行动。此操作无法撤销，是否继续？`
      );
      if (!confirmed) return;
      await workspaceFetch("?confirmation=DELETE_LOCAL_WORKSPACE", {method: "DELETE"});
      state.selectedTrackId = null;
      await loadWorkspaceData({quiet: true});
      setMessage("本地求职工作区已清空。", "success");
    } catch (error) {
      setMessage(error.message || "工作区清除失败", "error");
    }
  });

  switchWorkspacePage("overview");
  loadWorkspaceData();
})();
