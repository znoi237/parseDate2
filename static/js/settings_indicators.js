async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}
function setStatus(msg) { const el = document.getElementById("ind_status"); if (el) el.textContent = msg; }
function setChk(id, v) { const el = document.getElementById(id); if (el) el.checked = !!v; }
function setVal(id, v) { const el = document.getElementById(id); if (el) el.value = v; }
function getChk(id) { const el = document.getElementById(id); return !!el.checked; }
function getNum(id) { const el = document.getElementById(id); return Number(el.value); }
function getText(id) { const el = document.getElementById(id); return String(el.value || ""); }

function csvToNums(s) { return s.split(",").map(x => Number(x.trim())).filter(x => Number.isFinite(x) && x > 0); }
function numsToCsv(a) { return (a||[]).join(","); }

function applyForm(s) {
  setChk("rsi_enabled", s.rsi?.enabled); setVal("rsi_period", s.rsi?.period); setVal("rsi_source", s.rsi?.source || "close");
  setChk("stoch_enabled", s.stoch?.enabled); setVal("stoch_k", s.stoch?.k); setVal("stoch_d", s.stoch?.d); setVal("stoch_smooth", s.stoch?.smooth);
  setChk("macd_enabled", s.macd?.enabled); setVal("macd_fast", s.macd?.fast); setVal("macd_slow", s.macd?.slow); setVal("macd_signal", s.macd?.signal);
  setChk("ema_enabled", s.ema?.enabled); setVal("ema_periods", numsToCsv(s.ema?.periods));
  setChk("sma_enabled", s.sma?.enabled); setVal("sma_periods", numsToCsv(s.sma?.periods));
  setChk("bb_enabled", s.bbands?.enabled); setVal("bb_period", s.bbands?.period); setVal("bb_std", s.bbands?.stddev);
  setChk("atr_enabled", s.atr?.enabled); setVal("atr_period", s.atr?.period);
  setChk("cci_enabled", s.cci?.enabled); setVal("cci_period", s.cci?.period);
  setChk("roc_enabled", s.roc?.enabled); setVal("roc_periods", numsToCsv(s.roc?.periods));
  setChk("willr_enabled", s.willr?.enabled); setVal("willr_period", s.willr?.period);
  setChk("mfi_enabled", s.mfi?.enabled); setVal("mfi_period", s.mfi?.period);
  setChk("obv_enabled", s.obv?.enabled);
  setChk("lags_enabled", s.lags?.enabled); setVal("lags_max", s.lags?.max_lag);
}

function collectForm() {
  return {
    rsi: { enabled: getChk("rsi_enabled"), period: getNum("rsi_period"), source: getText("rsi_source") },
    stoch: { enabled: getChk("stoch_enabled"), k: getNum("stoch_k"), d: getNum("stoch_d"), smooth: getNum("stoch_smooth") },
    macd: { enabled: getChk("macd_enabled"), fast: getNum("macd_fast"), slow: getNum("macd_slow"), signal: getNum("macd_signal") },
    ema: { enabled: getChk("ema_enabled"), periods: csvToNums(getText("ema_periods")) },
    sma: { enabled: getChk("sma_enabled"), periods: csvToNums(getText("sma_periods")) },
    bbands: { enabled: getChk("bb_enabled"), period: getNum("bb_period"), stddev: Number(getText("bb_std")) },
    atr: { enabled: getChk("atr_enabled"), period: getNum("atr_period") },
    cci: { enabled: getChk("cci_enabled"), period: getNum("cci_period") },
    roc: { enabled: getChk("roc_enabled"), periods: csvToNums(getText("roc_periods")) },
    willr: { enabled: getChk("willr_enabled"), period: getNum("willr_period") },
    mfi: { enabled: getChk("mfi_enabled"), period: getNum("mfi_period") },
    obv: { enabled: getChk("obv_enabled") },
    lags: { enabled: getChk("lags_enabled"), max_lag: getNum("lags_max") }
  };
}

async function loadIndicators() {
  try {
    const js = await fetchJson("/api/indicators");
    applyForm(js.data || {});
    setStatus("Загружено");
  } catch (e) {
    console.error(e);
    setStatus("Ошибка загрузки");
  }
}

async function saveIndicators() {
  try {
    const body = collectForm();
    await fetchJson("/api/indicators", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    setStatus("Сохранено");
  } catch (e) {
    console.error(e);
    setStatus("Ошибка сохранения");
  }
}

// Добавляем ссылку в меню (если ещё нет)
function addIndicatorsMenuLink() {
  try {
    const candidates = Array.from(document.querySelectorAll("nav .navbar-nav, .navbar .navbar-nav, ul.navbar-nav"));
    const ul = candidates.find(el => el && el.tagName && el.tagName.toLowerCase() === "ul") || candidates[0];
    if (!ul) return;
    if (!ul.querySelector('a[href="/settings/indicators"]')) {
      const li = document.createElement("li");
      li.className = "nav-item";
      li.innerHTML = `<a class="nav-link" href="/settings/indicators">Индикаторы</a>`;
      ul.appendChild(li);
    }
  } catch (e) {
    console.debug("addIndicatorsMenuLink", e);
  }
}

window.addEventListener("load", async () => {
  document.getElementById("btn_reload_ind").addEventListener("click", loadIndicators);
  document.getElementById("btn_save_ind").addEventListener("click", saveIndicators);
  addIndicatorsMenuLink();
  await loadIndicators();
});