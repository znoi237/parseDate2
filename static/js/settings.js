async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}

// -------- API Keys --------
async function loadKeys() {
  const net = document.getElementById("api_network").value || "mainnet";
  try {
    const js = await fetchJson(`/api/keys?network=${encodeURIComponent(net)}`);
    const data = js.data;
    const key = data?.api_key || "";
    const sec = data?.api_secret || "";
    document.getElementById("api_key").value = key;
    document.getElementById("api_secret").value = sec;
    document.getElementById("api_keys_hint").textContent = key || sec ? "Значения замаскированы: сохранены ранее." : "Ключи не заданы.";
  } catch (e) {
    document.getElementById("api_keys_hint").textContent = "Ошибка загрузки ключей: " + e.message;
  }
}

async function saveKeys() {
  const net = document.getElementById("api_network").value || "mainnet";
  const api_key = document.getElementById("api_key").value.trim();
  const api_secret = document.getElementById("api_secret").value.trim();
  if (!api_key || !api_secret) {
    alert("Введите API Key и API Secret");
    return;
  }
  try {
    await fetchJson(`/api/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ network: net, api_key, api_secret })
    });
    document.getElementById("api_keys_hint").textContent = "Сохранено.";
  } catch (e) {
    alert("Ошибка сохранения: " + e.message);
  }
}

// -------- Signal profiles --------
async function refreshProfiles() {
  try {
    const js = await fetchJson("/api/signal_profiles");
    const data = js.data || { active: "default", profiles: { default: {} } };
    document.getElementById("sp_active").textContent = data.active || "default";
    const list = document.getElementById("sp_list");
    list.innerHTML = "";
    Object.keys(data.profiles || {}).sort().forEach(name => {
      const a = document.createElement("a");
      a.href = "#";
      a.className = "list-group-item list-group-item-action d-flex align-items-center";
      a.innerHTML = `
        <span>${name}</span>
        ${name === data.active ? '<span class="badge bg-success ms-auto">active</span>' : '<button class="btn btn-sm btn-outline-secondary ms-auto">Активировать</button>'}
      `;
      if (name !== data.active) {
        a.querySelector("button").addEventListener("click", async (ev) => {
          ev.preventDefault();
          await fetchJson("/api/signal_profiles/activate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name })
          });
          await refreshProfiles();
        });
      }
      list.appendChild(a);
    });
  } catch (e) {
    console.error(e);
  }
}

async function createProfile() {
  const name = document.getElementById("sp_new_name").value.trim();
  if (!name) { alert("Введите имя нового профиля"); return; }
  try {
    const js = await fetchJson("/api/signal_profiles");
    const data = js.data || { active: "default", profiles: {} };
    const params = data.profiles?.[data.active] || {};
    await fetchJson("/api/signal_profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, params, activate: true })
    });
    document.getElementById("sp_new_name").value = "";
    await refreshProfiles();
  } catch (e) {
    alert("Ошибка создания профиля: " + e.message);
  }
}

window.addEventListener("load", () => {
  document.getElementById("api_network").addEventListener("change", loadKeys);
  document.getElementById("btn_load_keys").addEventListener("click", (e)=>{e.preventDefault(); loadKeys();});
  document.getElementById("btn_save_keys").addEventListener("click", (e)=>{e.preventDefault(); saveKeys();});
  document.getElementById("sp_refresh").addEventListener("click", (e)=>{e.preventDefault(); refreshProfiles();});
  document.getElementById("sp_create").addEventListener("click", (e)=>{e.preventDefault(); createProfile();});
  loadKeys();
  refreshProfiles();
});