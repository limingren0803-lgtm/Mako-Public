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
    overview: ["准备好，向下一站前进。", ""],
    tasks: ["求职任务", "围绕一个真实目标持续分析，岗位、材料与下一步都保留在同一条线上。"],
    tracks: ["目标岗位", "从关注到面试，保留岗位依据，把准备接到具体机会。"],
    actions: ["行动日程", "每件事都有完成标准，由你决定何时开始、完成或重新打开。"],
    materials: ["个人材料库", "整理简历、项目与经历，让每次分析都有可核对的依据。"]
  };

  const state = {
    sessionReady: false,
    tracks: [],
    actions: [],
    summary: null,
    reviewedJobs: new Map(),
    reviewedJobItems: [],
    selectedTrackId: null,
    editingActionId: null,
    retryTrackCreate: null,
    retryActionCreate: null,
    calendarMonth: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
    calendarDay: ""
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
      const error = new Error(payload?.detail === "personal material selection requires reconfirmation" ? "任务材料已变化，请核对后重新确认。" : "数据已在其他窗口发生变化，已重新加载最新内容。请确认后重试。");
      error.status = 409; error.detail = payload?.detail;
      throw error;
    }
    if (!response.ok) { const error = new Error(responseMessage(payload)); error.status = response.status; throw error; }
    return payload;
  };

  window.MakoWorkspace = Object.freeze({
    fetch: workspaceFetch,
    ensureSession: startSession,
    refresh: () => loadWorkspaceData({quiet: true}),
    showPage: page => switchWorkspacePage(page),
    newAction: () => { switchWorkspacePage("actions"); openActionDialog(); },
    showSkill: () => switchToSkill(),
    position: () => ({view: skillView.hidden ? document.querySelector(".workspace-page:not([hidden])").dataset.page : "skill", date: state.calendarDay || formatDateTimeLocal(state.calendarMonth).slice(0, 10), actionView: document.getElementById("action-list").hidden ? "calendar" : "list"}),
    restoreCalendar: (date, view) => { openCalendarDay(date); document.querySelector(`[data-action-view="${view}"]`).click(); },
    showSuggestedActions: async () => {
      await loadWorkspaceData({quiet: true});
      document.getElementById("action-status-filter").value = "suggested";
      document.getElementById("action-track-filter").value = "";
      document.querySelector('[data-action-view="list"]').click();
      switchWorkspacePage("actions");
    }
  });

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

    renderDashboardSchedule();
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
    const headerActions = document.createElement("div");
    headerActions.className = "track-header-actions";
    headerActions.append(sourcePill, button("以此岗位开始任务", "start-track-task", track.track_id, "secondary"));
    header.append(heading, headerActions);

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

  const datedEntries = (actions, trackFilter = "") => {
    const byDay = new Map();
    const add = (date, entry) => {
      if (!byDay.has(date)) byDay.set(date, []);
      byDay.get(date).push(entry);
    };
    actions.forEach(action => {
      const local = formatDateTimeLocal(action.due_at);
      if (local) add(local.slice(0, 10), {action, title: action.title, label: `${local.slice(11)} · ${statusLabels[action.status]}`, time: local});
    });
    state.tracks.forEach(({track}) => {
      if (track.deadline && track.stage !== "closed" && (!trackFilter || track.track_id === trackFilter)) {
        add(track.deadline, {track, title: `${track.company_name} · ${track.title}`, label: "报名截止", time: ""});
      }
    });
    byDay.forEach(entries => entries.sort((a, b) => a.time.localeCompare(b.time)));
    return byDay;
  };

  const openCalendarDay = key => {
    const [year, month] = key.split("-").map(Number);
    state.calendarMonth = new Date(year, month - 1, 1);
    state.calendarDay = key;
    document.getElementById("action-status-filter").value = "";
    document.getElementById("action-track-filter").value = "";
    document.querySelector('[data-action-view="calendar"]').click();
    switchWorkspacePage("actions");
  };

  const renderDashboardSchedule = () => {
    const entries = datedEntries(state.actions.filter(action => ["todo", "suggested"].includes(action.status)));
    const week = document.getElementById("dashboard-week");
    const upcoming = document.getElementById("dashboard-upcoming");
    week.replaceChildren(); upcoming.replaceChildren();
    const now = new Date();
    const items = [];
    for (let offset = 0; offset < 7; offset++) {
      const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset);
      const key = formatDateTimeLocal(day).slice(0, 10);
      const dayItems = entries.get(key) || [];
      const control = textElement("button", "", "dashboard-day");
      control.type = "button"; control.dataset.calendarOpen = key;
      control.setAttribute("aria-label", `${key}，${dayItems.length} 项截止事项`);
      if (!offset) control.setAttribute("aria-current", "date");
      control.append(textElement("small", !offset ? "今天" : new Intl.DateTimeFormat("zh-CN", {weekday: "short"}).format(day)), textElement("b", String(day.getDate())), textElement("span", dayItems.length ? `${dayItems.length}项` : "—"));
      week.append(control);
      dayItems.forEach(entry => items.push({...entry, date: key}));
    }
    items.slice(0, 3).forEach(item => {
      const row = textElement("button", "", "dashboard-deadline");
      row.type = "button"; row.dataset.calendarOpen = item.date;
      const date = item.date.split("-");
      row.append(textElement("span", `${Number(date[1])}/${Number(date[2])}`, "dashboard-deadline-date"), textElement("b", item.title), textElement("small", item.label));
      upcoming.append(row);
    });
    if (!items.length) upcoming.append(textElement("p", "未来七天暂无截止事项。可以先安排一项准备行动。", "hint"));
  };

  const renderCalendar = () => {
    const today = formatDateTimeLocal(new Date()).slice(0, 10);
    if (!state.calendarDay) state.calendarDay = today;
    const year = state.calendarMonth.getFullYear();
    const month = state.calendarMonth.getMonth();
    const monthKey = `${year}-${String(month + 1).padStart(2, "0")}`;
    const actions = filteredActions().filter(action => action.status !== "cancelled");
    const byDay = datedEntries(actions, document.getElementById("action-track-filter").value);
    document.getElementById("calendar-month").textContent = `${year} 年 ${month + 1} 月`;
    window.MakoContinuity?.schedule();
    const grid = document.getElementById("calendar-grid");
    const focusedDay = grid.contains(document.activeElement) ? document.activeElement.dataset.calendarDay : null;
    grid.replaceChildren();
    const offset = (state.calendarMonth.getDay() + 6) % 7;
    const days = new Date(year, month + 1, 0).getDate();
    const cells = Math.ceil((offset + days) / 7) * 7;
    for (let index = 0; index < cells; index++) {
      const day = index - offset + 1;
      if (day < 1 || day > days) {
        grid.appendChild(textElement("div", "", "calendar-blank"));
        continue;
      }
      const key = `${monthKey}-${String(day).padStart(2, "0")}`;
      const entries = byDay.get(key) || [];
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "calendar-day";
      cell.dataset.calendarDay = key;
      cell.setAttribute("aria-pressed", String(key === state.calendarDay));
      cell.setAttribute("aria-label", `${month + 1} 月 ${day} 日${key === today ? "，今天" : ""}，${entries.length} 项${entries.length ? `：${entries.map(entry => `${entry.label} ${entry.title}`).join("；")}` : ""}`);
      if (key === today) cell.setAttribute("aria-current", "date");
      cell.appendChild(textElement("span", String(day), "calendar-date"));
      entries.slice(0, 2).forEach(entry => {
        const preview = textElement("span", "", `calendar-event${entry.track ? " deadline-event" : ""}`);
        preview.append(textElement("span", entry.title, "calendar-event-title"), textElement("small", entry.label));
        if (entry.action) preview.dataset.status = entry.action.status;
        cell.appendChild(preview);
      });
      if (entries.length) cell.appendChild(textElement("span", `${entries.length}项${entries.some(entry => entry.track) ? "·截止" : ""}`, "calendar-count"));
      grid.appendChild(cell);
    }
    if (focusedDay) grid.querySelector(`[data-calendar-day="${focusedDay}"]`)?.focus({preventScroll: true});
    const [, selectedMonth, selectedDay] = state.calendarDay.split("-");
    document.getElementById("calendar-day-title").textContent = `${Number(selectedMonth)} 月 ${Number(selectedDay)} 日${state.calendarDay === today ? " · 今天" : ""}`;
    const agenda = document.getElementById("calendar-day-items");
    agenda.replaceChildren();
    const entries = byDay.get(state.calendarDay) || [];
    if (!entries.length) agenda.appendChild(textElement("p", "这天没有符合筛选条件的截止事项，可以添加一项准备行动。", "hint"));
    entries.forEach(entry => {
      if (entry.action) {
        const row = actionCard(entry.action);
        row.prepend(textElement("span", entry.label, "calendar-agenda-time"));
        agenda.appendChild(row);
      } else {
        const row = textElement("article", "", "calendar-deadline-row");
        const open = textElement("button", "查看岗位", "secondary");
        open.type = "button";
        open.dataset.openTrackId = entry.track.track_id;
        const copy = textElement("div", "");
        copy.append(textElement("p", "报名截止 · 以岗位来源为准", "eyebrow"), textElement("h4", entry.title));
        row.append(copy, open);
        agenda.appendChild(row);
      }
    });
    const undated = actions.filter(action => !formatDateTimeLocal(action.due_at));
    document.getElementById("calendar-undated-title").textContent = `未设截止时间 · ${undated.length} 项`;
    renderActionCollection(document.getElementById("calendar-undated-items"), undated, "没有未定日期的行动", "新行动可以在确定时间后加入日历。");
  };

  const renderActions = () => {
    renderActionCollection(
      document.getElementById("action-list"),
      filteredActions(),
      "没有符合条件的行动",
      "调整筛选条件，或添加一个有明确完成标准的行动。"
    );
    renderCalendar();
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
    if (window.MakoApp && !window.MakoApp.canSwitch()) return;
    workspaceView.hidden = false;
    skillView.hidden = true;
    document.querySelectorAll(".workspace-page").forEach(section => { section.hidden = section.dataset.page !== page; });
    workspaceNav.querySelectorAll("button").forEach(item => item.classList.toggle("active", item.dataset.workspaceView === page));
    skillNav.querySelectorAll("button").forEach(item => item.classList.remove("active"));
    updateNavigation();
    window.MakoContinuity?.navigate();
    document.getElementById("workspace-view-title").textContent = viewCopy[page][0];
    document.getElementById("workspace-view-description").textContent = viewCopy[page][1];
    document.getElementById("workspace-view-description").hidden = !viewCopy[page][1];
    if (page === "overview") window.MakoTasks?.loadOverview();
    if (page === "actions") renderActions();
    if (page === "tracks") renderTracks();
    if (page === "materials") window.MakoMaterials?.load();
    if (page === "tasks") return window.MakoTasks?.load();
  };

  const switchToSkill = () => {
    workspaceView.hidden = true;
    skillView.hidden = false;
    window.MakoToolPage?.activate();
    workspaceNav.querySelectorAll("button").forEach(item => item.classList.remove("active"));
    updateNavigation();
    window.MakoContinuity?.navigate();
  };

  const updateNavigation = () => {
    document.querySelectorAll(".sidebar .nav-item").forEach(item => {
      if (item.classList.contains("active")) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
  };

  const reviewedJobControls = () => ({
    industry: document.getElementById("track-reviewed-industry"),
    companyType: document.getElementById("track-reviewed-company-type"),
    company: document.getElementById("track-reviewed-company"),
    job: document.getElementById("track-reviewed-job")
  });

  const replaceReviewedOptions = (select, placeholder, values = []) => {
    select.replaceChildren(new Option(placeholder, ""), ...values.map(value => new Option(value, value)));
    select.disabled = !values.length;
  };

  const uniqueReviewedValues = (items, field) => [...new Set(items.map(item => item[field]).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, "zh-CN"));

  const resetReviewedJobCascade = () => {
    const controls = reviewedJobControls();
    replaceReviewedOptions(controls.industry, "请选择行业", uniqueReviewedValues(state.reviewedJobItems, "industry"));
    replaceReviewedOptions(controls.companyType, "请先选择行业");
    replaceReviewedOptions(controls.company, "请先选择企业类型");
    replaceReviewedOptions(controls.job, "请先选择企业");
    document.getElementById("track-reviewed-status").textContent = state.reviewedJobItems.length
      ? `共 ${state.reviewedJobItems.length} 个近期已审核职位，请从行业开始筛选。`
      : "当前没有符合条件的已审核职位，可以改为自行提供 JD。";
  };

  const updateReviewedCompanyTypes = () => {
    const controls = reviewedJobControls();
    const items = state.reviewedJobItems.filter(item => item.industry === controls.industry.value);
    replaceReviewedOptions(controls.companyType, controls.industry.value ? "请选择企业类型" : "请先选择行业", uniqueReviewedValues(items, "company_type"));
    replaceReviewedOptions(controls.company, "请先选择企业类型");
    replaceReviewedOptions(controls.job, "请先选择企业");
  };

  const updateReviewedCompanies = () => {
    const controls = reviewedJobControls();
    const items = state.reviewedJobItems.filter(item => item.industry === controls.industry.value && item.company_type === controls.companyType.value);
    replaceReviewedOptions(controls.company, controls.companyType.value ? "请选择企业" : "请先选择企业类型", uniqueReviewedValues(items, "company_name"));
    replaceReviewedOptions(controls.job, "请先选择企业");
  };

  const updateReviewedJobOptions = () => {
    const controls = reviewedJobControls();
    const items = state.reviewedJobItems.filter(item => item.industry === controls.industry.value && item.company_type === controls.companyType.value && item.company_name === controls.company.value);
    controls.job.replaceChildren(new Option(controls.company.value ? "请选择具体岗位" : "请先选择企业", ""), ...items.map(item => {
      const locations = item.locations.length ? ` · ${item.locations.join(" / ")}` : "";
      return new Option(`${item.title}${locations}`, item.key);
    }));
    controls.job.disabled = !items.length;
    document.getElementById("track-reviewed-status").textContent = items.length
      ? `${controls.company.value}共有 ${items.length} 个近期已审核职位。`
      : "该范围内没有符合条件的已审核职位。";
  };

  const loadReviewedJobs = async () => {
    const controls = reviewedJobControls();
    const status = document.getElementById("track-reviewed-status");
    Object.values(controls).forEach(select => { select.disabled = true; });
    status.textContent = "正在读取系统内已审核职位…";
    try {
      const response = await fetch("/v2/workspace/jobs?max_age_days=90&limit=50");
      const payload = await readPayload(response);
      if (!response.ok) throw new Error(responseMessage(payload));
      state.reviewedJobs.clear();
      state.reviewedJobItems = payload.items.map(job => {
        const key = `${job.job_id}|${job.job_version_id}`;
        state.reviewedJobs.set(key, job);
        return {...job, key};
      });
      resetReviewedJobCascade();
    } catch (error) {
      state.reviewedJobItems = [];
      replaceReviewedOptions(controls.industry, "职位列表暂时不可用");
      replaceReviewedOptions(controls.companyType, "请先选择行业");
      replaceReviewedOptions(controls.company, "请先选择企业类型");
      replaceReviewedOptions(controls.job, "请先选择企业");
      status.textContent = `${error.message || "职位列表读取失败"}，可以改为自行提供 JD。`;
    }
  };

  const openTrackDialog = () => {
    document.getElementById("track-form").reset();
    document.getElementById("track-reviewed-fields").hidden = false;
    document.getElementById("track-manual-fields").hidden = true;
    document.getElementById("track-form-status").textContent = "";
    trackDialog.showModal();
    if (!state.reviewedJobs.size) loadReviewedJobs();
    else resetReviewedJobCascade();
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
    const pageLink = event.target.closest("[data-show-page]");
    if (pageLink) return pageLink.dataset.showPage === "actions" ? openCalendarDay(formatDateTimeLocal(new Date()).slice(0, 10)) : switchWorkspacePage(pageLink.dataset.showPage);
    const dayLink = event.target.closest("[data-calendar-open]");
    if (dayLink) return openCalendarDay(dayLink.dataset.calendarOpen);
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
      else if (operation === "start-track-task") window.MakoTasks.openCreate({trackId: id});
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
  document.querySelectorAll("[data-action-view]").forEach(control => control.addEventListener("click", () => {
    document.querySelectorAll("[data-action-view]").forEach(item => item.setAttribute("aria-pressed", String(item === control)));
    document.getElementById("action-calendar").hidden = control.dataset.actionView !== "calendar";
    document.getElementById("action-list").hidden = control.dataset.actionView !== "list";
  }));
  document.querySelectorAll("[data-calendar-month]").forEach(control => control.addEventListener("click", () => {
    state.calendarMonth.setMonth(state.calendarMonth.getMonth() + Number(control.dataset.calendarMonth));
    state.calendarDay = formatDateTimeLocal(state.calendarMonth).slice(0, 10);
    renderCalendar();
  }));
  document.getElementById("calendar-today").addEventListener("click", () => {
    const today = new Date();
    state.calendarMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    state.calendarDay = formatDateTimeLocal(today).slice(0, 10);
    renderCalendar();
  });
  document.getElementById("calendar-grid").addEventListener("click", event => {
    const day = event.target.closest("[data-calendar-day]");
    if (!day) return;
    state.calendarDay = day.dataset.calendarDay;
    renderCalendar();
  });
  document.getElementById("calendar-add-action").addEventListener("click", () => {
    openActionDialog(null, document.getElementById("action-track-filter").value || null);
    document.getElementById("action-due").value = `${state.calendarDay}T09:00`;
  });

  document.querySelectorAll('input[name="track-source"]').forEach(input => input.addEventListener("change", () => {
    const manual = input.value === "manual_jd" && input.checked;
    if (!input.checked) return;
    document.getElementById("track-reviewed-fields").hidden = manual;
    document.getElementById("track-manual-fields").hidden = !manual;
  }));
  document.getElementById("track-reviewed-industry").addEventListener("change", updateReviewedCompanyTypes);
  document.getElementById("track-reviewed-company-type").addEventListener("change", updateReviewedCompanies);
  document.getElementById("track-reviewed-company").addEventListener("change", updateReviewedJobOptions);

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
      if (!impact.tracks && !impact.actions && !impact.tasks) {
        setMessage("当前工作区没有需要清除的数据。", "success");
        return;
      }
      const confirmed = window.confirm(
        `将永久删除 ${impact.tracks} 个目标岗位、${impact.actions} 项行动和 ${impact.tasks || 0} 个求职任务。此操作无法撤销，是否继续？`
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

  const guide = document.getElementById("operation-guide");
  const guideHeading = document.getElementById("guide-heading");
  const guidePrimary = document.getElementById("guide-primary");
  let guideAction = null;
  const guideShell = document.getElementById("guide-card-shell");
  const guideTilt = document.getElementById("guide-tilt-surface");
  const guideCard = document.getElementById("guide-card");
  const guideFront = document.getElementById("guide-card-front");
  const guideReverse = document.getElementById("guide-card-back");
  const guideFlip = document.getElementById("guide-flip");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const mouseMotion = matchMedia("(hover: hover) and (pointer: fine)");
  const resetGuideTilt = () => { guideTilt.style.transform = ""; };
  const flipGuide = (flipped, animate = false) => {
    resetGuideTilt();
    guideCard.dataset.animate = String(animate);
    guideCard.classList.toggle("is-flipped", flipped);
    guideFront.inert = flipped;
    guideFront.setAttribute("aria-hidden", String(flipped));
    guideReverse.inert = !flipped;
    guideReverse.setAttribute("aria-hidden", String(!flipped));
    guideFlip.setAttribute("aria-pressed", String(flipped));
    guideFlip.textContent = flipped ? "返回工具介绍 ↶" : "查看准备材料 ↻";
  };
  guideFlip.addEventListener("click", event => flipGuide(guideFlip.getAttribute("aria-pressed") !== "true", event.detail > 0));
  guideShell.addEventListener("pointermove", event => {
    if (guideFlip.hidden || guideFlip.getAttribute("aria-pressed") === "true" || event.pointerType !== "mouse" || reducedMotion.matches || !mouseMotion.matches || guideCard.getAnimations().length) return;
    const rect = guideShell.getBoundingClientRect();
    const x = Math.max(-1, Math.min(1, (event.clientX - rect.left) / rect.width * 2 - 1));
    const y = Math.max(-1, Math.min(1, (event.clientY - rect.top) / rect.height * 2 - 1));
    guideTilt.style.transform = "rotateX(" + (-y * 2) + "deg) rotateY(" + (x * 2) + "deg)";
  });
  guideShell.addEventListener("pointerleave", resetGuideTilt);
  guide.addEventListener("keydown", resetGuideTilt);
  reducedMotion.addEventListener("change", resetGuideTilt);
  mouseMotion.addEventListener("change", resetGuideTilt);
  const guideStarts = {
    direction: {
      title: "先认识自己，再缩小方向", description: "从背景诊断开始，把已有经历和还不确定的部分分开。",
      steps: ["写下专业、项目经历与求职偏好。", "建立一个背景诊断任务，确认材料后再分析。", "保存值得保留的结果，再按需要进入方向匹配。"],
      label: "从背景诊断开始", intent: "career_profile"
    },
    job: {
      title: "围绕一个岗位，串起准备", description: "用同一个求职任务连接 JD 分析、简历与面试，减少重复提供材料。",
      steps: ["备好完整 JD；已有目标岗位时，可在新任务中绑定。", "以 JD 分析建立任务，写清最想弄懂的问题。", "确认结果后保存，再沿用任务进入简历或面试阶段。"],
      label: "建立 JD 分析任务", intent: "career_jd"
    },
    application: {
      title: "先准备最近要用的那一份", description: "临近投递先优化简历；已收到面试邀请，可以在新任务中选“面试准备”。",
      steps: ["备好目标 JD、简历和相关项目经历。", "选择简历优化或面试准备，写下这次要解决的问题。", "核对分析中的事实，把需要补齐的事项安排进日历。"],
      label: "建立投递准备任务", intent: "career_resume"
    }
  };
  const renderGuide = (route, contextual = false) => {
    document.getElementById("guide-location").hidden = !route || !contextual;
    guideAction = route;
    flipGuide(false);
    const materials = route?.materials || [];
    guideShell.classList.toggle("has-materials", materials.length > 0);
    guideFlip.hidden = guideReverse.hidden = !materials.length;
    document.getElementById("guide-materials").replaceChildren(...materials.map(value => textElement("li", value)));
    document.getElementById("guide-status").textContent = "";
    guideHeading.textContent = route?.title || "不知道从哪里开始？";
    document.getElementById("guide-description").textContent = route?.description || "选最接近你现状的一项，Finn 帮你找到第一步。";
    document.getElementById("guide-starts").hidden = Boolean(route);
    const steps = document.getElementById("guide-steps");
    steps.hidden = !route;
    steps.replaceChildren(...(route?.steps || []).map(value => textElement("li", value)));
    guidePrimary.hidden = !route;
    guidePrimary.textContent = route?.label || "";
    document.getElementById("guide-back").hidden = !route;
  };
  const currentGuide = () => {
    if (!skillView.hidden) {
      const hasResult = !document.getElementById("result").hidden;
      const inTask = !document.getElementById("task-context-rail").hidden;
      const hasCandidates = !document.getElementById("task-action-candidates").hidden;
      const saved = document.getElementById("save-task-result").textContent === "已保存";
      const title = document.getElementById("skill-title").textContent;
      document.getElementById("guide-location").textContent = `你在这里 · ${title}`;
      return hasResult ? {
        title: "分析之后，先核对再保留", description: "结果需要你的判断。先核对事实，再决定下一步。",
        steps: ["检查经历、数字与引用来源，区分事实和建议。", inTask ? (saved ? "结果已保存到当前任务，可以返回任务继续准备。" : "在结果区点击“保存到当前任务”，保留正文与来源。") : "结果可复制或下载；开启本机保留后，可在刷新时恢复正文副本。", inTask ? (hasCandidates ? "勾选需要的行动建议，检查后加入日程并设置日期。" : "返回任务选择下一阶段，或到行动日程中手动添加事项。") : "想持续推进时，建立求职任务来连接后续准备。"],
        label: "前往结果区核对", target: "#output-card", focusOnly: true
      } : {
        title: `这次先完成${title}`, description: document.getElementById("skill-description").textContent,
        materials: [...document.querySelectorAll("#skill-prepare li")].map(item => item.textContent),
        steps: [document.querySelector("#skill-prepare li")?.textContent || "整理这次分析需要的经历和材料。", "填写需求、添加附件，直接点击开始分析。", inTask ? "分析完成后，可保存到任务并继续下一个阶段。" : "独立分析可复制或下载结果，也可开启本机草稿保留。"],
        label: "查看本阶段准备说明", target: "#analysis-guide summary", focusOnly: true
      };
    }
    const page = document.querySelector(".workspace-page:not([hidden])")?.dataset.page || "overview";
    document.getElementById("guide-location").textContent = `你在这里 · ${page === "overview" ? "我的工作台" : viewCopy[page][0]}`;
    const continuing = document.querySelector('[data-dashboard-continue]');
    const taskContinue = document.querySelector('[data-task-operation="continue"]');
    return {
      overview: continuing ? {title: "接着上次的准备继续", description: "工作台已显示一个进行中的任务，可以从它接着做。", steps: ["打开任务，核对当前岗位与材料。", "完成当前阶段，需要时沿用任务切换工具。", "保存结果，把确认后的行动安排到日历。"], label: "继续工作台上的任务", target: "[data-dashboard-continue]"} : null,
      tasks: {title: "用一个任务，装下同一个目标", description: "任务连接你的岗位、材料与分析阶段。六个工具可以按需要选择。", steps: ["选择已有任务，或新建一个明确的求职目标。", "提供材料，点击开始分析，再查看结果。", "保存结果后沿用任务进入下一阶段。"], label: taskContinue ? "继续选中的任务" : "新建求职任务", target: taskContinue ? '[data-task-operation="continue"]' : "#open-task-dialog"},
      tracks: {title: "先把一个目标岗位留在这里", description: "这里记录具体机会和投递进度；求职任务用来推进针对它的准备。", steps: ["添加已核验职位，或自行提供完整 JD。", "查看岗位详情，选择“以此岗位开始任务”。", "在同一任务内推进 JD、简历与面试准备。"], label: "添加一个目标岗位", target: '[data-page="tracks"] [data-open-track]'},
      materials: {title: "先放入一份最有用的材料", description: "优先选择本次准备会用到的简历或项目复盘，不必一次整理完所有文件。", steps: ["选择 TXT、Markdown、文本 PDF 或 DOCX 文件。", "预览解析内容，核对后确认保存到本机。", "在求职任务中选择材料，或使用自动查找。"], label: "前往材料上传区", target: "#knowledge-file", focusOnly: true},
      actions: {title: "给下一步一个具体日期", description: "日历按截止日期显示行动；点选某天可以查看当天完整事项。", steps: ["添加一项行动，或检查分析生成的待确认建议。", "写清完成标准，选择日期并保存。", "完成后勾选；需要改期时打开行动的“编辑”。"], label: "添加一项行动", target: '[data-page="actions"] [data-open-action]'}
    }[page];
  };
  guide.addEventListener("beforetoggle", event => {
    if (event.newState === "open") renderGuide(currentGuide(), true);
    else resetGuideTilt();
  });
  guide.addEventListener("pointerdown", () => { guide.dataset.motion = "pointer"; });
  guide.addEventListener("keydown", () => { guide.dataset.motion = "keyboard"; });
  guide.addEventListener("toggle", event => {
    document.getElementById("guide-launcher").setAttribute("aria-expanded", String(event.newState === "open"));
  });
  guide.addEventListener("click", event => {
    const start = event.target.closest("[data-guide-start]");
    if (start) { renderGuide(guideStarts[start.dataset.guideStart]); guideHeading.focus(); }
  });
  document.getElementById("guide-back").addEventListener("click", () => { renderGuide(null); guideHeading.focus(); });
  guidePrimary.addEventListener("click", () => {
    if (!guideAction) return;
    if (!window.MakoApp.canSwitch()) {
      document.getElementById("guide-status").textContent = "正在处理当前操作，完成后就可以前往。";
      return;
    }
    const route = guideAction;
    const target = route.target ? document.querySelector(route.target) : null;
    if (!route.intent && (!target || !target.getClientRects().length)) {
      renderGuide(currentGuide(), true);
      document.getElementById("guide-status").textContent = "页面内容已变化，已更新指南。";
      return;
    }
    guide.hidePopover();
    if (route.intent) {
      switchWorkspacePage("tasks");
      window.MakoTasks.openCreate({intent: route.intent});
    } else if (route.focusOnly) {
      if (target.parentElement.tagName === "DETAILS") target.parentElement.open = true;
      if (!target.matches("input, button, summary")) target.setAttribute("tabindex", "-1");
      target.focus({preventScroll: true});
      target.scrollIntoView({block: "center", behavior: "instant"});
    } else target.click();
  });

  switchWorkspacePage("overview");
  loadWorkspaceData();
})();
