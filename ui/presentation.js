(() => {
  const node = (tag, value = "", className = "") => {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    return element;
  };
  // ponytail: bounded Markdown subset, not CommonMark; unsupported syntax remains readable text.
  const inline = (target, value, depth = 0) => {
    if (depth > 3) { target.append(document.createTextNode(value)); return; }
    const pattern = /`([^`\n]+)`|\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|\[([^\]\n]+)\]\(([^\s)]+)\)/g;
    let last = 0;
    for (const match of value.matchAll(pattern)) {
      target.append(document.createTextNode(value.slice(last, match.index)));
      const [, code, bold, emphasis, label, href] = match;
      let element;
      if (code !== undefined) element = node("code", code);
      else if (label !== undefined) {
        let url;
        try { url = new URL(href); } catch (_) { /* Keep invalid links as text. */ }
        if (url && ["https:", "http:"].includes(url.protocol) && !url.username && !url.password && value[match.index - 1] !== "!") {
          element = node("a", label); element.href = url.href; element.rel = "noopener noreferrer"; element.target = "_blank";
        } else element = node("span", match[0]);
      } else { element = node(bold !== undefined ? "strong" : "em"); inline(element, bold ?? emphasis, depth + 1); }
      target.append(element); last = match.index + match[0].length;
    }
    target.append(document.createTextNode(value.slice(last)));
  };
  const cells = line => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|");
  const markdown = (target, source, headingOffset = 1) => {
    target.replaceChildren(); target.classList.add("markdown");
    const lines = String(source || "").replace(/\r\n?/g, "\n").split("\n");
    let list = null;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (!line.trim()) { list = null; continue; }
      const fence = /^\s*(`{3,}|~{3,})/.exec(line);
      if (fence) {
        const content = [];
        while (++i < lines.length && !new RegExp(`^\\s*${fence[1][0]}{${fence[1].length},}\\s*$`).test(lines[i])) content.push(lines[i]);
        const pre = node("pre"); pre.append(node("code", content.join("\n"))); target.append(pre); list = null; continue;
      }
      if (line.includes("|") && lines[i + 1]?.includes("|") && cells(lines[i + 1]).every(cell => /^\s*:?-{3,}:?\s*$/.test(cell))) {
        const wrap = node("div", "", "markdown-table"); wrap.tabIndex = 0; wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", "分析表格，可横向滚动");
        const table = node("table"); const head = node("thead"); const row = node("tr");
        cells(line).forEach(value => { const cell = node("th"); cell.scope = "col"; inline(cell, value.trim()); row.append(cell); });
        head.append(row); table.append(head); const body = node("tbody"); i++;
        while (lines[i + 1]?.trim() && lines[i + 1].includes("|")) {
          const row = node("tr"); cells(lines[++i]).forEach(value => { const cell = node("td"); inline(cell, value.trim()); row.append(cell); }); body.append(row);
        }
        table.append(body); wrap.append(table); target.append(wrap); list = null; continue;
      }
      const heading = /^(#{1,6})\s+(.+)$/.exec(line);
      const item = /^\s*(?:([-+*])\s+|\d+[.)]\s+)(.+)$/.exec(line);
      if (item) {
        const tag = item[1] ? "UL" : "OL";
        if (list?.tagName !== tag) { list = node(tag.toLowerCase()); target.append(list); }
        const li = node("li"); inline(li, item[2]); list.append(li); continue;
      }
      list = null;
      const block = node(heading ? `h${Math.min(heading[1].length + headingOffset, 6)}` : /^>\s?/.test(line) ? "blockquote" : "p");
      inline(block, heading ? heading[2] : line.replace(/^>\s?/, "")); target.append(block);
    }
  };
  const resultSections = source => {
    const lines = String(source || "").replace(/\r\n?/g, "\n").split("\n");
    const headings = [], numbered = [];
    let fence = null;
    lines.forEach((line, index) => {
      if (fence) {
        if (new RegExp(`^\\s*${fence[0]}{${fence.length},}\\s*$`).test(line)) fence = null;
        return;
      }
      fence = /^\s*(`{3,}|~{3,})/.exec(line)?.[1] || null;
      if (fence) return;
      const heading = /^(#{1,2})\s+(.+)$/.exec(line);
      if (heading) { headings.push({index, level: heading[1].length, title: heading[2].trim().replace(/^\*\*(.+)\*\*$/, "$1")}); return; }
      if (index && lines[index - 1].trim()) return;
      if (lines[index + 1]?.trim()) return;
      const plain = line.trim().replace(/^\*\*(.+)\*\*$/, "$1");
      const match = /^(\d{1,2})[.、．]\s+(.+)$/.exec(plain);
      const title = match?.[2].replace(/^\*\*(.+)\*\*$/, "$1").replace(/[：:]$/, "").trim();
      if (title && title.length <= 42 && !/[。！？；;]$/.test(title)) numbered.push({index, number: Number(match[1]), title: `${match[1]}. ${title}`});
    });
    // ponytail: blank-separated short numbered lines are the only plain-number heading signal; ambiguous loose lists stay one block when the sequence is not clear.
    const level = [1, 2].find(value => headings.filter(item => item.level === value).length >= 2);
    const chosen = level ? headings.filter(item => item.level === level) : numbered.length >= 2 && [0, 1].includes(numbered[0].number)
      && numbered.every((item, index) => !index || item.number === numbered[index - 1].number + 1 && item.index - numbered[index - 1].index >= 3)
      ? numbered : [];
    if (chosen.length < 2) return null;
    const sections = [];
    if (lines.slice(0, chosen[0].index).join("\n").trim()) sections.push({title: "开头说明", body: lines.slice(0, chosen[0].index).join("\n")});
    chosen.forEach((item, index) => sections.push({title: item.title, body: lines.slice(item.index + 1, chosen[index + 1]?.index ?? lines.length).join("\n")}));
    return sections;
  };
  let resultRenderId = 0;
  const renderResult = (target, source, planning = false) => {
    target.dataset.rawText = source || "";
    const sections = resultSections(source);
    if (sections) {
      target.replaceChildren(); target.classList.add("markdown");
      const outline = node("nav", "", "result-outline"); outline.setAttribute("aria-label", "本次分析目录");
      outline.append(node("span", "本次分析", "result-outline-label"));
      const links = node("div", "", "result-outline-links");
      const groupId = ++resultRenderId;
      sections.forEach((section, index) => {
        const card = node("section", "", "result-section"); card.id = `result-section-${groupId}-${index + 1}`; card.tabIndex = -1;
        card.setAttribute("aria-label", section.title);
        card.append(node("h4", section.title));
        const body = node("div"); markdown(body, section.body, 3); card.append(body);
        const button = node("button", section.title); button.type = "button";
        button.addEventListener("click", () => { card.focus({preventScroll: true}); card.scrollIntoView({block: "start"}); });
        links.append(button); target.append(card);
      });
      outline.append(links); target.prepend(outline);
    } else markdown(target, source);
    if (!planning) return;
    // ponytail: the timeline recognizes only explicit time headings; all source sections remain visible below it.
    const groups = []; let group = null; let inCode = false;
    for (const line of String(source || "").split(/\r?\n/)) {
      if (/^\s*(`{3,}|~{3,})/.test(line)) { inCode = !inCode; continue; }
      if (inCode) continue;
      const title = line.trim().replace(/^#{1,6}\s+/, "").replace(/^\*\*(.*?)\*\*$/, "$1").replace(/[：:]$/, "");
      if (/^(今天|近期|第[一二三123](?:个)?月)$/.test(title)) { group = {title, items: []}; groups.push(group); }
      else if (/^#{1,6}\s/.test(line)) group = null;
      else {
        const item = /^\s*(?:[-+*]|\d+[.)])\s+(.+)$/.exec(line);
        if (group && item) group.items.push(item[1]);
        else if (line.trim()) group = null;
      }
    }
    const usable = groups.filter(group => group.items.length);
    if (!usable.length) return;
    const timeline = node("section", "", "planning-timeline");
    timeline.append(node("h3", "按时间推进"), node("p", "以下仅整理原文中明确列出的事项，尚未加入行动日程。", "hint"));
    usable.forEach(group => { const section = node("section"); section.append(node("h4", group.title)); const list = node("ul"); group.items.forEach(item => { const li = node("li"); inline(li, item); list.append(li); }); section.append(list); timeline.append(section); });
    target.prepend(timeline);
  };
  const wait = (target, message) => {
    const start = Date.now(); target.textContent = message;
    const elapsed = node("span", " · 已经过 0 秒", "elapsed"); elapsed.setAttribute("aria-hidden", "true"); target.append(elapsed);
    const timer = setInterval(() => { elapsed.textContent = ` · 已经过 ${Math.floor((Date.now() - start) / 1000)} 秒`; }, 1000);
    return () => clearInterval(timer);
  };
  const upload = (input, receive, fail) => {
    const zone = input.closest(".upload-zone, .knowledge-upload-zone");
    if (!zone) return;
    const label = zone.querySelector("label"); label.tabIndex = 0; label.setAttribute("role", "button");
    label.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); if (!input.disabled) input.click(); } });
    let depth = 0;
    zone.addEventListener("dragenter", event => { if (!event.dataTransfer.types.includes("Files")) return; event.preventDefault(); depth++; zone.classList.toggle("drag-over", !input.disabled); });
    zone.addEventListener("dragover", event => { if (event.dataTransfer.types.includes("Files")) { event.preventDefault(); event.dataTransfer.dropEffect = input.disabled ? "none" : "copy"; } });
    zone.addEventListener("dragleave", () => { if (--depth <= 0) zone.classList.remove("drag-over"); });
    zone.addEventListener("drop", event => {
      event.preventDefault(); depth = 0; zone.classList.remove("drag-over");
      if (input.disabled) return;
      if (!input.multiple && event.dataTransfer.files.length !== 1) return fail("请每次选择一份文件，完成预览后再添加下一份。");
      receive(input.multiple ? [...event.dataTransfer.files] : event.dataTransfer.files[0]);
    });
  };
  const stages = {career_profile: "背景诊断", career_match: "方向匹配", career_jd: "JD 分析", career_resume: "简历优化", career_interview: "面试准备", career_planning: "行动规划"};
  const route = (target, task) => {
    target.replaceChildren(); target.classList.add("career-route"); target.setAttribute("aria-label", "求职航线；可按需要选择阶段");
    Object.entries(stages).forEach(([intent, label], index) => {
      const current = task.career_intent === intent;
      const saved = task.saved_analysis_intent === intent && Boolean(task.saved_analysis_text);
      const li = node("li", "", current ? "current" : ""); if (current) li.setAttribute("aria-current", "step");
      li.append(node("span", String(index + 1).padStart(2, "0")), node("b", label), node("small", current ? "当前阶段" : saved ? "已有保存结果" : "按需前往")); target.append(li);
    });
  };
  const analysisState = payload => {
    if (![payload?.conclusion, payload?.response].some(value => typeof value === "string" && value.trim()) || (payload?.response_complete === false && Array.isArray(payload.quality_flags) && payload.quality_flags.includes("empty_response"))) return "empty";
    return payload.response_complete === false ? "partial" : "complete";
  };
  const renderAnalysis = (target, payload, planning = false) => {
    if (analysisState(payload) === "empty") { target.replaceChildren(); delete target.dataset.rawText; return; }
    const original = typeof payload.response === "string" && payload.response.trim() ? payload.response : "";
    const distinctConclusion = typeof payload.conclusion === "string" && payload.conclusion.trim() && payload.conclusion.trim() !== original.trim();
    const conclusion = distinctConclusion ? payload.conclusion : original;
    const label = distinctConclusion ? "结论与下一步" : "完整分析";
    const tab = document.getElementById("conclusions-tab");
    const heading = document.querySelector("#conclusions-panel .result-column-heading");
    if (tab) tab.textContent = label;
    if (heading) heading.textContent = label;
    renderResult(target, conclusion, planning && !distinctConclusion);
    if (!distinctConclusion && original) target.prepend(node("p", "这次没有单独生成简短结论；以下是完整分析，请核对依据后使用。", "task-reference-warning"));
    if (analysisState(payload) === "partial") target.prepend(node("p", "回答未完成。下面只保留了已返回的内容，不能当作完整结论；核对后可以保留或重新分析。", "task-reference-warning"));
    for (const [field, title] of [["gaps", "仍需补齐"], ["recommendations", "建议下一步"]]) {
      if (!Array.isArray(payload[field]) || !payload[field].length) continue;
      const section = node("section", "", "structured-analysis-section"); section.append(node("h3", title));
      const list = node("ul");
      payload[field].forEach(value => { const li = node("li"); if (typeof value === "string") inline(li, value); else li.append(node("code", JSON.stringify(value))); list.append(li); });
      section.append(list); target.append(section);
    }
    if (original && conclusion !== original) {
      const full = node("div");
      if (resultSections(original)) {
        target.append(node("h3", "完整分析正文")); renderResult(full, original, planning); target.append(full);
      } else {
        const details = node("details"); details.append(node("summary", "查看完整分析正文"));
        markdown(full, original); details.append(full); target.append(details);
      }
    }
    target.dataset.rawText = original || conclusion;
  };
  const renderBasis = (target, payload) => {
    target.replaceChildren();
    const resume = payload.resume_usage || payload.analysis_basis?.resume;
    if (resume) {
      const section = node("section", "", "material-usage");
      section.append(node("h3", "本次简历"));
      if (resume.source === "none") section.append(node("p", "本次未使用简历。"));
      else if (resume.source === "legacy") section.append(node("p", "本次未单独指定简历，个人材料仍按原有检索规则参与。"));
      else {
        section.append(node("b", resume.title || resume.filename || "所选简历"));
        const included = Number(resume.included_characters || 0);
        section.append(node("p", `${resume.source === "temporary" ? "本次附件" : "个人材料库"} · ${included > 0 ? `已进入分析 ${included} 字` : "未进入分析上下文"}`));
        if (resume.truncated) section.append(node("p", "这次只纳入了部分简历内容；涉及未纳入部分的判断还需要核对。", "task-reference-warning"));
        if (!included && resume.unused_reason) section.append(node("p", "所选简历未被采用，请检查文件状态或重新选择后分析。", "task-reference-warning"));
      }
      target.append(section);
    }
    const usage = payload.personal_material_usage || payload.analysis_basis?.saved_materials;
    if (usage && Array.isArray(usage.items)) {
      const section = node("section", "", "material-usage");
      section.append(node("h3", "个人材料采用情况"), node("p", `本次范围 ${usage.expected_count} 份 · 采用 ${usage.used_count} 份 · 未采用 ${usage.unused_count} 份`));
      const list = node("ul");
      usage.items.forEach(item => {
        const li = node("li"); li.append(node("b", item.title || item.material_id));
        li.append(node("span", item.status === "used" ? "已采用" : item.status === "unused" ? "未采用" : "状态未提供"));
        if (item.status === "unused") li.append(node("p", item.unused_reason === "no_relevant_chunk" ? "本次没有检索到达到相关性要求的内容。" : "服务未提供可解释的原因。"));
        list.append(li);
      });
      section.append(list); target.append(section);
    }
    const temporary = payload.analysis_basis?.temporary_materials;
    if (Array.isArray(temporary) && temporary.length) {
      const section = node("section", "", "material-usage"); section.append(node("h3", "本次临时附件"));
      temporary.forEach(item => {
        const article = node("article"); article.append(node("b", item.filename));
        article.append(node("p", `${String(item.file_type || "").toUpperCase()} · 解析 ${item.character_count} 字 · 本次纳入 ${item.included_characters} 字 · ${item.status === "used" ? "已采用" : "未采用"}`));
        if (item.truncated) article.append(node("p", "本次仅使用了部分解析文本，请检查是否遗漏重要内容。", "task-reference-warning"));
        if (item.status === "unused") article.append(node("p", item.unused_reason === "context_limit_reached" ? "本次附件上下文已达到长度上限。" : item.unused_reason === "resume_not_selected" ? "这份简历未被选为本次使用版本，已排除。" : "服务未提供可解释的原因。"));
        (Array.isArray(item.warnings) ? item.warnings : []).forEach(value => article.append(node("p", value === "analysis context was truncated" ? "附件解析文本超出本次可用上下文，已截断。" : String(value), "hint")));
        section.append(article);
      }); target.append(section);
    }
    if (Array.isArray(payload.sources) && payload.sources.length) {
      const details = node("details"); details.append(node("summary", "本次来源清单"));
      payload.sources.forEach(source => {
        if (typeof source === "string") return details.append(node("p", source));
        if (!source || typeof source !== "object") return;
        const article = node("article"); article.append(node("b", source.title || source.filename || source.material_id || "其他来源"));
        if (Array.isArray(source.locators)) article.append(node("p", source.locators.join(" · ")));
        if (Array.isArray(source.excerpts)) source.excerpts.forEach(value => article.append(node("blockquote", String(value))));
        details.append(article);
      }); target.append(details);
    }
    const stages = {validating: "输入校验", parsing: "附件解析", retrieving: "材料检索", analyzing: "分析", completed: "完成", failed: "失败"};
    if (payload.analysis_stage === "completed" && Array.isArray(payload.analysis_stage_history)) target.append(node("p", `服务返回的处理记录：${payload.analysis_stage_history.map(value => stages[value] || "其他步骤").join(" → ")}`, "hint"));
    return Boolean(resume || usage || Array.isArray(temporary));
  };
  const feedback = target => {
    const mark = target.matches(".analysis-complete-mark") ? target : node("span", "✓", "success-feedback-mark");
    mark.setAttribute("aria-hidden", "true");
    if (mark !== target) {
      target.querySelector(".success-feedback-mark")?.remove();
      target.prepend(mark);
    }
    mark.getAnimations().forEach(animation => animation.cancel());
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches && document.visibilityState === "visible") {
      mark.animate([{transform: "scale(.9)"}, {transform: "scale(1.12)", offset: .5}, {transform: "scale(1)"}], {duration: 200, easing: "cubic-bezier(.23,1,.32,1)"});
    }
  };
  window.MakoView = Object.freeze({feedback, node, markdown, renderResult, analysisState, renderAnalysis, renderBasis, wait, upload, route});
})();
