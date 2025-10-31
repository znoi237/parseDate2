async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}

function getSelectedTFs() {
  return Array.from(document.querySelectorAll('input[name="tr_tf"]:checked')).map(x => x.value);
}

function setJobBadge(job) {
  const el = document.getElementById("train_job_status");
  if (!el) return;
  if (!job) { el.className = "badge bg-secondary"; el.textContent = "нет задачи"; return; }
  const pct = (job.progress || 0) * 100;
  const pctTxt = pct.toFixed(1).replace('.0','');
  el.className = job.status === "finished" ? "badge bg-success" :
                 job.status === "error" ? "badge bg-danger" :
                 job.status === "queued" ? "badge bg-info text-dark" :
                 "badge bg-warning text-dark";
  el.textContent = job.status === "queued" ? "в очереди" :
                   job.status === "finished" ? "готово" :
                   job.status === "error" ? "ошибка" : `идёт: ${pctTxt}%`;
}

function setProgress(p) {
  const el = document.getElementById("train_progress_bar");
  if (!el) return;
  const pct = Math.max(0, Math.min(100, p * 100));
  el.style.width = pct + "%";
  el.ariaValueNow = String(pct.toFixed(1));
  el.textContent = pct.toFixed(1) + "%";
}

let ACTIVE_JOB_ID = null;
let LAST_LOG_ID = null;
let POLL_TIMER = null;
let LAST_LOG_TS = 0;

async function refreshActive() {
  try {
    const js = await fetchJson("/api/training/active");
    const job = js.data || null;
    setJobBadge(job);
    if (job) {
      ACTIVE_JOB_ID = job.id;
      setProgress(job.progress || 0);
      await pullLogs(job.id);
    }
    // watchdog: если 30 сек не приходят новые логи
    const now = Date.now();
    if (ACTIVE_JOB_ID && now - LAST_LOG_TS > 30000) {
      const pre = document.getElementById("train_logs");
      if (pre && !pre.textContent.endsWith("\n[watchdog] нет новых логов >30s\n")) {
        pre.textContent += "\n[watchdog] нет новых логов >30s\n";
        pre.scrollTop = pre.scrollHeight;
      }
    }
  } catch (e) { /* noop */ }
}

async function pullLogs(jobId) {
  try {
    const q = `/api/training/${jobId}/logs` + (LAST_LOG_ID ? `?since_id=${LAST_LOG_ID}` : "");
    const js = await fetchJson(q);
    const rows = js.data || [];
    if (rows.length) {
      const pre = document.getElementById("train_logs");
      const buf = rows.map(r => `[${r.ts}] ${r.level} ${r.phase}: ${r.message}`).join("\n") + "\n";
      pre.textContent += buf;
      LAST_LOG_ID = rows[rows.length - 1].id;
      LAST_LOG_TS = Date.now();
      pre.scrollTop = pre.scrollHeight;
    }
  } catch (e) { /* noop */ }
}

async function startTrain() {
  const symbol = document.getElementById("tr_symbol").value.trim();
  const mode = document.getElementById("tr_mode").value;
  const years = Number(document.getElementById("tr_years").value || 2);
  const optimize = document.getElementById("tr_opt").value === "true";
  const timeframes = getSelectedTFs();
  if (!symbol) { alert("Укажите тикер"); return; }
  try {
    const js = await fetchJson("/api/train", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ symbol, timeframes, years, mode, optimize })
    });
    ACTIVE_JOB_ID = js.job_id || null;
    LAST_LOG_ID = null;
    LAST_LOG_TS = 0;
    const pre = document.getElementById("train_logs");
    if (pre) pre.textContent = "";
    await refreshActive();
    if (POLL_TIMER) clearInterval(POLL_TIMER);
    POLL_TIMER = setInterval(refreshActive, 2000);
  } catch (e) {
    alert("Ошибка запуска: " + e.message);
  }
}

window.addEventListener("load", () => {
  document.getElementById("btn_train_start")?.addEventListener("click", startTrain);
  document.getElementById("btn_train_refresh")?.addEventListener("click", refreshActive);
  refreshActive();
  POLL_TIMER = setInterval(refreshActive, 4000);
});