async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt  res.statusText);
  return JSON.parse(txt);
}

async function loadNews() {
  const h = Number(document.getElementById(n_hours).value  24);
  const js = await fetchJson(`apinewshours=${encodeURIComponent(h)}`);
  const data = js.data  [];
  const box = document.getElementById(news_list);
  box.innerHTML = ;
  data.forEach(n = {
    const a = document.createElement(a);
    a.className = list-group-item list-group-item-action;
    a.href = n.url  #;
    a.target = _blank;
    const when = n.published_at  new Date(n.published_at).toLocaleString()  ;
    const sent = (n.sentiment !== null && n.sentiment !== undefined)  `  Sent ${Number(n.sentiment).toFixed(2)}`  ;
    const prov = n.provider  ` [${n.provider}]`  ;
    const syms = n.symbols  ` (${n.symbols})`  ;
    a.innerHTML = `divstrong${when}strong${prov}${sent}${syms}divdiv${n.title  ''}div`;
    box.appendChild(a);
  });
}

window.addEventListener(load, () = {
  document.getElementById(news-form).addEventListener(submit, (e)={ e.preventDefault(); loadNews(); });
  loadNews();
});