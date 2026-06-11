// prep.js — list + view + generate weekly prep markdown.

let activeDoc = null;

async function loadPrepList() {
  const list = document.getElementById("prep-list");
  try {
    const res = await fetch("/api/prep");
    const data = await res.json();
    const docs = data.docs || [];
    if (!docs.length) {
      list.innerHTML = `<li class="px-3 py-2 text-slate-500">no docs yet</li>`;
      return;
    }
    list.innerHTML = docs.map((d) => `
      <li class="px-3 py-2 cursor-pointer hover:bg-slate-800 border-b border-slate-800/50 ${d === activeDoc ? "bg-slate-800 text-cyan-400" : ""}"
          data-doc="${d}">${d}</li>
    `).join("");
    list.querySelectorAll("[data-doc]").forEach((li) => {
      li.addEventListener("click", () => loadDoc(li.dataset.doc));
    });
    if (!activeDoc && docs.length) loadDoc(docs[0]);
  } catch (e) {
    list.innerHTML = `<li class="px-3 py-2 text-red-400">${e.message}</li>`;
  }
}

async function loadDoc(name) {
  activeDoc = name;
  const content = document.getElementById("prep-content");
  content.innerHTML = `<div class="text-slate-500">loading ${name}…</div>`;
  try {
    const res = await fetch(`/api/prep/${encodeURIComponent(name)}`);
    const data = await res.json();
    if (!res.ok) {
      content.innerHTML = `<div class="text-red-400">${data.detail || "load failed"}</div>`;
      return;
    }
    const md = data.markdown || "";
    const html = window.marked ? window.marked.parse(md) : `<pre>${md}</pre>`;
    content.innerHTML = `<h1 class="text-cyan-400 text-2xl font-bold mb-4">${name}</h1>${html}`;
    document.querySelectorAll("#prep-list [data-doc]").forEach((li) => {
      li.classList.toggle("bg-slate-800", li.dataset.doc === name);
      li.classList.toggle("text-cyan-400", li.dataset.doc === name);
    });
  } catch (e) {
    content.innerHTML = `<div class="text-red-400">${e.message}</div>`;
  }
}

async function generate() {
  const btn = document.getElementById("prep-generate");
  const status = document.getElementById("prep-status");
  btn.disabled = true;
  btn.textContent = "generating…";
  status.textContent = "Asking Claude — this can take 30–60s.";
  try {
    const res = await fetch("/api/prep", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      status.textContent = data.detail || "generate failed";
      return;
    }
    status.textContent = `generated ${data.name}`;
    activeDoc = data.name;
    await loadPrepList();
    loadDoc(data.name);
  } catch (e) {
    status.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate weekly prep";
  }
}

window.initPrep = function () {
  document.getElementById("prep-generate").addEventListener("click", generate);
  loadPrepList();
};
