(() => {
  const categoryLabels = {
    resume: "简历",
    project: "项目文档",
    course: "课程材料",
    note: "求职笔记",
    other: "其他"
  };
  const fileTypeLabels = {txt: "TXT", md: "Markdown", pdf: "PDF", docx: "DOCX"};
  const indexLabels = {pending: "正在建立索引", ready: "索引就绪", failed: "索引失败"};
  const state = {
    loaded: false,
    loading: false,
    materials: [],
    selectedId: null,
    detailOffset: 0,
    previewFile: null,
    retryCreate: null,
    deleting: null
  };

  const fileInput = document.getElementById("knowledge-file");
  const fileStatus = document.getElementById("knowledge-file-status");
  const preview = document.getElementById("material-preview");
  const previewStats = document.getElementById("preview-stats");
  const previewWarnings = document.getElementById("preview-warnings");
  const previewExcerpts = document.getElementById("preview-excerpts");
  const list = document.getElementById("material-list");
  const detail = document.getElementById("material-detail");
  const message = document.getElementById("materials-message");
  const deleteDialog = document.getElementById("material-delete-dialog");
  const picker = document.getElementById("personal-material-picker");
  const pickerOptions = document.getElementById("personal-material-options");
  const pickerStatus = document.getElementById("personal-material-picker-status");
  const knowledgeHint = document.getElementById("personal-knowledge-hint");
  const resultSources = document.getElementById("personal-result-sources");

  const text = (tag, value, className = "") => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };

  const setMessage = (value = "", kind = "") => {
    message.textContent = value;
    message.className = `workspace-message${kind ? ` ${kind}` : ""}`;
  };

  const formatBytes = bytes => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const formatDate = value => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("zh-CN", {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"}).format(date);
  };

  const friendlyError = error => {
    const value = String(error?.message || error || "操作没有完成");
    const lower = value.toLowerCase();
    if (lower.includes("password") || lower.includes("encrypted")) return "这个 PDF 受密码保护，当前无法解析。";
    if (lower.includes("no extractable text") || lower.includes("no text")) return "文件中没有可提取的文本。扫描件需要 OCR，当前版本暂不支持。";
    if (lower.includes("extension") || lower.includes("unsupported") || lower.includes("macro")) return "文件格式或内部结构不受支持，请确认扩展名与文件内容一致。";
    if (lower.includes("10 mb") || lower.includes("too large") || lower.includes("exceeds") || lower.includes("pages")) return "文件超过当前解析限制，请缩小文件后重试。";
    if (lower.includes("utf-8")) return "TXT 和 Markdown 需要使用 UTF-8 编码。";
    if (lower.includes("another request") || lower.includes("发生变化")) return "材料已在其他窗口发生变化，已重新加载最新内容。请确认后重试。";
    if (lower.includes("索引") && lower.includes("删除")) return "索引服务暂时不可用，材料仍然完整保留，可以稍后重试删除。";
    return value;
  };

  const materialById = id => state.materials.find(item => item.material_id === id);

  const resetPreview = () => {
    state.previewFile = null;
    state.retryCreate = null;
    fileInput.value = "";
    preview.hidden = true;
    previewStats.replaceChildren();
    previewWarnings.replaceChildren();
    previewWarnings.hidden = true;
    previewExcerpts.replaceChildren();
    document.getElementById("material-save-status").textContent = "";
    fileStatus.textContent = "单个文件不超过 10 MB。PDF 需要文本层且最多 200 页，解析文本最多 1,000,000 字符。";
    fileStatus.classList.remove("error");
  };

  const renderPreview = payload => {
    preview.hidden = false;
    document.getElementById("preview-file-type").textContent = fileTypeLabels[payload.file_type] || payload.file_type;
    previewStats.replaceChildren();
    [["文件大小", formatBytes(payload.byte_size)], ["解析文本", `${payload.character_count.toLocaleString("zh-CN")} 字符`], ["引用位置", `${payload.section_count.toLocaleString("zh-CN")} 处`]].forEach(([label, value]) => {
      const item = document.createElement("div");
      item.append(text("span", label), text("strong", value));
      previewStats.appendChild(item);
    });
    previewWarnings.replaceChildren();
    payload.warnings.forEach(value => previewWarnings.appendChild(text("p", value)));
    previewWarnings.hidden = !payload.warnings.length;
    previewExcerpts.replaceChildren();
    payload.excerpts.forEach(item => {
      const article = document.createElement("article");
      article.append(text("span", item.locator_label, "source-locator"), text("p", item.text));
      previewExcerpts.appendChild(article);
    });
    const baseName = payload.original_filename.replace(/\.[^.]+$/, "");
    document.getElementById("material-title").value = baseName.slice(0, 200);
    fileStatus.textContent = `${payload.original_filename} 已完成解析。请检查预览，再选择名称和分类。`;
    preview.scrollIntoView({behavior: "smooth", block: "nearest"});
  };

  const previewFile = async file => {
    if (!file) return;
    state.previewFile = file;
    preview.hidden = true;
    fileStatus.classList.remove("error");
    fileStatus.textContent = "正在安全解析文件，预览不会保存材料…";
    const body = new FormData();
    body.append("file", file);
    try {
      const payload = await window.MakoWorkspace.fetch("/materials/preview", {method: "POST", body});
      renderPreview(payload);
    } catch (error) {
      state.previewFile = null;
      fileInput.value = "";
      fileStatus.textContent = friendlyError(error);
      fileStatus.classList.add("error");
    }
  };

  const renderPicker = () => {
    const selectedIds = new Set([...pickerOptions.querySelectorAll("input:checked")].map(input => input.value));
    const available = state.materials.filter(item => item.status === "active" && item.index_status === "ready");
    pickerOptions.replaceChildren();
    if (!available.length) {
      pickerOptions.appendChild(text("p", "当前没有可检索的个人材料。请先在个人材料库保存材料，或选择其他模式。", "picker-empty"));
      pickerStatus.textContent = "";
      return;
    }
    available.forEach(material => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = material.material_id;
      input.checked = selectedIds.has(material.material_id);
      const copy = document.createElement("span");
      copy.append(text("b", material.title), text("small", `${categoryLabels[material.category]} · ${fileTypeLabels[material.file_type]}`));
      label.append(input, copy);
      pickerOptions.appendChild(label);
    });
    pickerStatus.textContent = `可选择 ${available.length} 份材料，最多 20 份。`;
  };

  const renderList = () => {
    list.replaceChildren();
    const status = document.getElementById("material-status-filter").value;
    const category = document.getElementById("material-category-filter").value;
    const visible = state.materials.filter(item => (!status || item.status === status) && (!category || item.category === category));
    if (!visible.length) {
      const empty = document.createElement("div");
      empty.className = "workspace-empty material-list-empty";
      empty.append(text("span", "▤"), text("h3", "还没有符合条件的材料"), text("p", "选择文件完成预览，确认后才会保存到本机。"));
      list.appendChild(empty);
      renderPicker();
      return;
    }
    visible.forEach(material => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `material-list-item${material.material_id === state.selectedId ? " active" : ""}`;
      button.dataset.materialId = material.material_id;
      const heading = document.createElement("div");
      heading.append(text("h3", material.title), text("span", indexLabels[material.index_status] || material.index_status, `index-state ${material.index_status}`));
      button.append(heading, text("p", `${categoryLabels[material.category]} · ${fileTypeLabels[material.file_type]} · ${material.status === "active" ? "使用中" : "已停用"}`));
      list.appendChild(button);
    });
    renderPicker();
  };

  const loadMaterials = async ({quiet = false} = {}) => {
    if (state.loading) return;
    state.loading = true;
    if (!quiet) setMessage("正在读取本机个人材料…");
    try {
      const payload = await window.MakoWorkspace.fetch("/materials?limit=500");
      state.materials = payload.items;
      state.loaded = true;
      if (state.selectedId && !materialById(state.selectedId)) state.selectedId = null;
      renderList();
      if (state.selectedId) await loadDetail(state.selectedId, state.detailOffset);
      else detail.replaceChildren(emptyDetail());
      if (!quiet) setMessage();
    } catch (error) {
      setMessage(`${friendlyError(error)} 你可以保留当前文件并稍后重试。`, "error");
    } finally {
      state.loading = false;
    }
  };

  const emptyDetail = () => {
    const empty = document.createElement("div");
    empty.className = "workspace-empty";
    empty.append(text("span", "▤"), text("h3", "选择一份个人材料"), text("p", "这里会显示保存状态、引用位置和解析内容，不会执行材料中的链接或 HTML。"));
    return empty;
  };

  const renderDetail = payload => {
    const material = payload.material;
    detail.replaceChildren();
    const header = document.createElement("header");
    header.className = "material-detail-header";
    const heading = document.createElement("div");
    heading.append(text("h2", material.title), text("p", `${material.original_filename} · ${formatBytes(material.byte_size)}`));
    const states = document.createElement("div");
    states.className = "material-state-stack";
    states.append(text("span", material.status === "active" ? "使用中" : "已停用", `material-status ${material.status}`), text("span", indexLabels[material.index_status], `index-state ${material.index_status}`));
    header.append(heading, states);

    const meta = document.createElement("div");
    meta.className = "detail-meta material-meta";
    meta.append(text("span", categoryLabels[material.category]), text("span", fileTypeLabels[material.file_type]), text("span", `${material.character_count.toLocaleString("zh-CN")} 字符`), text("span", `${material.section_count.toLocaleString("zh-CN")} 个引用位置`), text("span", `更新于 ${formatDate(material.updated_at)}`));

    const controls = document.createElement("section");
    controls.className = "track-detail-section material-controls";
    controls.appendChild(text("h3", "材料设置"));
    const grid = document.createElement("div");
    grid.className = "material-control-grid";
    const titleLabel = document.createElement("label");
    titleLabel.append(text("span", "显示名称"));
    const titleInput = document.createElement("input");
    titleInput.id = "detail-material-title";
    titleInput.maxLength = 200;
    titleInput.value = material.title;
    titleLabel.appendChild(titleInput);
    const categoryLabel = document.createElement("label");
    categoryLabel.append(text("span", "分类"));
    const categorySelect = document.createElement("select");
    categorySelect.id = "detail-material-category";
    Object.entries(categoryLabels).forEach(([value, label]) => categorySelect.appendChild(new Option(label, value)));
    categorySelect.value = material.category;
    categoryLabel.appendChild(categorySelect);
    const statusLabel = document.createElement("label");
    statusLabel.append(text("span", "使用状态"));
    const statusSelect = document.createElement("select");
    statusSelect.id = "detail-material-status";
    statusSelect.append(new Option("使用中，可参与检索", "active"), new Option("已停用，不参与检索", "inactive"));
    statusSelect.value = material.status;
    statusLabel.appendChild(statusSelect);
    const save = text("button", "保存设置", "primary");
    save.type = "button";
    save.dataset.materialOperation = "save";
    save.dataset.materialId = material.material_id;
    grid.append(titleLabel, categoryLabel, statusLabel, save);
    controls.appendChild(grid);

    if (material.index_status === "failed") {
      const recovery = document.createElement("div");
      recovery.className = "index-recovery";
      recovery.append(text("p", "材料已经保存，但当前无法用于检索。可以重新建立索引，原文不会被改写。"));
      const reindex = text("button", "重新建立索引", "secondary");
      reindex.type = "button";
      reindex.dataset.materialOperation = "reindex";
      reindex.dataset.materialId = material.material_id;
      recovery.appendChild(reindex);
      controls.appendChild(recovery);
    }

    const content = document.createElement("section");
    content.className = "track-detail-section material-sections";
    const contentHeading = document.createElement("div");
    contentHeading.className = "workspace-card-heading";
    contentHeading.append(text("h3", `解析内容 · ${material.section_count} 处`), text("span", "引用位置随原文保留", "trace-note"));
    content.appendChild(contentHeading);
    payload.sections.forEach(section => {
      const article = document.createElement("article");
      article.className = "material-section";
      article.append(text("span", section.locator_label, "source-locator"), text("p", section.text));
      content.appendChild(article);
    });
    const pager = document.createElement("div");
    pager.className = "material-pager";
    const previous = text("button", "上一页", "secondary");
    previous.type = "button";
    previous.disabled = payload.section_offset === 0;
    previous.dataset.materialPage = String(Math.max(0, payload.section_offset - payload.section_limit));
    const page = text("span", `第 ${Math.floor(payload.section_offset / payload.section_limit) + 1} 页`);
    const next = text("button", "下一页", "secondary");
    next.type = "button";
    next.disabled = !payload.has_more;
    next.dataset.materialPage = String(payload.section_offset + payload.section_limit);
    pager.append(previous, page, next);
    content.appendChild(pager);

    const danger = document.createElement("section");
    danger.className = "track-detail-section material-danger-zone";
    danger.append(text("p", "永久删除会同时移除解析文本与个人材料索引，不影响其他工作区数据。"));
    const remove = text("button", "查看删除影响", "mini-button danger");
    remove.type = "button";
    remove.dataset.materialOperation = "delete";
    remove.dataset.materialId = material.material_id;
    danger.appendChild(remove);
    detail.append(header, meta, controls, content, danger);
  };

  const loadDetail = async (materialId, offset = 0) => {
    detail.replaceChildren();
    detail.appendChild(text("p", "正在读取材料内容…", "material-loading"));
    try {
      const payload = await window.MakoWorkspace.fetch(`/materials/${encodeURIComponent(materialId)}?section_offset=${offset}&section_limit=20`);
      state.selectedId = materialId;
      state.detailOffset = offset;
      const index = state.materials.findIndex(item => item.material_id === materialId);
      if (index >= 0) state.materials[index] = payload.material;
      renderList();
      renderDetail(payload);
    } catch (error) {
      detail.replaceChildren(text("p", `${friendlyError(error)} 请重新选择材料后重试。`, "workspace-message error"));
    }
  };

  const savePreview = async () => {
    const status = document.getElementById("material-save-status");
    const titleValue = document.getElementById("material-title").value.trim();
    if (!state.previewFile || !titleValue) {
      status.textContent = "请保留待保存文件并填写材料名称。";
      status.className = "status-message error";
      return;
    }
    const save = document.getElementById("save-material");
    save.disabled = true;
    status.textContent = "正在保存并建立索引…";
    status.className = "status-message busy";
    const signature = `${state.previewFile.name}|${state.previewFile.size}|${state.previewFile.lastModified}|${titleValue}|${document.getElementById("material-category").value}`;
    const idempotencyKey = state.retryCreate?.signature === signature ? state.retryCreate.key : `material_${crypto.randomUUID().replaceAll("-", "")}`;
    state.retryCreate = {signature, key: idempotencyKey};
    const body = new FormData();
    body.append("file", state.previewFile);
    body.append("title", titleValue);
    body.append("category", document.getElementById("material-category").value);
    try {
      const payload = await window.MakoWorkspace.fetch("/materials", {method: "POST", headers: {"Idempotency-Key": idempotencyKey}, body});
      state.retryCreate = null;
      const saved = payload.material;
      resetPreview();
      await loadMaterials({quiet: true});
      state.selectedId = saved.material_id;
      await loadDetail(saved.material_id);
      setMessage(payload.indexed ? "材料已保存，现在可以参与相关分析。" : "材料已保存，但索引尚未建立。可以在详情中重试。", payload.indexed ? "success" : "error");
    } catch (error) {
      status.textContent = `${friendlyError(error)} 文件和预览仍然保留，可以检查后重试。`;
      status.className = "status-message error";
      await loadMaterials({quiet: true});
    } finally {
      save.disabled = false;
    }
  };

  const patchMaterial = async materialId => {
    const material = materialById(materialId);
    if (!material) return;
    const titleValue = document.getElementById("detail-material-title").value.trim();
    if (!titleValue) throw new Error("材料名称不能为空。 ");
    await window.MakoWorkspace.fetch(`/materials/${encodeURIComponent(materialId)}`, {
      method: "PATCH",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({revision: material.revision, title: titleValue, category: document.getElementById("detail-material-category").value, status: document.getElementById("detail-material-status").value})
    });
    await loadMaterials({quiet: true});
    setMessage("材料设置已保存。", "success");
  };

  const reindexMaterial = async materialId => {
    const material = materialById(materialId);
    if (!material) return;
    setMessage("正在重新建立材料索引…");
    const payload = await window.MakoWorkspace.fetch(`/materials/${encodeURIComponent(materialId)}/reindex`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({revision: material.revision})
    });
    await loadMaterials({quiet: true});
    setMessage(payload.indexed ? "材料索引已恢复。" : "索引仍未建立，材料原文已经保留，可以稍后重试或删除。", payload.indexed ? "success" : "error");
  };

  const openDeleteDialog = async materialId => {
    const material = materialById(materialId);
    if (!material) return;
    const impact = await window.MakoWorkspace.fetch(`/materials/${encodeURIComponent(materialId)}/deletion-impact`);
    state.deleting = {material, impact};
    document.getElementById("material-delete-impact").textContent = `“${material.title}”包含 ${impact.sections} 个引用位置和 ${impact.vector_chunks} 个索引块。`;
    document.getElementById("material-delete-status").textContent = "";
    deleteDialog.showModal();
  };

  const deleteMaterial = async () => {
    if (!state.deleting) return;
    const {material} = state.deleting;
    const status = document.getElementById("material-delete-status");
    const button = document.getElementById("confirm-delete-material");
    button.disabled = true;
    status.textContent = "正在永久删除材料和索引…";
    try {
      await window.MakoWorkspace.fetch(`/materials/${encodeURIComponent(material.material_id)}?revision=${material.revision}&confirmation=DELETE_PERSONAL_MATERIAL`, {method: "DELETE"});
      deleteDialog.close();
      state.deleting = null;
      state.selectedId = null;
      state.detailOffset = 0;
      await loadMaterials({quiet: true});
      setMessage("个人材料及对应索引已永久删除。", "success");
    } catch (error) {
      status.textContent = friendlyError(error);
      status.className = "status-message error";
      await loadMaterials({quiet: true});
    } finally {
      button.disabled = false;
    }
  };

  const selection = () => {
    const mode = document.querySelector('input[name="personal-knowledge-mode"]:checked')?.value || "auto";
    const ids = [...pickerOptions.querySelectorAll("input:checked")].map(input => input.value);
    if (mode === "selected" && !ids.length) throw new Error("请选择至少一份可以检索的个人材料，或切换到其他模式。");
    if (ids.length > 20) throw new Error("每次最多选择 20 份个人材料。");
    return {mode, ids: mode === "selected" ? ids : []};
  };

  const search = async query => {
    const current = selection();
    if (current.mode === "off") return [];
    const payload = await window.MakoWorkspace.fetch("/materials/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query, material_ids: current.ids, top_k: 5})
    });
    return payload.items;
  };

  const renderSources = (sources, used, mode = selection().mode) => {
    resultSources.replaceChildren();
    if (mode === "off") {
      resultSources.hidden = true;
      return;
    }
    resultSources.hidden = false;
    if (!used || !sources?.length) {
      resultSources.className = "personal-result-sources no-match";
      resultSources.append(text("h3", "个人材料未参与本次分析"), text("p", "没有检索到足够相关的内容，本次结果只使用当前输入和现有求职信息。"));
      return;
    }
    resultSources.className = "personal-result-sources";
    resultSources.appendChild(text("h3", "本次使用的个人材料"));
    sources.forEach(source => {
      const article = document.createElement("article");
      const heading = document.createElement("div");
      heading.append(text("b", source.title), text("span", categoryLabels[source.category] || source.category));
      article.appendChild(heading);
      const locators = source.locators || [source.locator_label].filter(Boolean);
      article.appendChild(text("p", locators.join(" · "), "source-locator-line"));
      const excerpts = source.excerpts || [source.excerpt].filter(Boolean);
      excerpts.slice(0, 3).forEach(value => article.appendChild(text("blockquote", value)));
      resultSources.appendChild(article);
    });
  };

  const updateMode = () => {
    const mode = document.querySelector('input[name="personal-knowledge-mode"]:checked')?.value || "auto";
    picker.hidden = mode !== "selected";
    if (mode === "selected") {
      if (!state.loaded) loadMaterials({quiet: true});
      renderPicker();
      knowledgeHint.textContent = "本次只会检索你勾选的材料；停用或索引失败的材料不会出现在选择列表中。";
    } else if (mode === "off") {
      knowledgeHint.textContent = "本次分析不会读取个人材料库。当前输入仍按原有流程处理。";
    } else {
      knowledgeHint.textContent = "Mako 会自动查找相关内容；如果没有达到相关性要求，本次分析不会引用个人材料。";
    }
    const confirmation = document.getElementById("confirm-input");
    if (confirmation.checked) {
      confirmation.checked = false;
      confirmation.dispatchEvent(new Event("change"));
    }
  };

  fileInput.addEventListener("change", () => previewFile(fileInput.files[0]));
  document.getElementById("discard-material-preview").addEventListener("click", resetPreview);
  document.getElementById("save-material").addEventListener("click", savePreview);
  document.getElementById("material-status-filter").addEventListener("change", renderList);
  document.getElementById("material-category-filter").addEventListener("change", renderList);
  list.addEventListener("click", event => {
    const target = event.target.closest("[data-material-id]");
    if (target) loadDetail(target.dataset.materialId);
  });
  detail.addEventListener("click", async event => {
    const page = event.target.closest("[data-material-page]");
    if (page && !page.disabled) return loadDetail(state.selectedId, Number(page.dataset.materialPage));
    const target = event.target.closest("[data-material-operation]");
    if (!target) return;
    target.disabled = true;
    try {
      if (target.dataset.materialOperation === "save") await patchMaterial(target.dataset.materialId);
      if (target.dataset.materialOperation === "reindex") await reindexMaterial(target.dataset.materialId);
      if (target.dataset.materialOperation === "delete") await openDeleteDialog(target.dataset.materialId);
    } catch (error) {
      setMessage(friendlyError(error), "error");
      await loadMaterials({quiet: true});
    } finally {
      target.disabled = false;
    }
  });
  document.getElementById("material-delete-form").addEventListener("submit", event => {
    event.preventDefault();
    if (event.submitter?.value === "cancel") {
      state.deleting = null;
      deleteDialog.close();
      return;
    }
    deleteMaterial();
  });
  document.getElementById("export-materials").addEventListener("click", async () => {
    try {
      const payload = await window.MakoWorkspace.fetch("/materials/export");
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json;charset=utf-8"});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `mako-personal-materials-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage("个人材料已导出。", "success");
    } catch (error) {
      setMessage(friendlyError(error), "error");
    }
  });
  document.querySelectorAll('input[name="personal-knowledge-mode"]').forEach(input => input.addEventListener("change", updateMode));
  pickerOptions.addEventListener("change", event => {
    const count = pickerOptions.querySelectorAll("input:checked").length;
    if (count > 20) {
      event.target.checked = false;
      pickerStatus.textContent = "每次最多选择 20 份材料。";
    }
    const confirmation = document.getElementById("confirm-input");
    if (confirmation.checked) {
      confirmation.checked = false;
      confirmation.dispatchEvent(new Event("change"));
    }
  });

  window.MakoMaterials = Object.freeze({
    load: () => loadMaterials(),
    selection,
    search,
    renderSources,
    clearSources: () => {
      resultSources.replaceChildren();
      resultSources.hidden = true;
    }
  });
  updateMode();
})();
