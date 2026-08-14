// ============================================================
// 以下为完整的 app.js，包含 Day 20 所有功能，并确保全局可用
// ============================================================

const state = {
  sessions: [],
  currentSessionId: null,
  messages: [],
  questions: [],
  assets: { crystals: [], holes: [], counts: {} },
  pending: [],
  tasks: [],
  jobs: new Map(),
  currentLayer: "all",
  currentBatchJobId: null,
  currentDailyJobId: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

function renderMessage(role, content, level = "") {
  const div = document.createElement("div");
  div.className = `msg ${role} ${level}`;
  const label = role === "user" ? "你" : role === "assistant" ? "AI" : "系统";
  div.innerHTML = `<span class="meta">${label} · ${new Date().toLocaleTimeString()}</span>${escapeHtml(content)}`;
  return div;
}

function updateChatMeta() {
  const count = state.messages.filter((m) => ["user", "assistant"].includes(m.role)).length;
  $("chatMeta").textContent = `${count} 条消息`;
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

function setStatus(text) {
  $("statusLine").textContent = text;
}

function clampRounds(value) {
  return Math.max(2, Math.min(12, Number(value || 2)));
}

function updateRoundControl() {
  const isSingle = $("reasonMode").value === "single";
  const input = $("debateRoundsInput");
  input.disabled = isSingle;
  input.closest(".round-control")?.classList.toggle("is-disabled", isSingle);
}

function buildReasonPayload() {
  const mode = $("reasonMode").value;
  const payload = { ...inputPayload(), mode };
  if (mode !== "single") {
    payload.max_rounds = clampRounds($("debateRoundsInput").value);
  }
  return payload;
}

async function bootstrap() {
  const data = await api("/api/bootstrap");
  state.sessions = data.sessions;
  setStatus(`数据根目录：${data.data_root} · API Key ${data.api_key_configured ? "已配置" : "未配置"}`);
  renderBackendAuth(Boolean(data.legacy_backend_running));
  $("assetStats").textContent = `资产 ${data.assets.total || 0}`;
  $("taskStats").textContent = `任务 ${data.task_count || 0}`;
  renderSessions();
  renderFocus(data.assets.L1 || 0);
  await loadAssets();
  await loadTasks();
  renderJobs();
  if (state.sessions.length) {
    await loadSession(state.sessions[0].id);
  } else {
    await createSession();
  }
}

function renderBackendAuth(running) {
  $("backendLoginBtn").disabled = running;
  $("backendLogoutBtn").disabled = !running;
  $("backendLoginBtn").textContent = running ? "老师模式已开启" : "老师入口";
}

function openAuthDialog() {
  $("authError").textContent = "";
  $("authUsername").value = "";
  $("authPassword").value = "";
  $("authDialog").showModal();
  setTimeout(() => $("authUsername").focus(), 0);
}

async function submitBackendLogin() {
  const username = $("authUsername").value.trim();
  const password = $("authPassword").value;
  if (!username || !password) {
    $("authError").textContent = "请输入用户名和密码";
    return;
  }
  try {
    const result = await api("/api/backend/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    $("authDialog").close();
    appendSystem(result.message || "老师模式已开启", "system");
    renderBackendAuth(Boolean(result.running));
  } catch (err) {
    $("authError").textContent = "用户名或密码错误";
  }
}

function renderSessions() {
  const q = $("sessionSearch").value.trim().toLowerCase();
  $("sessionList").innerHTML = "";
  state.sessions.filter((s) => !q || s.name.toLowerCase().includes(q)).forEach((s) => {
    const btn = document.createElement("button");
    btn.className = `session-item ${s.id === state.currentSessionId ? "active" : ""}`;
    btn.textContent = s.name;
    btn.title = `${s.name}\n${s.updated_at || ""}`;
    btn.onclick = () => loadSession(s.id);
    $("sessionList").appendChild(btn);
  });
}

async function refreshSessions() {
  state.sessions = (await api("/api/sessions")).sessions;
  renderSessions();
}

async function createSession() {
  const session = await api("/api/sessions", { method: "POST", body: JSON.stringify({}) });
  await refreshSessions();
  await loadSession(session.id);
}

async function renameCurrentSession() {
  if (!state.currentSessionId) return;
  const current = state.sessions.find((s) => s.id === state.currentSessionId);
  const name = prompt("请输入新会话名称：", current?.name || "");
  if (!name || !name.trim()) return;
  await api(`/api/sessions/${state.currentSessionId}`, { method: "PATCH", body: JSON.stringify({ name: name.trim() }) });
  await refreshSessions();
}

async function deleteCurrentSession() {
  if (!state.currentSessionId) return;
  const current = state.sessions.find((s) => s.id === state.currentSessionId);
  if (!confirm(`删除会话「${current?.name || state.currentSessionId}」？`)) return;
  await api(`/api/sessions/${state.currentSessionId}`, { method: "DELETE" });
  await refreshSessions();
  if (state.sessions.length) await loadSession(state.sessions[0].id);
  else await createSession();
}

async function loadSession(id) {
  const data = await api(`/api/sessions/${id}`);
  state.currentSessionId = id;
  state.messages = data.messages;
  state.questions = data.questions;
  renderSessions();
  renderLog();
  renderQuestions();
}

function renderLog() {
  $("logArea").innerHTML = "";
  if (!state.messages.length) {
    $("logArea").appendChild(renderMessage("system", "当前会话还没有消息。"));
    updateChatMeta();
    return;
  }
  state.messages.forEach((m) => $("logArea").appendChild(renderMessage(m.role, m.content)));
  updateChatMeta();
  $("logArea").scrollTop = $("logArea").scrollHeight;
}

function renderQuestions() {
  $("questionList").innerHTML = "";
  if (!state.questions.length) {
    $("questionList").innerHTML = `<div class="question-item">暂无问题</div>`;
    return;
  }
  state.questions.forEach((q) => {
    const div = document.createElement("div");
    div.className = "question-item";
    div.textContent = q.label;
    $("questionList").appendChild(div);
  });
}

function renderFocus(l1Count) {
  $("attentionCount").textContent = `${Math.min(50, l1Count + 3)}/50`;
  $("focusSlots").innerHTML = "";
  for (let i = 1; i <= 20; i += 1) {
    const span = document.createElement("span");
    span.className = `slot ${i <= Math.min(17, l1Count) ? "active" : ""} ${i === 5 ? "fixed" : ""}`;
    span.textContent = String(i).padStart(2, "0");
    $("focusSlots").appendChild(span);
  }
}

async function loadAssets() {
  state.assets = await api("/api/assets");
  renderFocus(state.assets.counts.L1 || 0);
  $("assetStats").textContent = `资产 ${state.assets.counts.total || 0}`;
  renderAssets();
  renderManager();
}

function layerName(layer) {
  if (layer === "L1") return "高价值区";
  if (layer === "L2") return "进阶区";
  if (layer === "L3") return "沉淀区";
  return layer;
}

function renderAssets() {
  const grid = $("assetGrid");
  grid.innerHTML = "";
  if (state.currentLayer === "holes") {
    state.assets.holes.forEach((h) => grid.appendChild(cardHtml("hole", h)));
    return;
  }
  state.assets.crystals
    .filter((c) => state.currentLayer === "all" || c.layer === state.currentLayer)
    .forEach((c) => grid.appendChild(cardHtml("crystal", c)));
}

function cardHtml(type, item) {
  const div = document.createElement("article");
  div.className = "asset-card";
  if (type === "hole") {
    div.innerHTML = `<div class="asset-head"><span class="pill">${item.id}</span><span class="pill green">启发线索</span></div><p>${escapeHtml(item.content)}</p><div class="asset-meta"><span>紧迫度 ${item.urgency}</span><span>Layer ${item.layer}</span></div>`;
    return div;
  }
  const heat = Math.min(100, Math.round((item.heat || 0) * 100));
  div.innerHTML = `
    <div class="asset-head"><span class="pill">${item.id}${item.fixed ? " ★" : ""}</span><span class="pill green">${layerName(item.layer)}</span></div>
    <p>${escapeHtml(item.content)}</p>
    <div class="value-track"><div class="value-fill" style="width:${heat}%"></div></div>
    <div class="asset-meta"><span>热度 ${item.heat}</span><span>${item.last_accessed || "从未访问"}</span></div>`;
  return div;
}

async function loadTasks() {
  state.pending = (await api("/api/pending")).cards;
  state.tasks = (await api("/api/tasks")).tasks;
  $("taskStats").textContent = `任务 ${state.tasks.filter((t) => t.status === "pending").length}`;
  renderTasks();
}

function renderTasks() {
  $("pendingList").innerHTML = state.pending.length ? "" : `<div class="list-card">暂无待确认卡片</div>`;
  state.pending.forEach((card) => {
    const div = document.createElement("div");
    div.className = "list-card";
    div.innerHTML = `<span class="pill">${card.id}</span><p><b>${escapeHtml(card.title)}</b></p><p>${escapeHtml(card.content || card.raw)}</p><div class="list-actions"><button class="success">转为晶体</button><button class="danger">忽略</button></div>`;
    div.querySelector(".success").onclick = () => confirmPending(card);
    div.querySelector(".danger").onclick = () => ignorePending(card.id);
    $("pendingList").appendChild(div);
  });
  const pendingTasks = state.tasks.filter((t) => t.status === "pending");
  $("taskList").innerHTML = pendingTasks.length ? "" : `<div class="list-card">暂无冲突任务</div>`;
  pendingTasks.forEach((task) => {
    const div = document.createElement("div");
    div.className = "list-card";
    div.innerHTML = `<span class="pill">${task.id}</span><p><b>${escapeHtml(task.title)}</b></p><p>${escapeHtml(task.content)}</p><p>${escapeHtml(task.suggested_action || "")}</p><div class="list-actions"><button class="success">标记处理</button><button class="danger">忽略</button></div>`;
    div.querySelector(".success").onclick = () => resolveTask(task.id);
    div.querySelector(".danger").onclick = () => ignoreTask(task.id);
    $("taskList").appendChild(div);
  });
}

function renderManager() {
  const layer = $("managerLayer").value;
  $("managerTable").innerHTML = "";
  state.assets.crystals.filter((c) => layer === "all" || c.layer === layer).forEach((c) => {
    const row = document.createElement("div");
    row.className = "table-row";
    row.innerHTML = `<b>${c.id}</b><span>${escapeHtml(c.content)}</span><span>${c.layer}${c.fixed ? " ★" : ""}</span><span>${c.heat}</span><div class="row-actions"><button>L1</button><button>L2</button><button>L3</button><button class="danger">删</button></div>`;
    const buttons = row.querySelectorAll("button");
    buttons[0].onclick = () => patchAsset(c.id, { layer: "L1", fixed: true });
    buttons[1].onclick = () => patchAsset(c.id, { layer: "L2", fixed: false });
    buttons[2].onclick = () => patchAsset(c.id, { layer: "L3", fixed: false });
    buttons[3].onclick = () => deleteAsset(c.id);
    $("managerTable").appendChild(row);
  });
}

async function patchAsset(id, payload) {
  await api(`/api/assets/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
  await loadAssets();
}

async function deleteAsset(id) {
  if (!confirm(`删除晶体 ${id}？不可恢复。`)) return;
  await api(`/api/assets/${id}`, { method: "DELETE" });
  await loadAssets();
}

async function confirmPending(card) {
  const content = prompt("确认前可编辑晶体内容：", card.content || card.title);
  if (content === null) return;
  let result = await api(`/api/pending/${card.id}/confirm`, { method: "POST", body: JSON.stringify({ content, force: false }) });
  if (result.needs_force && confirm(`发现可能重复晶体，仍继续？\n${result.similar.map((x) => `${x.id} ${x.score} ${x.content}`).join("\n")}`)) {
    result = await api(`/api/pending/${card.id}/confirm`, { method: "POST", body: JSON.stringify({ content, force: true }) });
  }
  if (result.ok) {
    await loadTasks();
    await loadAssets();
  }
}

async function ignorePending(id) {
  await api(`/api/pending/${id}/ignore`, { method: "POST" });
  await loadTasks();
}

async function resolveTask(id) {
  await api(`/api/tasks/${id}/resolve`, { method: "POST" });
  await loadTasks();
}

async function ignoreTask(id) {
  await api(`/api/tasks/${id}/ignore`, { method: "POST" });
  await loadTasks();
}

async function confirmPendingById() {
  const id = prompt("输入卡片 ID（例如 PENDING-20260618120000-001）：");
  if (!id) return;
  const card = state.pending.find((item) => item.id === id.trim());
  const initial = card?.content || card?.title || "";
  const content = prompt("确认前可编辑晶体内容：", initial);
  if (content === null) return;
  let result = await api(`/api/pending/${id.trim()}/confirm`, { method: "POST", body: JSON.stringify({ content, force: false }) });
  if (result.needs_force && confirm(`发现可能重复晶体，仍继续？\n${result.similar.map((x) => `${x.id} ${x.score} ${x.content}`).join("\n")}`)) {
    result = await api(`/api/pending/${id.trim()}/confirm`, { method: "POST", body: JSON.stringify({ content, force: true }) });
  }
  if (result.ok) {
    await loadTasks();
    await loadAssets();
  }
}

function activeView(name) {
  document.querySelectorAll(".nav-list button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
}

async function startJob(path, payload, label) {
  const data = await api(path, { method: "POST", body: JSON.stringify(payload) });
  state.jobs.set(data.job_id, { id: data.job_id, label, status: "queued" });
  renderJobs();
  pollJob(data.job_id);
  return data;
}

async function pollJob(jobId) {
  const job = await api(`/api/jobs/${jobId}`);
  state.jobs.set(jobId, { ...state.jobs.get(jobId), ...job });
  renderJobs();
  if (job.status === "done") {
    if (job.result?.debate) openDebateResult(job.result.debate);
    if (job.result?.preview) openCrystalPreview(job.result.session_id, job.result.preview);
    await refreshSessions();
    if (state.currentSessionId) await loadSession(state.currentSessionId);
    await loadAssets();
    await loadTasks();
  } else if (job.status === "error") {
    appendSystem(job.error || "任务失败", "error");
  } else {
    setTimeout(() => pollJob(jobId), 1200);
  }
}

function openDebateResult(debate) {
  const final = debate.final || {};
  const rigid = final.rigid_core || {};
  const rounds = debate.rounds || [];
  $("dialogTitle").textContent = "深入讨论结果";
  $("dialogBody").innerHTML = `
    <div class="stack-list">
      <div class="list-card"><b>一句话结论</b><p>${escapeHtml(rigid.decision_summary || final.one_sentence_conclusion || "")}</p></div>
      <div class="list-card"><b>给你的建议</b><p>${escapeHtml(final.soft_wrap || final.student_friendly_answer || debate.answer || "")}</p></div>
      <details class="list-card" open><summary><b>刚性内核</b></summary>
        <p><b>关键融合：</b>${escapeHtml(rigid.key_synthesis || final.key_synthesis || "")}</p>
        <p><b>边界风险：</b>${escapeHtml((rigid.risks_and_boundaries || final.risks || []).join("\\n") || "暂无特别风险。")}</p>
      </details>
      <details class="list-card"><summary><b>采纳了哪些观点</b></summary>${(rigid.core_adoptions || final.adopted_points || []).map((x) => `<p>${escapeHtml(x)}</p>`).join("") || "<p>暂无详细采纳记录。</p>"}</details>
      <details class="list-card" open><summary><b>辩论环节</b></summary>${renderDebateRounds(rounds)}</details>
      <details class="list-card"><summary><b>老师详情</b></summary><p>${escapeHtml(final.teacher_detail || "")}</p><p>模式：${escapeHtml(debate.mode)}；估算调用：${debate.calls_estimate || "-"} 次；轮次：${rounds.length}</p></details>
    </div>`;
  $("dialogPrimaryBtn").textContent = "我知道了";
  $("dialogPrimaryBtn").onclick = () => $("previewDialog").close();
  $("previewDialog").showModal();
}

function renderDebateRounds(rounds) {
  if (!rounds.length) return "<p>暂无辩论轮次记录。</p>";
  return rounds.map((round) => {
    const audit = round.audit || {};
    const answers = round.answers || [];
    return `
      <div class="debate-round">
        <h3>第 ${round.round} 轮 ${round.jaccard !== undefined ? `<span>Jaccard ${round.jaccard}</span>` : ""}</h3>
        ${audit.summary ? `<p class="audit-line"><b>逻辑检查员：</b>${escapeHtml(audit.summary)}</p>` : ""}
        ${audit.major_conflict !== undefined ? `<p class="audit-line"><b>关键分歧：</b>${audit.major_conflict ? "存在事实/逻辑层面重大分歧" : "暂无不可调和重大分歧"}</p>` : ""}
        <div class="role-answer-grid">
          ${answers.map((item) => `
            <article class="role-answer">
              <b>${escapeHtml(item.role || "角色")}</b>
              ${renderRoleSamples(item.samples || [])}
              ${formatDebateAnswer(item.answer || "")}
            </article>
          `).join("")}
        </div>
      </div>`;
  }).join("");
}

function renderRoleSamples(samples) {
  if (!samples.length) return "";
  return `<details class="debate-section"><summary>角色内多采样</summary>${samples.map((sample) => `
    <p><b>样本 ${escapeHtml(sample.sample || "")}：</b>${escapeHtml(sample.focus || "")}</p>
    <p>${escapeHtml(sample.answer || "")}</p>
  `).join("")}</details>`;
}

function formatDebateAnswer(text) {
  const safe = escapeHtml(text);
  const sections = [
    ["靶向攻击", "【靶向攻击】"],
    ["辩护与吸收", "【辩护与吸收】"],
    ["折冲整合方案", "【折冲整合方案】"],
  ];
  if (!sections.some(([, marker]) => safe.includes(marker))) {
    return `<p>${safe}</p>`;
  }
  return sections.map(([title, marker], index) => {
    const next = sections[index + 1]?.[1];
    const start = safe.indexOf(marker);
    if (start < 0) return "";
    const contentStart = start + marker.length;
    const end = next ? safe.indexOf(next, contentStart) : -1;
    const content = safe.slice(contentStart, end >= 0 ? end : undefined).trim();
    return `<details class="debate-section" ${title === "折冲整合方案" ? "open" : ""}><summary>${title}</summary><p>${content || "未提取到内容"}</p></details>`;
  }).join("");
}

function renderJobs() {
  $("jobList").innerHTML = "";
  if (!state.jobs.size) {
    $("jobList").innerHTML = `<div class="job-item">暂无后台任务</div>`;
    return;
  }
  [...state.jobs.values()].slice(-6).reverse().forEach((j) => {
    const div = document.createElement("div");
    div.className = `job-item ${j.status || ""}`;
    const daily = j.daily_progress || {};
    const logs = (j.logs || []).slice(-2).map((x) => `${x.time} ${x.message}`).join("\n");
    div.innerHTML = `
      <b>${escapeHtml(j.label || j.type)}: ${escapeHtml(j.status || "queued")} · ${j.progress || 0}%</b>
      <progress max="100" value="${Number(j.progress || 0)}"></progress>
      ${daily.stage ? `<small>${escapeHtml(daily.stage)} · 候选 ${daily.candidate_count || 0} · 卡片 ${daily.pending_count || 0} · 任务 ${daily.task_count || 0} · ${daily.elapsed_seconds || 0}/${daily.budget_seconds || 0}s</small>` : ""}
      ${logs ? `<small>${escapeHtml(logs)}</small>` : ""}
      ${j.type === "daily-plan" && ["queued", "running", "stopping"].includes(j.status || "") ? `<button data-stop-daily="${escapeHtml(j.id || "")}" class="danger">停止每日计划</button>` : ""}
    `;
    const stopBtn = div.querySelector("[data-stop-daily]");
    if (stopBtn) {
      stopBtn.onclick = async () => {
        await api(`/api/daily-plan/stop/${stopBtn.dataset.stopDaily}`, { method: "POST" });
        appendSystem("已请求中断每日计划，后端正在整理已有成果...", "system");
      };
    }
    $("jobList").appendChild(div);
  });
}

function parseDailyKeywords(text) {
  return text.split(/[,，;；\s\n]+/).map((x) => x.trim()).filter(Boolean);
}

function openDailyDialog() {
  const dialog = $("dailyDialog");
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}

function closeDailyDialog() {
  const dialog = $("dailyDialog");
  if (typeof dialog.close === "function") dialog.close();
  else dialog.removeAttribute("open");
}

async function startDailyPlan(useDefault = false) {
  const keywords = useDefault ? [] : parseDailyKeywords($("dailyKeywordsInput").value || "");
  closeDailyDialog();
  const data = await api("/api/daily-plan/run", {
    method: "POST",
    body: JSON.stringify({
      api_key: $("apiKeyInput").value.trim() || null,
      intent_keywords: keywords,
      time_budget_seconds: 900,
    }),
  });
  state.currentDailyJobId = data.job_id;
  state.jobs.set(data.job_id, { id: data.job_id, label: "每日计划", type: "daily-plan", status: "queued" });
  renderJobs();
  pollJob(data.job_id);
}

function appendSystem(content, role = "system") {
  $("logArea").appendChild(renderMessage(role, content, role === "error" ? "error" : ""));
  if (["user", "assistant"].includes(role)) {
    state.messages.push({ role, content });
    updateChatMeta();
  }
  $("logArea").scrollTop = $("logArea").scrollHeight;
}

function inputPayload() {
  const input = $("mainInput").value.trim();
  if (!input) throw new Error("请输入内容");
  return {
    session_id: state.currentSessionId,
    input,
    api_key: $("apiKeyInput").value.trim() || null,
  };
}

function openCrystalPreview(sessionId, preview) {
  $("dialogTitle").textContent = "晶体化预览确认";
  $("dialogBody").innerHTML = `
    <div class="stack-list">
      <div class="list-card"><b>摘要</b><p>${escapeHtml(preview.report_summary)}</p></div>
      <div class="list-card"><b>新增晶体 ${preview.new_crystals.length}</b>${preview.new_crystals.map((c) => `<p>${c.id} · ${escapeHtml(c.content)}</p>`).join("") || "<p>无</p>"}</div>
      <div class="list-card"><b>新增孔洞 ${preview.new_holes.length}</b>${preview.new_holes.map((h) => `<p>${h.id} · ${escapeHtml(h.content)}</p>`).join("") || "<p>无</p>"}</div>
      <div class="list-card"><b>待确认卡片 ${preview.pending_cards.length}</b>${preview.pending_cards.map((c) => `<p>${escapeHtml(c.type)} · ${escapeHtml(c.content)}</p>`).join("") || "<p>无</p>"}</div>
      <div class="list-card"><b>冲突 ${preview.conflicts.length}</b>${preview.conflicts.map((c) => `<p>${c.a} vs ${c.b} · ${escapeHtml(c.reason)}</p>`).join("") || "<p>无</p>"}</div>
    </div>`;
  $("dialogPrimaryBtn").textContent = "确认入库";
  $("dialogPrimaryBtn").onclick = async () => {
    await api("/api/crystallize/commit", { method: "POST", body: JSON.stringify({ session_id: sessionId, result: preview }) });
    $("previewDialog").close();
    await loadAssets();
    await loadTasks();
    if (state.currentSessionId) await loadSession(state.currentSessionId);
  };
  $("previewDialog").showModal();
}

async function showInfo(kind) {
  const map = {
    status: "/api/status",
    holes: "/api/holes",
    today: "/api/today",
    health: "/api/health",
  };
  const data = await api(map[kind]);
  $("healthPanel").textContent = JSON.stringify(data, null, 2);
}

function bindEvents() {
  $("newSessionBtn").onclick = createSession;
  $("renameSessionBtn").onclick = renameCurrentSession;
  $("deleteSessionBtn").onclick = deleteCurrentSession;
  $("sessionSearch").oninput = renderSessions;
  $("refreshBtn").onclick = async () => { await bootstrap(); appendSystem("数据已刷新"); };
  $("backendLoginBtn").onclick = openAuthDialog;
  $("authSubmitBtn").onclick = submitBackendLogin;
  $("authPassword").onkeydown = (event) => {
    if (event.key === "Enter") submitBackendLogin();
  };
  $("authUsername").onkeydown = (event) => {
    if (event.key === "Enter") $("authPassword").focus();
  };
  $("backendLogoutBtn").onclick = async () => {
    try {
      const result = await api("/api/backend/logout", { method: "POST" });
      appendSystem(result.message || "已退出老师模式，学生端仍可继续使用", "system");
      renderBackendAuth(Boolean(result.running));
    } catch (err) {
      appendSystem(`退出老师模式失败：${err.message}`, "error");
    }
  };
  document.querySelectorAll(".nav-list button").forEach((b) => b.onclick = () => activeView(b.dataset.view));
  $("clearInputBtn").onclick = () => { $("mainInput").value = ""; };
  $("reasonMode").onchange = updateRoundControl;
  $("debateRoundsInput").onblur = () => {
    const input = $("debateRoundsInput");
    input.value = clampRounds(input.value);
  };
  $("clearSessionBtn").onclick = async () => {
    if (!state.currentSessionId || !confirm("清空当前会话消息？")) return;
    await api(`/api/sessions/${state.currentSessionId}/clear`, { method: "POST" });
    await loadSession(state.currentSessionId);
  };
  $("chatBtn").onclick = async () => {
    try {
      const payload = inputPayload();
      $("mainInput").value = "";
      appendSystem(payload.input, "user");
      await startJob("/api/chat", payload, "聊天");
    } catch (err) { appendSystem(err.message, "error"); }
  };
  $("crystalBtn").onclick = async () => {
    try {
      const payload = { ...inputPayload(), fast_mode: $("fastModeInput").checked, scope: $("scopeInput").value };
      $("mainInput").value = "";
      appendSystem(`[晶体化] ${payload.input}`, "user");
      await startJob("/api/crystallize", payload, "晶体化");
    } catch (err) { appendSystem(err.message, "error"); }
  };
  $("reasonBtn").onclick = async () => {
    try {
      const payload = buildReasonPayload();
      $("mainInput").value = "";
      appendSystem(`[深度推理] ${payload.input}`, "user");
      await startJob("/api/deep-reasoning", payload, "深度思考");
    } catch (err) { appendSystem(err.message, "error"); }
  };
  $("fileInput").onchange = async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("session_id", state.currentSessionId || "");
    form.append("api_key", $("apiKeyInput").value.trim());
    form.append("upload", file);
    const data = await api("/api/file-chat", { method: "POST", body: form });
    state.jobs.set(data.job_id, { label: "文件对话", status: "queued" });
    pollJob(data.job_id);
  };
  $("batchStartBtn").onclick = async () => {
    try {
      const folder = $("batchFolderInput").value.trim();
      if (!folder) throw new Error("请输入后端可访问的文件夹路径");
      const data = await startJob("/api/batch/start", {
        folder,
        mode: $("batchModeInput").value,
        fast_mode: $("fastModeInput").checked,
        inject_history: $("batchInjectInput").checked,
        session_id: state.currentSessionId,
        api_key: $("apiKeyInput").value.trim() || null,
      }, "批量处理");
      state.currentBatchJobId = data.job_id;
    } catch (err) { appendSystem(err.message, "error"); }
  };
  $("batchStopBtn").onclick = async () => {
    if (!state.currentBatchJobId) {
      appendSystem("当前没有可停止的批量处理任务", "system");
      return;
    }
    await api(`/api/batch/stop/${state.currentBatchJobId}`, { method: "POST" });
    appendSystem("正在停止批量处理...", "system");
  };
  $("quickStatusBtn").onclick = async () => { activeView("health"); await showInfo("status"); };
  $("quickHolesBtn").onclick = async () => { activeView("health"); await showInfo("holes"); };
  $("quickPendingBtn").onclick = async () => { activeView("tasks"); await loadTasks(); };
  $("quickConfirmBtn").onclick = confirmPendingById;
  $("quickTodayBtn").onclick = async () => { activeView("health"); await showInfo("today"); };
  $("quickTasksBtn").onclick = async () => { activeView("tasks"); await loadTasks(); };
  $("quickManagerBtn").onclick = () => activeView("manager");
  $("quickSearchBtn").onclick = () => activeView("search");
  $("quickHealthBtn").onclick = async () => { activeView("health"); await showInfo("health"); };
  $("dailyBtn").onclick = async () => {
    $("dailyKeywordsInput").value = "";
    openDailyDialog();
    setTimeout(() => $("dailyKeywordsInput").focus(), 0);
  };
  document.querySelector('#dailyDialog button[value="cancel"]').onclick = closeDailyDialog;
  $("dailyStartBtn").onclick = () => startDailyPlan(false).catch((err) => appendSystem(err.message, "error"));
  $("dailyDefaultBtn").onclick = () => startDailyPlan(true).catch((err) => appendSystem(err.message, "error"));
  document.querySelectorAll("#assetTabs button").forEach((b) => b.onclick = () => {
    document.querySelectorAll("#assetTabs button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.currentLayer = b.dataset.layer;
    renderAssets();
  });
  $("managerLayer").onchange = renderManager;
  $("managerRefreshBtn").onclick = loadAssets;
  $("docSearchBtn").onclick = async () => {
    const data = await api("/api/search", { method: "POST", body: JSON.stringify({ keyword: $("docKeyword").value.trim(), regex: $("docRegex").checked, dirs: $("docDirs").value.split(",").map((x) => x.trim()).filter(Boolean) }) });
    $("searchResults").textContent = data.results.map((r) => `${r.file}:${r.line}: ${r.text}`).join("\n") + `\n\n共找到 ${data.total} 条结果`;
  };
  $("showStatusBtn").onclick = () => showInfo("status");
  $("showHolesBtn").onclick = () => showInfo("holes");
  $("showTodayBtn").onclick = () => showInfo("today");
  $("showHealthBtn").onclick = () => showInfo("health");

  // ============================================================
  // Day 21: 用户认证按钮绑定
  // ============================================================
  // 右上角"登录"按钮 -> 显示登录遮罩
  document.getElementById('loginBtn')?.addEventListener('click', function () {
    showLoginOverlay();
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('loginError').textContent = '';
  });

  // 右上角"注册"按钮 -> 显示注册遮罩
  document.getElementById('registerBtn')?.addEventListener('click', function () {
    showLoginOverlay();
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('registerError').textContent = '';
  });

  // 遮罩中的"登录"按钮
  document.getElementById('loginSubmitBtn')?.addEventListener('click', handleLogin);
  // 遮罩中密码框按回车触发登录
  document.getElementById('loginPassword')?.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') handleLogin();
  });

  // 遮罩中的"注册"按钮
  document.getElementById('registerSubmitBtn')?.addEventListener('click', handleRegister);
  // 遮罩中注册密码框按回车触发注册
  document.getElementById('registerPassword')?.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') handleRegister();
  });

  // 遮罩中"立即注册"链接
  document.getElementById('switchToRegister')?.addEventListener('click', function (e) {
    e.preventDefault();
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('registerError').textContent = '';
  });

  // 遮罩中"去登录"链接
  document.getElementById('switchToLogin')?.addEventListener('click', function (e) {
    e.preventDefault();
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('loginError').textContent = '';
  });

  // 退出登录按钮
  document.getElementById('logoutBtn')?.addEventListener('click', handleLogout);

  // 升级专业版按钮
  document.getElementById('upgradeBtn')?.addEventListener('click', handleUpgrade);

// ============================================================
// Day 20: GitHub Trending + 全球认知雷达
// ============================================================

// ---------- 加载 Trending ----------
async function loadTrending() {
  const container = document.getElementById('trendingGrid');
  if (!container) {
    console.warn('⚠️ trendingGrid 元素未找到');
    return;
  }
  container.innerHTML = '<div class="asset-card"><p>加载中...</p></div>';
  try {
    const data = await api('/api/trending?limit=10');
    if (data.crystals && data.crystals.length > 0) {
      container.innerHTML = data.crystals.map((c, i) => `
        <div class="asset-card" style="border-left:4px solid #2a9d8f;">
          <div class="head">
            <span class="pill">#${i + 1} ${c.id}</span>
            <span class="pill gold">GitHub</span>
          </div>
          <p>${escapeHtml(c.content)}</p>
          <div class="asset-meta">
            <span>📁 ${c.path?.split('/').slice(-2).join('/') || 'skills/trending'}</span>
          </div>
        </div>
      `).join('');
    } else {
      container.innerHTML = '<div class="asset-card"><p style="color:#5a7b8e;">暂无数据，点击「刷新抓取」</p></div>';
    }
  } catch (err) {
    container.innerHTML = `<div class="asset-card"><p style="color:#b13e3e;">加载失败：${err.message}</p></div>`;
    console.error('loadTrending 错误:', err);
  }
}

// ---------- 刷新 Trending ----------
async function refreshTrending() {
  console.log('🔄 refreshTrending 被点击');
  const btn = document.getElementById('refreshTrendingBtn');
  if (!btn) {
    console.error('❌ refreshTrendingBtn 元素未找到');
    return;
  }
  btn.disabled = true;
  btn.textContent = '⏳ 抓取中...';
  try {
    await api('/api/trending/refresh', { method: 'POST', body: JSON.stringify({ max_items: 10 }) });
    await loadTrending();
    alert('✅ Trending 刷新成功！');
  } catch (err) {
    console.error('刷新失败:', err);
    alert('❌ 刷新失败：' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-sync-alt"></i> 刷新抓取';
  }
}

// ---------- 扫描雷达 ----------
async function scanRadar() {
  console.log('🌍 scanRadar 被点击');
  const container = document.getElementById('radarResults');
  if (!container) {
    console.error('❌ radarResults 元素未找到');
    return;
  }
  container.innerHTML = '<div class="asset-card"><p>🌍 扫描全球新闻中...</p></div>';
  try {
    const data = await api('/api/radar');
    if (data.status === 'success' && data.data) {
      let html = '';
      const langMap = { zh: '🇨🇳', en: '🇬🇧', ja: '🇯🇵', de: '🇩🇪', es: '🇪🇸' };
      let total = 0;
      for (const [lang, articles] of Object.entries(data.data)) {
        if (!articles || !articles.length) continue;
        total += articles.length;
        html += `<div class="asset-card" style="margin-bottom:12px;border-left:4px solid #4a7a9c;">
          <div class="head"><span class="pill">${langMap[lang] || '🌐'} ${lang.toUpperCase()}</span><span class="pill">${articles.length} 条</span></div>`;
        articles.slice(0, 5).forEach(a => {
          html += `<p style="font-size:13px;border-bottom:1px solid rgba(42,157,143,0.06);padding:4px 0;">${escapeHtml(a.title)}</p>`;
        });
        html += `</div>`;
      }
      container.innerHTML = html || '<div class="asset-card"><p>暂无数据</p></div>';
      if (total > 0) {
        const stat = document.createElement('div');
        stat.className = 'asset-card';
        stat.style.marginTop = '12px';
        stat.innerHTML = `<p style="font-weight:600;">📊 共抓取 ${total} 条新闻，覆盖 ${Object.keys(data.data).filter(k => data.data[k].length).length} 种语言</p>`;
        container.appendChild(stat);
      }
    } else {
      container.innerHTML = '<div class="asset-card"><p style="color:#5a7b8e;">雷达数据暂不可用</p></div>';
    }
  } catch (err) {
    console.error('扫描失败:', err);
    container.innerHTML = `<div class="asset-card"><p style="color:#b13e3e;">扫描失败：${err.message}</p></div>`;
  }
}



  // 导航切换时自动加载
  document.querySelectorAll('.nav-list button[data-view]').forEach(btn => {
    btn.addEventListener('click', function () {
      const view = this.dataset.view;
      if (view === 'trending') setTimeout(loadTrending, 100);
      if (view === 'radar') setTimeout(scanRadar, 100);
    });
  });

  // 如果当前激活的是 trending 或 radar，立即加载
  const activeView = document.querySelector('.nav-list button.active');
  if (activeView) {
    const view = activeView.dataset.view;
    if (view === 'trending') setTimeout(loadTrending, 200);
    if (view === 'radar') setTimeout(scanRadar, 200);
  }
})();


// ============================================================
// 认知指纹加载与渲染
// ============================================================
async function loadFingerprint() {
  try {
    const data = await api("/api/fingerprint");
    if (data.fingerprint) {
      renderRadarChart(data.fingerprint);
      updateProfileLabels(data.fingerprint);
    } else {
      updateProfileLabels(null);
    }
  } catch (err) {
    console.warn('指纹加载失败:', err);
    updateProfileLabels(null);
  }
}

function renderRadarChart(fp) {
  const canvas = document.getElementById("radarCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  const cx = w / 2, cy = h / 2;
  const radius = 70;

  ctx.clearRect(0, 0, w, h);

  if (!fp) {
    ctx.fillStyle = "#999";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("暂无数据", cx, cy);
    return;
  }

  const dims = [
    fp.risk_tolerance || 0,
    fp.innovation_preference || 0,
    fp.decisiveness || 0,
    fp.attention_span || 0,
    fp.confidence || 0
  ];
  const labels = ["风险容忍", "创新偏好", "决策果断", "注意力持续", "认知置信"];
  const angles = [-90, -18, 54, 126, 198].map(deg => deg * Math.PI / 180);

  for (let r of [0.3, 0.6, 0.9]) {
    ctx.beginPath();
    for (let i = 0; i < 5; i++) {
      const x = cx + radius * r * Math.cos(angles[i]);
      const y = cy + radius * r * Math.sin(angles[i]);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = "#ddd";
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }

  for (let angle of angles) {
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + radius * 1.05 * Math.cos(angle), cy + radius * 1.05 * Math.sin(angle));
    ctx.strokeStyle = "#ddd";
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }

  ctx.beginPath();
  for (let i = 0; i < 5; i++) {
    const r = radius * Math.max(0, Math.min(1, dims[i]));
    const x = cx + r * Math.cos(angles[i]);
    const y = cy + r * Math.sin(angles[i]);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = "rgba(111, 86, 217, 0.25)";
  ctx.fill();
  ctx.strokeStyle = "#6f56d9";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  for (let i = 0; i < 5; i++) {
    const angle = angles[i];
    const lx = cx + (radius + 20) * Math.cos(angle);
    const ly = cy + (radius + 20) * Math.sin(angle);
    ctx.fillStyle = "#555";
    ctx.font = "9px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(labels[i], lx, ly);
  }

  const avg = dims.reduce((a, b) => a + b, 0) / 5;
  ctx.fillStyle = "#6f56d9";
  ctx.font = "bold 12px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(avg.toFixed(2), cx, cy);
}

function updateProfileLabels(fp) {
  const container = document.getElementById("profileLabels");
  if (!container) return;
  if (!fp) {
    container.innerHTML = '<span style="color:#999;font-size:11px;">暂无认知数据，开始对话后生成</span>';
    return;
  }
  const items = [
    ["风险容忍", fp.risk_tolerance],
    ["创新偏好", fp.innovation_preference],
    ["决策果断", fp.decisiveness],
    ["注意力持续", fp.attention_span],
    ["认知置信", fp.confidence]
  ];
  container.innerHTML = items.map(([name, val]) =>
    `<span style="font-size:10px;color:#555;background:#f0edf5;padding:2px 8px;border-radius:10px;margin:2px;">${name}: ${(val || 0).toFixed(2)}</span>`
  ).join(" ");
}

// ============================================================
// 启动应用（最后执行）
// ============================================================
bindEvents();
updateRoundControl();

// ============================================================
// 确保函数全局可用（永久修复）
// ============================================================
window.refreshTrending = refreshTrending;
window.scanRadar = scanRadar;
window.loadTrending = loadTrending;

// ============================================================
// 绑定按钮（直接执行，不依赖任何事件）
// ============================================================
(function () {
  console.log('📌 永久绑定 Day20 按钮...');

  // 使用 addEventListener 更可靠
  const refreshBtn = document.getElementById('refreshTrendingBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', refreshTrending);
    console.log('✅ refreshTrendingBtn 永久绑定成功');
  } else {
    console.warn('⚠️ refreshTrendingBtn 未找到');
  }

  const scanBtn = document.getElementById('scanRadarBtn');
  if (scanBtn) {
    scanBtn.addEventListener('click', scanRadar);
    console.log('✅ scanRadarBtn 永久绑定成功');
  } else {
    console.warn('⚠️ scanRadarBtn 未找到');
  }

bootstrap().catch((err) => {
  setStatus("加载失败");
  appendSystem(err.message, "error");
  console.error("Bootstrap 错误:", err);
});

// 页面加载完成后加载指纹
setTimeout(loadFingerprint, 1000);
window.loadFingerprint = loadFingerprint;

  // ============================================================
  // Day 21: 用户认证 + 支付升级
  // ============================================================

  // ---------- 全局认证状态 ----------
  let authToken = localStorage.getItem('authToken') || null;
  let currentUser = null;

  // ---------- 认证 API ----------
  async function authApi(path, payload) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || '请求失败');
    return data;
  }

  // ---------- 登录 ----------
  async function handleLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');
    errorEl.textContent = '';

    if (!username || !password) {
      errorEl.textContent = '请填写用户名和密码';
      return;
    }

    try {
      const data = await authApi('/api/auth/login', { username, password });

      // ★★★ 第一步：先存 Token ★★★
      if (data.token) {
        localStorage.setItem('authToken', data.token);
        console.log('✅ Token 已存入 localStorage');
      } else {
        throw new Error('登录成功但未返回 Token');
      }

      // ★★★ 第二步：再加载用户信息（即使失败，Token 也已经保存了）★★★
      await loadCurrentUser();
      hideLoginOverlay();
      appendSystem(`✅ 欢迎回来，${currentUser?.username || '用户'}！`, 'success');
      updateAuthUI();
    } catch (e) {
      errorEl.textContent = e.message;
      console.error('登录流程出错:', e);
    }
  }

  // ---------- 注册 ----------
  async function handleRegister() {
    const username = document.getElementById('registerUsername').value.trim();
    const password = document.getElementById('registerPassword').value;
    const errorEl = document.getElementById('registerError');
    errorEl.textContent = '';

    if (!username || !password) {
      errorEl.textContent = '请填写完整';
      return;
    }
    if (password.length < 6) {
      errorEl.textContent = '密码至少6位';
      return;
    }

    try {
      await authApi('/api/auth/register', { username, password });
      // 注册成功，切换到登录表单
      document.getElementById('registerForm').style.display = 'none';
      document.getElementById('loginForm').style.display = 'block';
      document.getElementById('loginUsername').value = username;
      document.getElementById('loginPassword').value = '';
      document.getElementById('loginError').textContent = '✅ 注册成功，请登录！';
      document.getElementById('loginError').style.color = '#17a975';
    } catch (e) {
      errorEl.textContent = e.message;
    }
  }

  // ---------- 获取当前用户 ----------
  async function loadCurrentUser() {
    if (!authToken) {
      currentUser = null;
      return null;
    }
    try {
      const res = await fetch('/api/auth/me', {
        headers: { 'Authorization': 'Bearer ' + authToken }
      });
      if (!res.ok) throw new Error('获取用户信息失败');
      currentUser = await res.json();
      return currentUser;
    } catch (e) {
      console.warn('获取用户信息失败:', e);
      authToken = null;
      localStorage.removeItem('authToken');
      currentUser = null;
      return null;
    }
  }

  // ---------- 退出登录 ----------
  function handleLogout() {
    if (!confirm('确定要退出登录吗？')) return;
    authToken = null;
    localStorage.removeItem('authToken');
    currentUser = null;
    showLoginOverlay();
    updateAuthUI();
    appendSystem('已退出登录', 'system');
  }

  // ---------- 升级专业版 ----------
  async function handleUpgrade() {
    if (!authToken) {
      appendSystem('请先登录', 'warning');
      return;
    }
    try {
      const res = await fetch('/api/payment/create-checkout', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + authToken,
          'Content-Type': 'application/json'
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '创建支付会话失败');
      appendSystem('正在跳转到支付页面...', 'system');
      window.open(data.url, '_blank');
    } catch (e) {
      appendSystem('❌ ' + e.message, 'error');
    }
  }

  // ---------- 显示/隐藏登录遮罩 ----------
  function showLoginOverlay() {
    const overlay = document.getElementById('loginOverlay');
    if (overlay) overlay.classList.remove('hidden');
  }

  function hideLoginOverlay() {
    const overlay = document.getElementById('loginOverlay');
    if (overlay) overlay.classList.add('hidden');
  }

  // ---------- 切换登录/注册表单 ----------
  function switchToRegisterForm() {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('registerError').textContent = '';
  }

  function switchToLoginForm() {
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('loginError').textContent = '';
  }

  // ---------- 更新 UI 认证状态 ----------
  function updateAuthUI() {
    const userBadge = document.getElementById('userBadge');
    const authButtons = document.getElementById('authButtons');
    const upgradeBtn = document.getElementById('upgradeBtn');
    const userName = document.getElementById('userName');
    const userTierBadge = document.getElementById('userTierBadge');
    if (currentUser) {
      userBadge.style.display = 'inline-flex';
      authButtons.style.display = 'none';
      userName.textContent = currentUser.username || '用户';
      const isPro = currentUser.tier === 'pro';
      userTierBadge.textContent = isPro ? '专业版' : '免费版';
      userTierBadge.style.background = isPro ? '#8b5cf6' : '#2a9d8f';
      upgradeBtn.style.display = isPro ? 'none' : 'inline-flex';
      // 更新剩余次数
      const remaining = currentUser.trial_remaining;
      const quotaDisplay = document.getElementById('quotaDisplay');
      if (quotaDisplay) {
        if (remaining !== undefined && currentUser.tier === 'pro') {
          quotaDisplay.textContent = `本月剩余 ${remaining} 次`;
          quotaDisplay.style.display = 'inline';
        } else if (currentUser.tier === 'free') {
          quotaDisplay.textContent = '请设置 API Key';
          quotaDisplay.style.display = 'inline';
        } else {
          quotaDisplay.style.display = 'none';
        }
      }
      // 更新免费提示
      const freeHint = document.getElementById('freeHint');
      if (freeHint) {
        if (currentUser.tier === 'free') {
          freeHint.style.display = 'block';
          freeHint.textContent = '💡 免费用户请先在右上角设置自己的 DeepSeek API Key 以使用 AI 功能';
        } else {
          freeHint.style.display = 'none';
        }
      }
    } else {
      userBadge.style.display = 'none';
      authButtons.style.display = 'inline-flex';
      upgradeBtn.style.display = 'none';
      const quotaDisplay = document.getElementById('quotaDisplay');
      if (quotaDisplay) quotaDisplay.style.display = 'none';
      const freeHint = document.getElementById('freeHint');
      if (freeHint) freeHint.style.display = 'none';
    }
  }

  // ---------- 启动时检查登录状态 ----------
  async function checkAuthOnStartup() {
    const token = localStorage.getItem('authToken');
    if (token) {
      authToken = token;
      const user = await loadCurrentUser();
      if (user) {
        hideLoginOverlay();
        updateAuthUI();
        return true;
      } else {
        authToken = null;
        localStorage.removeItem('authToken');
      }
    }
    showLoginOverlay();
    return false;
  }

  // ---------- 绑定认证事件 ----------
  function bindAuthEvents() {
    // 登录按钮
    document.getElementById('loginSubmitBtn')?.addEventListener('click', handleLogin);
    document.getElementById('loginPassword')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleLogin();
    });

    // 注册按钮
    document.getElementById('registerSubmitBtn')?.addEventListener('click', handleRegister);
    document.getElementById('registerPassword')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleRegister();
    });

    // 切换表单
    document.getElementById('switchToRegister')?.addEventListener('click', (e) => {
      e.preventDefault();
      switchToRegisterForm();
    });
    document.getElementById('switchToLogin')?.addEventListener('click', (e) => {
      e.preventDefault();
      switchToLoginForm();
    });

    // 退出登录
    document.getElementById('logoutBtn')?.addEventListener('click', handleLogout);

    // 升级按钮
    document.getElementById('upgradeBtn')?.addEventListener('click', handleUpgrade);
  }

  // ============================================================
  // 修改 bootstrap 函数：先检查登录
  // ============================================================
  const originalBootstrap = bootstrap;
  bootstrap = async function () {
    await checkAuthOnStartup();
    return originalBootstrap();
  };

  // ============================================================
  // 导出到全局
  // ============================================================
  window.handleLogin = handleLogin;
  window.handleRegister = handleRegister;
  window.handleLogout = handleLogout;
  window.handleUpgrade = handleUpgrade;
  window.loadCurrentUser = loadCurrentUser;
  window.updateAuthUI = updateAuthUI;
  window.checkAuthOnStartup = checkAuthOnStartup;