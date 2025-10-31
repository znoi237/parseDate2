const LS_JOB_KEY = "train_job_id";
let pollTimer = null;
let logTimer = null;
let lastLogId = 0;

function qs(id) { return document.getElementById(id); }

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, { cache: 'no-store', ...opts });
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}

function setProgress(p0to1) {
  const el = qs("job_progress");
  let pct = Math.max(0, Math.min(1, Number(p0to1 || 0)));
  const txt = `${Math.round(pct * 100)}%`;
  el.style.width = txt;
  el.textContent = txt;
}

function setStatus(text, badge = "bg-secondary") {
  const el = qs("job_status");
  el.className = `badge ${badge}`;
  el.textContent = text;
}

function setMessage(msg) {
  qs("job_message").textContent = msg || "—";
}

function setDetail(job) {
  if (!job) { qs("job_detail").textContent = "—"; return; }
  const tfs = (job.timeframes || []).join(", ");
  qs("job_detail").textContent = `${job.symbol || ""} [${tfs}]`;
}

function setJobIdLabel(jobId) {
  qs("job_id_label").textContent = jobId ? `#${jobId}` : "—";
}

function appendLogs(rows) {
  if (!rows || !rows.length) return;
  const pre = qs("job_log");
  const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 5;
  rows.forEach(r => {
    const ts = new Date(r.ts).toLocaleString();
    const dataStr = r.data ? ` ${JSON.stringify(r.data)}` : "";
    pre.textContent += `[${ts}] ${r.level || "INFO"} ${r.phase || ""}: ${r.message}${dataStr}\n`;
    lastLogId = Math.max(lastLogId, Number(r.id || 0));
  });
  if (atBottom) {
    pre.scrollTop = pre.scrollHeight;
  }
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}
function stopLogPolling() {
  if (logTimer) clearInterval(logTimer);
  logTimer = null;
}

async function pollLogs(jobId) {
  const tick = async () => {
    try {
      const js = await fetchJson(`/api/training/${jobId}/logs?since_id=${lastLogId}&limit=200`);
      appendLogs(js.data || []);
    } catch (e) {
      console.error("pollLogs", e);
    }
  };
  stopLogPolling();
  await tick();
  logTimer = setInterval(tick, 1500);
}

async function pollJob(jobId, immediate = true) {
  setJobIdLabel(jobId);
  const tick = async () => {
    try {
      const js = await fetchJson(`/api/training/${jobId}`);
      const job = js.data;
      if (!job) {
        localStorage.removeItem(LS_JOB_KEY);
        setStatus("нет задачи", "bg-secondary");
        setProgress(0);
        setMessage("—");
        setDetail(null);
        stopPolling();
        stopLogPolling();
        return;
      }
      setDetail(job);
      setProgress(job.progress || 0);
      if (job.status === "queued") {
        setStatus("в очереди", "bg-warning text-dark");
        setMessage(job.message || "");
      } else if (job.status === "running") {
        setStatus("идёт", "bg-warning text-dark");
        setMessage(job.message || "");
      } else if (job.status === "finished") {
        setStatus("завершено", "bg-success");
        setMessage(job.message || "Completed");
        localStorage.removeItem(LS_JOB_KEY);
        stopPolling();
        // оставим лог‑polling ещё на 10 сек, потом остановим
        setTimeout(stopLogPolling, 10000);
      } else if (job.status === "error") {
        setStatus("ошибка", "bg-danger");
        setMessage(job.message || "Unknown error");
        localStorage.removeItem(LS_JOB_KEY);
        stopPolling();
      } else {
        setStatus(job.status || "статус?", "bg-secondary");
      }
    } catch (e) {
      console.error("pollJob", e);
    }
  };
  stopPolling();
  if (immediate) await tick();
  pollTimer = setInterval(tick, 2000);
  // параллельно — лог‑poll
  lastLogId = 0;
  await pollLogs(jobId);
}

async function loadSymbols() {
  try {
    const js = await fetchJson("/api/symbols");
    const sel = qs("tr_symbol");
    sel.innerHTML = "";
    (js.data || []).forEach(sym => {
      const opt = document.createElement("option");
      opt.value = sym; opt.textContent = sym;
      sel.appendChild(opt);
    });
    if (js.data && js.data.length) sel.value = js.data[0];
  } catch (e) {
    console.error("loadSymbols", e);
  }
}

function getSelectedTfs() {
  const sel = qs("tr_timeframes");
  return Array.from(sel.selectedOptions).map(o => o.value);
}

async function startTrain() {
  try {
    const symbol = qs("tr_symbol").value;
    const tfs = getSelectedTfs();
    const years = Number(qs("tr_years").value || 3);
    const mode = qs("tr_mode").value || "auto";
    const optimize = qs("tr_optimize").checked;
    if (!symbol) return;

    setStatus("запуск...", "bg-warning text-dark");
    setProgress(0);
    setMessage("Создание задачи");
    setDetail({ symbol, timeframes: tfs });
    qs("job_log").textContent = "";

    const js = await fetchJson("/api/train", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, timeframes: tfs, years, mode, optimize })
    });
    const jobId = js.job_id;
    if (!jobId) {
      setStatus("ошибка", "bg-danger");
      setMessage("Не удалось создать задачу");
      return;
    }
    localStorage.setItem(LS_JOB_KEY, String(jobId));
    await pollJob(jobId, true);
  } catch (e) {
    console.error("startTrain", e);
    setStatus("ошибка", "bg-danger");
    setMessage(String(e).slice(0, 500));
  }
}

async function syncHistory() {
  try {
    const symbol = qs("tr_symbol").value;
    const tfs = getSelectedTfs();
    const years = Number(qs("tr_years").value || 3);
    setStatus("синхронизация...", "bg-info");
    setMessage("Подкачка истории...");
    await fetchJson("/api/sync_history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, timeframes: tfs, years, force: false })
    });
    setStatus("история готова", "bg-success");
    setMessage("История подкачана");
  } catch (e) {
    console.error("syncHistory", e);
    setStatus("ошибка", "bg-danger");
    setMessage(String(e).slice(0, 500));
  }
}

async function resumeOrDiscoverActive() {
  const saved = localStorage.getItem(LS_JOB_KEY);
  if (saved) {
    const jobId = Number(saved);
    if (Number.isFinite(jobId)) {
      await pollJob(jobId, true);
      return;
    } else {
      localStorage.removeItem(LS_JOB_KEY);
    }
  }
  try {
    const js = await fetchJson("/api/training/active");
    const job = js.data;
    if (job && (job.status === "queued" || job.status === "running")) {
      localStorage.setItem(LS_JOB_KEY, String(job.id));
      await pollJob(job.id, true);
      return;
    }
  } catch (e) {
    console.error("training/active", e);
  }
  setStatus("нет задачи", "bg-secondary");
  setProgress(0);
  setMessage("—");
  setJobIdLabel(null);
  setDetail(null);
}

window.addEventListener("load", async () => {
  await loadSymbols();
  qs("btn_train").addEventListener("click", startTrain);
  qs("btn_sync").addEventListener("click", syncHistory);
  await resumeOrDiscoverActive();
});