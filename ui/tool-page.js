(() => {
  const page = document.getElementById("skill-workspace-view");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const seen = new Map();
  const reveals = [...page.querySelectorAll(".tool-reveal")];
  const accordionStates = new Map();
  let inputMethod = "pointer", typingTimer, typingFinish = () => {};
  document.addEventListener("pointerdown", () => { inputMethod = "pointer"; document.documentElement.dataset.motionInput = "pointer"; }, true);
  document.addEventListener("keydown", () => { inputMethod = "keyboard"; document.documentElement.dataset.motionInput = "keyboard"; }, true);

  // Native details retain keyboard and no-script behavior; only pointer toggles animate.
  page.querySelectorAll(".tool-accordion, .help-details").forEach(details => {
    const summary = details.querySelector(":scope > summary");
    const content = document.createElement("div");
    content.className = "accordion-content";
    [...details.children].filter(child => child !== summary).forEach(child => content.append(child));
    details.append(content);
  });
  document.addEventListener("click", event => {
      const summary = event.target.closest("summary");
      const details = summary?.parentElement;
      if (!details?.matches("main details") || event.target.closest("button, a, input, select")) return;
      event.preventDefault();
      const prior = accordionStates.get(details);
      const open = !(prior ? prior.open : details.open);
      const from = details.getBoundingClientRect().height;
      prior?.animation.cancel();
      accordionStates.delete(details);
      details.style.overflow = "";
      if (!event.detail || reduce.matches) { details.open = open; return; }
      details.open = true;
      const style = getComputedStyle(details);
      const to = open ? details.getBoundingClientRect().height : summary.getBoundingClientRect().height + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
      details.style.overflow = "clip";
      const animation = details.animate([{height: `${from}px`}, {height: `${to}px`}], {duration: 280, easing: "cubic-bezier(.23,1,.32,1)"});
      accordionStates.set(details, {animation, open});
      animation.onfinish = () => { details.open = open; details.style.overflow = ""; accordionStates.delete(details); };
  });
  const finishAccordions = () => {
    accordionStates.forEach(({animation, open}, details) => { animation.cancel(); details.open = open; details.style.overflow = ""; });
    accordionStates.clear();
  };
  const reveal = element => {
    const pending = element.classList.contains("tool-reveal-pending");
    element.classList.remove("tool-reveal-pending");
    observer.unobserve(element);
    const key = window.MakoApp.position().skill;
    seen.get(key)?.add(element);
    if (pending && !reduce.matches && inputMethod !== "keyboard") element.animate([{opacity: 0, transform: "translateY(24px)"}, {opacity: 1, transform: "none"}], {duration: 600, easing: "ease-out"});
  };
  const observer = new IntersectionObserver(entries => {
    if (!page.hidden) entries.filter(entry => entry.isIntersecting).forEach(entry => reveal(entry.target));
  }, {threshold: .05});
  const typePrompt = () => {
    typingFinish();
    const hint = document.getElementById("request-hint");
    const text = hint.querySelector(".sr-only")?.textContent || hint.textContent;
    const accessible = window.MakoView.node("span", text, "sr-only");
    const visual = window.MakoView.node("span", "", "typing-prompt");
    visual.setAttribute("aria-hidden", "true");
    hint.replaceChildren(accessible, visual);
    typingFinish = () => { clearTimeout(typingTimer); visual.textContent = text; };
    if (reduce.matches || inputMethod === "keyboard" || document.activeElement === document.getElementById("request") || document.getElementById("request").value) { typingFinish(); return; }
    const characters = Array.from(text); let index = 0;
    const tick = () => { visual.textContent = characters.slice(0, ++index).join(""); if (index < characters.length) typingTimer = setTimeout(tick, 60); };
    tick();
  };
  const summarize = () => {
    const resume = document.getElementById("analysis-resume-select");
    const mode = document.querySelector('input[name="personal-knowledge-mode"]:checked')?.value;
    const label = {auto: "自动查找补充材料", selected: "只使用指定材料", off: "不使用材料库"}[mode] || "沿用任务材料";
    document.getElementById("reference-summary").textContent = `${resume.selectedOptions[0]?.textContent || "请选择简历"} · ${label}`;
    const job = document.getElementById("job-select");
    document.getElementById("job-options-summary").textContent = document.querySelector('input[name="match-source"]:checked')?.value === "manual" ? "自行提供 JD · 展开编辑职位描述" : job.value ? job.selectedOptions[0].textContent : "常规方向分析 · 可展开选择具体岗位与信息范围";
  };
  const activate = () => {
    finishAccordions(); typingFinish(); observer.disconnect();
    document.getElementById("analysis-guide").open = false;
    const attachmentResume = document.getElementById("analysis-resume-file");
    document.getElementById("reference-options").open = !attachmentResume.hidden && !attachmentResume.value;
    const key = window.MakoApp.position().skill;
    if (!seen.has(key)) seen.set(key, new Set());
    reveals.forEach(element => {
      element.getAnimations().forEach(animation => animation.cancel());
      element.classList.toggle("tool-reveal-pending", !reduce.matches && inputMethod !== "keyboard" && !seen.get(key).has(element));
      observer.observe(element);
    });
    summarize(); typePrompt();
  };
  page.addEventListener("focusin", event => {
    const target = event.target.closest(".tool-reveal");
    if (target) { target.classList.remove("tool-reveal-pending"); target.getAnimations().forEach(animation => animation.cancel()); }
    if (event.target.matches("input, textarea")) typingFinish();
  });
  page.addEventListener("change", summarize);
  const stopMotion = () => { typingFinish(); finishAccordions(); reveals.forEach(element => { element.classList.remove("tool-reveal-pending"); element.getAnimations().forEach(animation => animation.cancel()); }); };
  reduce.addEventListener("change", stopMotion);
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopMotion(); });
  new MutationObserver(() => { if (page.hidden) stopMotion(); }).observe(page, {attributes: true, attributeFilter: ["hidden"]});
  if (!CSS.supports("animation-timeline: scroll(root block)")) {
    const progress = () => { const range = document.documentElement.scrollHeight - innerHeight; page.querySelector(".tool-scroll-progress span").style.transform = `scaleX(${range > 0 ? scrollY / range : 0})`; };
    addEventListener("scroll", progress, {passive: true}); addEventListener("resize", progress); progress();
  }
  window.MakoToolPage = Object.freeze({activate, summarize});
})();
