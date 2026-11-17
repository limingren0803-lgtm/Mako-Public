(() => {
  "use strict";
  const node = window.MakoView.node;
  const labels = {career_match: "方向匹配", career_jd: "JD 分析", career_resume: "简历优化", career_interview: "面试准备", career_planning: "行动规划", clarify: "补充信息"};
  const KEY = "mako.first-diagnosis.v1", PREF = "mako.first-diagnosis.skip-welcome", WEEK = 7 * 86400000;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const fresh = () => ({stage:"welcome", concern:"", jd:"", duration:"", replies:"", file:null, preview:null, libraryId:"", library:[], result:null, keep:false, auto:false, retain:false, receivedAt:0, requestKey:null, saveAttempt:null, error:""});
  let state = fresh(), pending = null, baseline = null, blocked = false, loading = false, saving = false, reading = false, started = 0, clock;
  const temporaryResumes = new Map();
  const dialog = node("dialog", "", "workspace-dialog diagnosis-dialog");
  dialog.id="first-diagnosis-dialog"; dialog.setAttribute("aria-labelledby","diagnosis-title");
  const launcher=node("button","初步诊断","secondary diagnosis-launcher"); launcher.type="button";
  const continuation=node("aside","","diagnosis-continuation"); continuation.hidden=true; continuation.setAttribute("aria-live","polite");
  const notice=node("p","","diagnosis-notice"); notice.hidden=true; notice.setAttribute("role","status");
  document.body.append(dialog,continuation,notice);
  document.getElementById("workspace-view-title").parentElement.append(launcher);
  const notify=message=>{notice.textContent=message;notice.hidden=false;clearTimeout(notify.timer);notify.timer=setTimeout(()=>{notice.hidden=true;},10000);};
  const busy=()=>loading||saving||reading;
  const fetchAPI=(path,options)=>window.MakoWorkspace.fetch(path,options);
  const button=(label,action,style="secondary",disabled=false)=>`<button type="button" class="${style}" data-diagnosis-action="${action}" ${disabled?'disabled':''}>${esc(label)}</button>`;
  const check=(field,label,description="",disabled=false)=>`<label class="diagnosis-check"><input type="checkbox" data-diagnosis-field="${field}" ${state[field]?'checked':''} ${disabled?'disabled':''}><span>${esc(label)}${description?`<small>${esc(description)}</small>`:''}</span></label>`;
  function store() {
    if(!state.retain || blocked || pending)return;
    try {
      if(localStorage.getItem(KEY)!==baseline)throw new Error("另一页面修改了保留内容，本页自动保留已暂停。");
      // Explicit allowlist: no File, parsed resume, material excerpts or library list.
      const usage=state.result?.resume_usage;
      const value={version:1,expires:Math.min(Date.now()+WEEK,(state.receivedAt||Date.now())+WEEK),concern:state.concern,jd:state.jd,duration:state.duration,replies:state.replies,result:state.result?{response:state.result.response,response_complete:state.result.response_complete!==false,diagnosis:state.result.diagnosis,diagnosis_receipt:state.result.diagnosis_receipt,resume_usage:usage?{source:usage.source,material_id:usage.material_id,content_sha256:usage.content_sha256}:null}:null,receivedAt:state.receivedAt,saveAttempt:state.saveAttempt};
      const raw=JSON.stringify(value);decode(raw);localStorage.setItem(KEY,raw);baseline=raw;
    }catch(error){blocked=true;notify(`${error.message||"本机存储不可用"} 当前页面内容仍在，请保留页面。`);}
  }
  function decode(raw){
    if(typeof raw!=="string"||raw.length>200000)throw new Error("首次诊断记录超出范围");
    const v=JSON.parse(raw), bounded=(s,n)=>typeof s==="string"&&s.length<=n;
    if(v.version!==1||!Number.isFinite(v.expires)||v.expires>Date.now()+WEEK+300000||!bounded(v.concern,500)||!bounded(v.jd,4000)||!bounded(v.duration,100)||!bounded(v.replies,500)||!Number.isFinite(v.receivedAt))throw new Error("首次诊断记录无法识别");
    if(v.result){
      if(!bounded(v.result.response,100000)||![true,false].includes(v.result.response_complete)||!(v.result.diagnosis_receipt===undefined||bounded(v.result.diagnosis_receipt,60000)))throw new Error("诊断结果无法识别");
      const b=v.result.diagnosis;
      const usage=v.result.resume_usage;if(usage&&(!['library','temporary'].includes(usage.source)||!(usage.material_id===null||bounded(usage.material_id,128))||!(usage.content_sha256===undefined||/^[a-f0-9]{64}$/.test(usage.content_sha256))))throw new Error("简历来源记录无法识别");
      if(b&&(!bounded(b.priority,60)||!Array.isArray(b.reasons)||b.reasons.length>2||!b.reasons.every(r=>bounded(r,150))||!Object.hasOwn(labels,b.next_intent)||!bounded(b.next_step,60)||!bounded(b.details,2000)))throw new Error("诊断摘要无法识别");
    }
    if(v.saveAttempt && (!bounded(v.saveAttempt.receipt,60000)||typeof v.saveAttempt.keep!=="boolean"||typeof v.saveAttempt.auto!=="boolean"||!bounded(v.saveAttempt.materialKey,128)||!(v.saveAttempt.materialId===null||bounded(v.saveAttempt.materialId,128))))throw new Error("保存记录无法识别");
    return v;
  }
  function erase(){try{localStorage.removeItem(KEY);baseline=null;pending=null;state.retain=false;blocked=false;notify("已清除首次诊断的本机记录；当前页面、任务和材料库不受影响。");}catch{notify("浏览器未允许清除本机记录，请在站点设置中清除。");}updateContinuation();}
  function updateContinuation(){
    continuation.hidden=dialog.open||(!pending&&["welcome","saved"].includes(state.stage));
    if(continuation.hidden)return;
    const title=pending?"有上次保留的初步诊断":loading?"初步诊断进行中":saving?"正在保存任务":state.result?.diagnosis?"初步判断已完成":"继续初步诊断";
    continuation.innerHTML=`<b>${title}</b><p>${loading?'请保留本页面，可继续浏览工作台。':pending?'由你选择恢复，不会自动分析。':'尚未保存为任务'}</p>${button(pending?'恢复查看':loading?'查看进度':state.result?'查看初步判断':'继续填写',pending?'restore':'resume')}`;
  }
  const retention=()=>`<details class="diagnosis-details"><summary>刷新后的保留设置</summary><div>${check('retain','允许此浏览器在刷新后恢复','保留输入和判断 7 天，可能含必要摘录；不保留原始简历或完整解析文本。')}${button('清除本次保留','erase','text-button')}</div></details>`;
  function fileArea(){
    const file=state.file;
    const chosen=state.library.find(m=>m.material_id===state.libraryId);
    return `<div class="field"><label class="diagnosis-label" for="diagnosis-library">简历来源</label><select id="diagnosis-library" ${reading?'disabled':''}><option value="">本次上传，不存入材料库</option>${state.library.map(m=>`<option value="${esc(m.material_id)}" ${m.material_id===state.libraryId?'selected':''}>${esc(m.title)}</option>`).join('')}</select></div>${state.libraryId?`<p class="hint">已选择：${esc(chosen?.title||'请重新选择可用版本')}。这份简历原本已在材料库，保存任务时只引用。</p>`:`<div class="upload-zone diagnosis-upload"><label for="diagnosis-file">${file?'更换简历文件':'选择或拖入简历'}</label><input id="diagnosis-file" type="file" accept=".pdf,.docx,.txt,.md" ${reading?'disabled':''}><p class="hint">PDF、DOCX、TXT、Markdown · 最大 10 MB · 不支持扫描件</p></div>${file?`<div class="diagnosis-file"><b>${esc(file.name)}</b>${button('移除','remove','text-button',reading)}</div>`:''}${state.preview?`<details class="diagnosis-details"><summary>已读取 · 查看解析节选</summary><div>${state.preview.excerpts.map(p=>`<p>${esc(p.text)}</p>`).join('')}<p class="hint">节选不能替代完整简历；分析使用原文件解析内容。</p></div></details>`:reading?'<p role="status">正在读取简历…</p>':''}`}`;
  }
  function render(){
    let title="初步判断",subtitle="尚未保存为任务",body="",footer="";
    const error=state.error?`<p class="diagnosis-error" role="status">${esc(state.error)}</p>`:"";
    if(state.stage==='welcome'){
      title="第一次使用 Mako 工作台吗？";subtitle="可以先做一次简短诊断，看看当前求职最值得优先解决的问题。";
      body=`<div class="diagnosis-welcome-actions">${button('第一次，带我开始','materials','primary')}${button('用过了，进入工作台','close')}</div><label class="diagnosis-check"><input type="checkbox" id="diagnosis-no-remind"><span>以后不再提醒</span></label>`;
    }else if(state.stage==='materials'){
      title="先看看求职卡在哪里";subtitle="先说说困扰，再选一份简历；没有 JD 也可以开始。";
      body=`<label class="diagnosis-label" for="diagnosis-concern">你现在最想解决什么？</label><textarea id="diagnosis-concern" data-diagnosis-field="concern" maxlength="500" placeholder="例如：投了很多没有回应，不知道是简历还是方向的问题。">${esc(state.concern)}</textarea>${error}${fileArea()}<details class="diagnosis-details"><summary>补充投递情况（选填）</summary><div><label class="diagnosis-label" for="diagnosis-jd">目标岗位或 JD</label><textarea id="diagnosis-jd" data-diagnosis-field="jd" maxlength="4000">${esc(state.jd)}</textarea><label class="diagnosis-label" for="diagnosis-duration">投递多久了？</label><input id="diagnosis-duration" data-diagnosis-field="duration" maxlength="100" value="${esc(state.duration)}"><label class="diagnosis-label" for="diagnosis-replies">收到过哪些回应？</label><textarea id="diagnosis-replies" data-diagnosis-field="replies" maxlength="500">${esc(state.replies)}</textarea></div></details>${retention()}`;
      footer=button('开始初步诊断','analyze','primary',reading||!state.concern.trim()||!(state.libraryId||state.preview));
    }else if(loading){title="正在分析你的求职情况";subtitle="先找到最值得优先解决的问题。";body='<div class="diagnosis-wait"><span class="diagnosis-spinner" aria-hidden="true"></span><h3>正在整理材料与问题</h3><p id="diagnosis-elapsed" role="status"></p><p class="hint">临时分析，不写入对话记忆或材料库。</p></div>';footer=button('暂时收起','close');
    }else if(state.result?.diagnosis){
      const b=state.result.diagnosis,locked=Boolean(state.saveAttempt);
      body=`${error}<div class="diagnosis-priority"><span>优先检查</span><h3>${esc(b.priority)}</h3></div><ul class="diagnosis-reasons">${b.reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul><h3>下一步：${esc(labels[b.next_intent])}</h3><p>${esc(b.next_step)}</p><details class="diagnosis-details"><summary>查看判断依据与边界</summary><div><p class="diagnosis-preline">${esc(b.details)}</p></div></details>${!locked?button('修改材料','materials','text-button'):''}${retention()}`;
      footer=`${state.libraryId?'<p class="hint">所选简历已在材料库；当前任务将引用该版本，不重复导入。</p>':check('keep','同时保留本次简历，方便下次继续','存入个人材料库并由当前任务引用，不保留原始文件。',saving||locked)}${b.next_intent!=='clarify'?check('auto',`保存后直接进入${labels[b.next_intent]}`,'只打开工具，点击开始后才分析。',saving||locked):''}<div class="diagnosis-actions">${button('暂不保存，返回工作台','close','text-button',saving)}${button(saving?'正在保存…':locked?'重试保存':'保存为任务并继续','save','primary',saving)}</div>`;
    }else{title=state.result?'部分内容已生成':'这次诊断未能完成';subtitle="本次输入和材料仍在，可以直接重试。";body=`${error}${state.result?`<p>结果尚未完整生成，暂不能保存为完整判断。</p><details class="diagnosis-details"><summary>查看已返回内容</summary><div class="diagnosis-preline">${esc(state.result.response)}</div></details>`:''}`;footer=`${button('修改材料','materials')}${button('重新尝试','analyze','primary')}`;}
    if(state.result?.diagnosis&&state.keep&&!state.libraryId&&!state.file&&!state.saveAttempt?.materialId)body+=`<p class="hint">刷新后请重新选择原简历；会核对文件指纹，不会重新分析。</p>${fileArea()}`;
    dialog.innerHTML=`<header class="diagnosis-header"><img src="assets/mako-icon.png" alt="" width="60" height="60"><div><h2 id="diagnosis-title" tabindex="-1">${title}</h2><p>${subtitle}</p></div><button class="text-button diagnosis-close" data-diagnosis-action="close" aria-label="收起初步诊断">×</button></header><section class="diagnosis-body">${body}</section>${footer?`<footer class="diagnosis-footer">${footer}</footer>`:''}`;
    const input=dialog.querySelector('#diagnosis-file');if(input){input.addEventListener('change',()=>receiveFile(input.files[0]));window.MakoView.upload(input,receiveFile,message=>{state.error=message;render();});}
    updateContinuation();tick();
  }
  function tick(){const el=document.getElementById('diagnosis-elapsed');if(el)el.textContent=`已用时 ${Math.floor((Date.now()-started)/1000)} 秒`;}
  function open(){if(document.querySelector('dialog[open]')&&!dialog.open){notify('请先关闭当前窗口，再查看初步诊断。');return;}render();if(!dialog.open)dialog.showModal();document.getElementById('diagnosis-title').focus({preventScroll:true});updateContinuation();}
  function close(){dialog.close();updateContinuation();launcher.focus({preventScroll:true});}
  async function receiveFile(file){
    if(file&&state.result?.diagnosis&&state.keep){
      if(file.size>10*1024*1024){state.error='请选择不超过 10 MB 的原简历。';render();return;}
      const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))].map(n=>n.toString(16).padStart(2,'0')).join('');
      if(digest!==state.result.resume_usage?.content_sha256){state.error='这不是诊断时的原简历，未保存该文件；请重新选择原文件。';render();return;}
    }
    return readFile(file);
  }
  async function materials(){if(busy()||state.saveAttempt)return;state.stage='materials';state.error='';state.requestKey=null;state.result=null;state.receivedAt=0;open();try{const list=await fetchAPI('/materials?category=resume&status=active&limit=500');state.library=list.items.filter(m=>m.index_status==='ready');if(!state.library.some(m=>m.material_id===state.libraryId))state.libraryId='';if(dialog.open)render();}catch(e){state.error=e.message;if(dialog.open)render();}store();}
  async function readFile(file){if(!file||busy())return;state.file=file;state.preview=null;state.libraryId='';state.requestKey=null;state.error='';if(file.size>10*1024*1024||! /\.(pdf|docx|txt|md)$/i.test(file.name)){state.error='请选择不超过 10 MB 的 PDF、DOCX、TXT 或 Markdown 文件。';render();return;}reading=true;render();try{const body=new FormData();body.append('file',file);state.preview=await fetchAPI('/materials/preview',{method:'POST',body});}catch(e){state.error=window.MakoMaterials.friendlyError(e);}finally{reading=false;if(dialog.open)render();}}
  async function analyze(){
    if(busy()||!window.MakoApp.canSwitch())return;
    if(!state.concern.trim()||!(state.libraryId||state.file&&state.preview)){state.error='请填写问题并选择可用简历。刷新后需重新选择临时文件。';state.stage='materials';open();return;}
    const payload={message:[state.concern.trim(),state.jd&&`目标岗位 / JD：${state.jd}`,state.duration&&`投递时间：${state.duration}`,state.replies&&`投递回应：${state.replies}`].filter(Boolean).join('\n'),career_intent:'career_profile',first_visit:true,personal_knowledge_mode:'off',memory_mode:'none',include_action_candidates:false,resume_source:state.libraryId?'library':'temporary',...(state.libraryId?{resume_material_id:state.libraryId}:{temporary_resume_filename:state.file.name})};
    const key=state.requestKey||`diagnosis_${crypto.randomUUID().replaceAll('-','')}`;state.requestKey=key;state.error='';state.stage='loading';loading=true;started=Date.now();open();clock=setInterval(tick,1000);
    try{let body, path;if(state.libraryId){body=JSON.stringify(payload);path='/analyze';}else{body=new FormData();body.append('payload',JSON.stringify(payload));body.append('files',state.file);path='/analyze/files';}
      state.result=await fetchAPI(path,{method:'POST',headers:{'Idempotency-Key':key,...(state.libraryId?{'Content-Type':'application/json'}:{})},body});state.receivedAt=Date.now();state.stage=state.result.diagnosis?'result':'partial';state.error=state.result.diagnosis_error||'';if(!state.result.diagnosis)state.requestKey=null;
    }catch(e){state.stage='failure';state.error=e.message||'连接中断，可重试找回本次请求。';if(e.status)state.requestKey=null;}
    finally{loading=false;clearInterval(clock);store();if(dialog.open)render();updateContinuation();}
  }
  async function save(){
    if(busy()||!state.result?.diagnosis_receipt)return;
    const attempt=state.saveAttempt||{receipt:state.result.diagnosis_receipt,keep:state.keep,auto:state.auto,materialKey:`diagnosis_material_${crypto.randomUUID().replaceAll('-','')}`,materialId:state.libraryId||null,indexed:Boolean(state.libraryId)};
    if(attempt.keep&&!attempt.materialId&&!state.file){state.error='刷新后需要重新选择原简历才能保留，或在首次保存前取消保留简历。';render();return;}
    state.saveAttempt=attempt;saving=true;state.error='';store();render();
    try{
      if(attempt.keep&&!attempt.materialId){const body=new FormData();body.append('file',state.file);body.append('title',state.file.name.slice(0,200));body.append('category','resume');body.append('set_current_if_missing','false');const saved=await fetchAPI('/materials',{method:'POST',headers:{'Idempotency-Key':attempt.materialKey},body});attempt.materialId=saved.material.material_id;attempt.indexed=saved.indexed;store();if(!saved.indexed)throw new Error('简历已保留到材料库，但索引未完成；点击重试保存会重建索引后继续。');}
      if(attempt.keep&&attempt.materialId&&!attempt.indexed){const current=await fetchAPI(`/materials/${encodeURIComponent(attempt.materialId)}`);const material=current.material;if(material.index_status!=='ready'){const indexed=await fetchAPI(`/materials/${encodeURIComponent(attempt.materialId)}/reindex`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:material.revision})});if(!indexed.indexed)throw new Error('简历已保留，索引仍未完成，可稍后重试。');}attempt.indexed=true;store();}
      const item=await fetchAPI('/diagnoses/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation:'SAVE_DIAGNOSIS_TO_TASK',receipt:attempt.receipt,resume_material_id:attempt.materialId})});
      if(state.file&&!item.task.resume_material_id)temporaryResumes.set(item.task.task_id,state.file);
      state.stage='saved';state.saveAttempt=null;state.retain=false;try{localStorage.removeItem(KEY);baseline=null;}catch{notify('任务已保存，但浏览器未允许清除本机副本，请在保留设置中清除。');}
      saving=false;close();await window.MakoTasks.acceptDiagnosis(item,attempt.auto&&state.result.diagnosis.next_intent!=='clarify'?state.result.diagnosis.next_intent:null);notify('任务已创建，初步判断已保存。');
    }catch(e){if(state.stage==='saved')notify(`任务已保存，后续页面暂未打开：${e.message}。可从求职任务继续。`);else state.error=`${attempt.materialId&&attempt.keep?'简历已保留到材料库。':''}暂未确认任务保存成功：${e.detail||e.message||'请重试找回同一次保存'}。不会重新分析。`;}
    finally{saving=false;store();if(dialog.open)render();updateContinuation();}
  }
  const toolDialog=node('dialog','','workspace-dialog diagnosis-tool-dialog');toolDialog.setAttribute('aria-label','当前任务的分析工具');
  const toolClose=node('button','返回任务','secondary diagnosis-tool-close');toolClose.type='button';toolDialog.append(toolClose);document.body.append(toolDialog);
  const skillView=document.getElementById('skill-workspace-view'),anchor=document.createComment('task tool original location');skillView.before(anchor);
  let leavingTool=false;
  function leaveTool(){if(!toolDialog.open)return;leavingTool=true;anchor.after(skillView);toolDialog.close();}
  function closeTool(){if(!window.MakoApp.canSwitch())return;toolDialog.close();}
  toolClose.addEventListener('click',closeTool);toolDialog.addEventListener('cancel',e=>{if(!window.MakoApp.canSwitch())e.preventDefault();});
  toolDialog.addEventListener('close',()=>{anchor.after(skillView);if(leavingTool){leavingTool=false;return;}window.MakoWorkspace.showPage('tasks');});
  async function wrapTool(item){
    toolDialog.querySelector('.diagnosis-tool-context')?.remove();
    const context=node('section','','diagnosis-tool-context');context.append(node('b','已带入的初步判断'),node('p',item.task.initial_diagnosis.priority),node('p',item.task.initial_diagnosis.next_step,'hint'));toolClose.after(context);
    toolDialog.append(skillView);skillView.hidden=false;if(!toolDialog.open)toolDialog.showModal();const nav=document.querySelector('[data-workspace-view="tasks"]');nav.classList.add('active');nav.setAttribute('aria-current','page');
    const file=temporaryResumes.get(item.task.task_id);
    if(!file&&!item.task.resume_material_id)context.append(node('p','此前未将简历存入材料库；若下方未带入临时简历，请重新选择文件后再分析。','hint'));
    if(file&&!item.task.resume_material_id){try{await window.MakoApp.acceptTemporaryResume(file);temporaryResumes.delete(item.task.task_id);}catch(e){notify(e.message);}}
    window.MakoToolPage?.summarize();
  }
  async function action(name){
    if(name==='close')return close();if(name==='resume')return open();if(name==='materials')return materials();if(name==='analyze')return analyze();if(name==='save')return save();if(name==='erase'){erase();render();return;}
    if(name==='remove'&&!busy()){state.file=null;state.preview=null;state.requestKey=null;render();return;}
    if(name==='restore'&&pending){const v=pending;pending=null;state={...fresh(),concern:v.concern,jd:v.jd,duration:v.duration,replies:v.replies,result:v.result,receivedAt:v.receivedAt,saveAttempt:v.saveAttempt,retain:true,libraryId:v.result?.resume_usage?.material_id||'',stage:v.result?.diagnosis?'result':v.result?'partial':'materials'};if(v.saveAttempt){state.keep=v.saveAttempt.keep;state.auto=v.saveAttempt.auto;}open();}
  }
  [dialog,continuation].forEach(el=>el.addEventListener('click',e=>{const target=e.target.closest('[data-diagnosis-action]');if(target)action(target.dataset.diagnosisAction).catch(error=>notify(error.message));}));
  dialog.addEventListener('close',updateContinuation);
  dialog.addEventListener('change',e=>{
    if(e.target.id==='diagnosis-no-remind'){try{localStorage.setItem(PREF,String(e.target.checked));}catch{notify('浏览器未允许记住提醒偏好。');}}
    if(e.target.id==='diagnosis-library'){state.libraryId=e.target.value;state.file=null;state.preview=null;state.requestKey=null;render();}
  });
  dialog.addEventListener('input',e=>{const field=e.target.dataset.diagnosisField;if(!field)return;state[field]=e.target.type==='checkbox'?e.target.checked:e.target.value;if(field==='retain'&&!state.retain)erase();else store();if(['concern','jd','duration','replies'].includes(field))state.requestKey=null;if(field==='keep'&&!state.file)render();const start=dialog.querySelector('[data-diagnosis-action="analyze"]');if(start&&state.stage==='materials')start.disabled=reading||!state.concern.trim()||!(state.libraryId||state.preview);});
  launcher.addEventListener('click',()=>{if(pending)return action('restore');if(state.stage==='saved')state=fresh();if(state.stage==='welcome')return materials();open();});
  window.addEventListener('pagehide',store);
  window.addEventListener('storage',e=>{if(e.key===KEY||e.key===null){blocked=true;state.retain=false;pending=null;notify('另一页面更新或清除了首次诊断保留，本页自动保留已暂停；当前内容仍在。');updateContinuation();}});
  window.MakoFirstVisit=Object.freeze({busy,wrapTool,leaveTool});
  try{baseline=localStorage.getItem(KEY);if(baseline){pending=decode(baseline);if(pending.expires<=Date.now()){erase();pending=null;}}if(!pending&&localStorage.getItem(PREF)!=='true'&&!document.querySelector('dialog[open]'))open();}catch{blocked=true;notify('上次首次诊断记录不可读取，未自动覆盖。可打开诊断后清除本次保留。');}
  updateContinuation();
})();
