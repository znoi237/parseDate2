async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}

async function refreshProfilesMenu() {
  try {
    const js = await fetchJson("/api/signal_profiles");
    const data = js.data || { active: "default", profiles: { default: {} } };

    const label = document.getElementById("nav_active_profile");
    if (label) label.textContent = data.active || "default";

    const list = document.getElementById("profile_menu_list");
    if (!list) return;
    list.innerHTML = "";

    const names = Object.keys(data.profiles || {}).sort();
    names.forEach(name => {
      const a = document.createElement("a");
      a.className = "dropdown-item d-flex align-items-center gap-2";
      a.href = "#";
      a.dataset.profile = name;
      a.innerHTML = `${name} ${name === data.active ? '<span class="badge bg-success ms-auto">active</span>' : ""}`;
      a.addEventListener("click", async (ev) => {
        ev.preventDefault();
        try {
          await fetchJson("/api/signal_profiles/activate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name })
          });
          await refreshProfilesMenu();
          window.dispatchEvent(new CustomEvent("profiles:updated"));
        } catch (e) {
          console.error("activate profile", e);
        }
      });
      const li = document.createElement("li");
      li.appendChild(a);
      list.appendChild(li);
    });

    list.appendChild(Object.assign(document.createElement("li"), { innerHTML: '<hr class="dropdown-divider">' }));

    const liNew = document.createElement("li");
    const aNew = document.createElement("a");
    aNew.className = "dropdown-item";
    aNew.href = "#";
    aNew.textContent = "Создать профиль…";
    aNew.addEventListener("click", async (ev) => {
      ev.preventDefault();
      const baseName = prompt("Имя нового профиля:", "custom");
      if (!baseName) return;
      try {
        const activeParams = data.profiles[data.active] || {};
        await fetchJson("/api/signal_profiles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: baseName.trim(), params: activeParams, activate: true })
        });
        await refreshProfilesMenu();
        window.location.href = "/api/settings";
      } catch (e) {
        console.error("create profile", e);
      }
    });
    liNew.appendChild(aNew);
    list.appendChild(liNew);

    const liSett = document.createElement("li");
    const aSett = document.createElement("a");
    aSett.className = "dropdown-item";
    aSett.href = "/api/settings";
    aSett.textContent = "Открыть настройки";
    liSett.appendChild(aSett);
    list.appendChild(liSett);
  } catch (e) {
    console.debug("refreshProfilesMenu", e);
  }
}

async function loadTrainingStatus() {
  try {
    const js = await fetchJson("/api/training/active");
    const job = js.data;
    const el = document.getElementById("train_job_status");
    if (!el) return;
    if (job) {
      const pct = Math.round((job.progress ?? 0) * 100);
      el.className = "badge bg-warning text-dark";
      el.textContent = job.status === "queued" ? "в очереди" : `идёт: ${pct}%`;
      const tfs = (job.timeframes || []).join(", ");
      el.title = `${job.symbol} [${tfs}] ${job.message || ""}`;
    } else {
      el.className = "badge bg-secondary";
      el.textContent = "нет задачи";
      el.title = "";
    }
  } catch (e) {
    console.error("loadTrainingStatus", e);
  }
}

window.addEventListener("load", () => {
  refreshProfilesMenu();
  loadTrainingStatus();
  setInterval(loadTrainingStatus, 10000);
});