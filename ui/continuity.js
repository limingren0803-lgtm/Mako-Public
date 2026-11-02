(() => {
  const KEY = "mako.continuity.v1";
  const WEEK = 7 * 24 * 60 * 60 * 1000;
  const MAX_SIZE = 2_000_000;
  const skills = new Set([...document.querySelectorAll("[data-skill]")].map(node => node.dataset.skill));
  const views = new Set(["overview", "tasks", "tracks", "materials", "actions", "skill"]);
  const fieldIds = ["request", "manual-jd", "manual-jd-source", "evidence-detail", "job-query", "job-age", "job-mode"];
  const checkbox = document.getElementById("retain-on-device");
  const dialog = document.getElementById("continuity-dialog");
  const banner = document.getElementById("resume-banner");
  const status = document.getElementById("retention-status");
  let enabled = false, blocked = false, restoring = false, pending = null, baseline = null, lastContent = "", timer;
  const identifier = value => typeof value === "string" && /^[A-Za-z0-9_-]{1,100}$/.test(value);
  const bounded = (value, limit) => typeof value === "string" && value.length <= limit;
  const validDate = value => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return false;
    const date = new Date(`${value}T12:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  };
  const validPosition = position => position && views.has(position.view) && skills.has(position.skill)
    && (position.taskId === null || identifier(position.taskId)) && validDate(position.date)
    && ["calendar", "list"].includes(position.actionView) && Number.isFinite(position.y) && position.y >= 0 && position.y <= 1_000_000
    && ["page", "result"].includes(position.region);
  const decode = raw => {
    if (raw.length > MAX_SIZE) throw new Error("保留内容超出读取范围");
    const data = JSON.parse(raw);
    if (data.version !== 1 || !Number.isFinite(data.updatedAt) || data.updatedAt > Date.now() + 300000 || !validPosition(data.position)
      || !Array.isArray(data.drafts) || data.drafts.length > 20) throw new Error("保留格式无法识别");
    const keys = new Set();
    for (const draft of data.drafts) {
      if (!draft || !skills.has(draft.skill) || !identifier(draft.taskId) || !draft.fields || typeof draft.fields !== "object"
        || !bounded(draft.fileText, 15000) || !bounded(draft.response, 100000)
        || (draft.requestId !== null && !bounded(draft.requestId, 128))
        || !["manual", "verified"].includes(draft.matchSource) || !["auto", "selected", "off"].includes(draft.materialMode)) throw new Error("草稿内容无法识别");
      for (const [id, value] of Object.entries(draft.fields)) {
        if (!fieldIds.includes(id)) throw new Error("草稿字段无法识别");
        const control = document.getElementById(id);
        if (!bounded(value, control.maxLength > 0 ? control.maxLength : 200)
          || (control.tagName === "SELECT" && ![...control.options].some(option => option.value === value))) throw new Error("草稿输入超出范围");
      }
      if (draft.attachments !== undefined && (!Array.isArray(draft.attachments) || draft.attachments.length > 5 || draft.attachments.some(name => !bounded(name, 255)))) throw new Error("附件提示超出范围");
      if (draft.responseComplete !== undefined && typeof draft.responseComplete !== "boolean") throw new Error("结果状态无法识别");
      const key = `${draft.taskId}:${draft.skill}`;
      if (keys.has(key)) throw new Error("草稿重复");
      keys.add(key);
    }
    return data;
  };
  const showStatus = (text, error = false) => {
    status.textContent = text;
    status.classList.toggle("error", error);
    document.getElementById("continuity-message").textContent = text;
    const notice = document.getElementById("continuity-notice");
    notice.textContent = error ? text : "";
    notice.hidden = !error;
  };
  const capturePosition = () => {
    const workspace = window.MakoWorkspace.position();
    const app = window.MakoApp.position();
    return {...workspace, ...app, taskId: workspace.view === "tasks" ? window.MakoTasks.selected() : workspace.view === "skill" ? app.taskId : null,
      y: Math.round(scrollY), region: workspace.view === "skill" && !document.getElementById("result").hidden && document.getElementById("output-card").getBoundingClientRect().top < innerHeight / 2 ? "result" : "page"};
  };
  history.scrollRestoration = "manual";
  let lastPosition = capturePosition();
  const setRestoring = value => {
    restoring = value;
    document.querySelector(".workspace").inert = value;
    document.querySelector(".topbar").inert = value;
    document.getElementById("guide-launcher").disabled = value;
  };
  const flush = () => {
    clearTimeout(timer);
    if (!enabled || blocked || pending || restoring) return false;
    try {
      if (localStorage.getItem(KEY) !== baseline) throw new Error("另一页面更新了保留内容，本页自动保留已暂停。请重新打开页面选择恢复，或关闭后重新开启保留。");
      const content = {drafts: window.MakoApp.portableDrafts(), position: capturePosition()};
      if (content.drafts.length > 20) throw new Error("本机最多保留 20 份草稿，请先清除不用的输入后重新开启保留");
      const signature = JSON.stringify(content);
      if (signature === lastContent) { showStatus("本机草稿已保留 · 结果需另存到任务"); return true; }
      const raw = JSON.stringify({version: 1, updatedAt: Date.now(), ...content});
      decode(raw);
      localStorage.setItem(KEY, raw);
      baseline = raw; lastContent = signature;
      showStatus(`本机草稿已保留 · ${new Date().toLocaleTimeString("zh-CN", {hour: "2-digit", minute: "2-digit"})} · 结果需另存到任务`);
      return true;
    } catch (error) {
      blocked = true;
      const message = error.name === "QuotaExceededError" ? "浏览器存储空间不足，草稿未能保留" : error.name === "SecurityError" ? "浏览器未允许使用本机存储" : error.message || "本机存储不可用";
      showStatus(`${message}。本次内容仍在页面内，请先复制或下载。`, true);
      return false;
    }
  };
  const schedule = () => {
    if (!enabled || blocked || pending || restoring) return;
    clearTimeout(timer);
    showStatus("正在保留本机草稿…");
    timer = setTimeout(flush, 350);
  };
  const navigate = () => queueMicrotask(() => {
    if (restoring) return;
    const position = capturePosition();
    const key = value => `${value.view}:${value.taskId}:${value.view === "skill" ? value.skill : ""}`;
    if (key(position) !== key(lastPosition)) history.pushState({mako: position}, "");
    else history.replaceState({mako: position}, "");
    lastPosition = position;
    schedule();
  });
  const restorePosition = async (position, resume = false) => {
    if (position.view === "skill") {
      if (position.taskId) await window.MakoTasks.resume(position.taskId, position.skill);
      else window.MakoApp.resumeIndependent(position.skill);
    } else {
      await window.MakoWorkspace.showPage(position.view);
      if (position.view === "tasks" && position.taskId) await window.MakoTasks.resume(position.taskId);
      if (position.view === "actions") {
        await window.MakoWorkspace.refresh();
        window.MakoWorkspace.restoreCalendar(position.date, position.actionView);
      }
    }
    if (resume) banner.hidden = true;
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (position.region === "result" && !document.getElementById("result").hidden) document.getElementById("output-card").scrollIntoView({block: "start", behavior: "instant"});
    else window.scrollTo({top: position.y, behavior: "instant"});
  };
  const erase = () => {
    clearTimeout(timer);
    try {
      localStorage.removeItem(KEY);
      baseline = null; pending = null; enabled = false; blocked = false; lastContent = "";
      checkbox.checked = false; banner.hidden = true;
      window.MakoApp.forgetRetained();
      showStatus("本机保留已关闭并清除；当前页面输入和已保存任务不受影响。");
    } catch { blocked = true; showStatus("浏览器未允许清除保留内容，请在浏览器设置中清除此站点的数据。", true); }
  };
  const describePending = () => {
    banner.hidden = false;
    window.scrollTo({top: 0, behavior: "instant"});
    document.getElementById("resume-description").textContent = `${new Date(pending.updatedAt).toLocaleString("zh-CN")} · ${pending.drafts.length} 份草稿与上次位置。恢复后可以接着编辑；临时附件需重新选择。`;
    showStatus("有上次保留的内容，请先选择恢复或丢弃；当前输入尚未覆盖它。");
  };
  try {
    baseline = localStorage.getItem(KEY);
    if (baseline) {
      pending = decode(baseline);
      if (Date.now() - pending.updatedAt > WEEK) { erase(); showStatus("上次保留内容已超过 7 天，已清除。可重新开启本机保留。"); }
      else { enabled = true; checkbox.checked = true; describePending(); }
    }
  } catch { blocked = true; showStatus("本机保留内容不可读取，未自动覆盖。可在设置中关闭并清除。", true); }
  checkbox.addEventListener("change", () => {
    if (!checkbox.checked) return erase();
    if (pending || blocked) { checkbox.checked = enabled; showStatus("请先恢复上次内容，或关闭并清除已有保留。", true); return; }
    enabled = true; flush();
  });
  for (const id of ["open-continuity", "configure-retention"]) document.getElementById(id).addEventListener("click", () => {
    document.getElementById("workspace-data-menu").open = false;
    dialog.showModal();
  });
  for (const id of ["clear-retained", "discard-retained"]) document.getElementById(id).addEventListener("click", () => {
    if (confirm("关闭并清除此浏览器保留的全部草稿和位置？当前页面输入、材料库和已保存任务不会删除。")) erase();
  });
  document.getElementById("resume-last").addEventListener("click", async event => {
    if (!pending || !window.MakoApp.canSwitch()) return;
    if (window.MakoApp.portableDrafts().length && !confirm("恢复会替换当前页面同一任务和工具的输入，是否继续？")) return;
    event.target.disabled = true; setRestoring(true);
    try {
      window.MakoApp.retain(pending.drafts);
      await restorePosition(pending.position, true);
      pending = null; banner.hidden = true;
      lastPosition = capturePosition(); history.replaceState({mako: lastPosition}, "");
      document.getElementById("resume-error").textContent = "";
    } catch (error) { banner.hidden = false; document.getElementById("resume-error").textContent = `${error.message || "暂时无法恢复"} 保留内容未删除，可以稍后重试。`; }
    finally { setRestoring(false); event.target.disabled = false; if (!pending) { document.getElementById("main-content").focus({preventScroll: true}); flush(); } }
  });
  window.addEventListener("storage", event => {
    if (event.key !== KEY && event.key !== null) return;
    clearTimeout(timer);
    blocked = true;
    if (event.newValue === null) { enabled = false; checkbox.checked = false; pending = null; banner.hidden = true; window.MakoApp.forgetRetained(); }
    showStatus("另一页面更改或清除了本机保留，本页自动保留已暂停；当前输入仍在。", true);
  });
  window.addEventListener("popstate", async event => {
    if (!validPosition(event.state?.mako)) return;
    if (restoring || !window.MakoApp.canSwitch()) { history.replaceState({mako: lastPosition}, ""); return; }
    setRestoring(true);
    try { await restorePosition(event.state.mako); lastPosition = capturePosition(); }
    catch (error) { showStatus(`${error.message || "暂时无法返回上次位置"} 当前草稿仍保留。`, true); history.replaceState({mako: capturePosition()}, ""); }
    finally { setRestoring(false); document.getElementById("main-content").focus({preventScroll: true}); schedule(); }
  });
  document.querySelector(".input-card").addEventListener("input", schedule);
  document.querySelector(".input-card").addEventListener("change", schedule);
  document.addEventListener("click", () => setTimeout(navigate, 0));
  window.addEventListener("scroll", () => {
    if (restoring) return;
    lastPosition = capturePosition(); history.replaceState({mako: lastPosition}, ""); schedule();
  }, {passive: true});
  window.addEventListener("pagehide", flush);
  history.replaceState({mako: lastPosition}, "");
  window.MakoContinuity = Object.freeze({schedule, navigate, flush});
})();
