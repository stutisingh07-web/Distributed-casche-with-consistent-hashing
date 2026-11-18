// Router base URL. Change this if the router runs on another host or port.
const API_BASE = "http://localhost:8000";
const REFRESH_MS = 3000;

const $ = (id) => document.getElementById(id);


function esc(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}


async function api(path, options = {}) {
  const response = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    
  }

  if (!response.ok) {
    const detail = data && data.detail ? data.detail : response.statusText;
    const text = typeof detail === "string" ? detail : JSON.stringify(detail);
    throw new Error(`${response.status}: ${text}`);
  }
  return data;
}

function setStatus(text, ok) {
  const el = $("status");
  el.textContent = text;
  el.style.color = ok ? "#b8f5c8" : "#ffd6d1";
}

function showKeyResult(value) {
  $("key-result").textContent =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function showNodeMessage(text, ok) {
  const el = $("node-message");
  el.textContent = text;
  el.className = "message " + (ok ? "ok" : "error");
}



async function loadStats() {
  const data = await api("/stats");
  const body = $("stats-body");
  body.innerHTML = "";

  for (const [name, s] of Object.entries(data.nodes)) {
    const tr = document.createElement("tr");
    if (s.error) {
      tr.innerHTML = `
        <td>${esc(name)}</td>
        <td colspan="4">-</td>
        <td class="down">DOWN</td>`;
    } else {
      const total = s.hits + s.misses;
      const rate = total ? ((s.hits / total) * 100).toFixed(1) + "%" : "-";
      tr.innerHTML = `
        <td>${esc(name)}</td>
        <td>${s.items} / ${s.max_items}</td>
        <td>${s.hits}</td>
        <td>${s.misses}</td>
        <td>${rate}</td>
        <td class="up">UP</td>`;
    }
    body.appendChild(tr);
  }

  $("total-items").textContent = data.total_items;
}


function getKey() {
  const key = $("key").value.trim();
  if (!key) {
    showKeyResult("Please enter a key first.");
    return null;
  }
  // encodeURIComponent keeps special characters (like "/" or "?") from breaking the URL.
  return encodeURIComponent(key);
}

async function routeKey() {
  const key = getKey();
  if (!key) return;
  try {
    showKeyResult(await api(`/admin/route/${key}`));
  } catch (err) {
    showKeyResult("Error: " + err.message);
  }
}

async function getValue() {
  const key = getKey();
  if (!key) return;
  try {
    showKeyResult(await api(`/cache/${key}`));
  } catch (err) {
    showKeyResult("Error: " + err.message);
  }
}

async function setValue() {
  const key = getKey();
  if (!key) return;

  const value = $("value").value;
  if (value === "") {
    showKeyResult("Please enter a value for Set.");
    return;
  }

  const body = { value };
  const ttl = parseInt($("ttl").value, 10);
  if (!Number.isNaN(ttl) && ttl > 0) {
    body.ttl = ttl;
  }

  try {
    showKeyResult(
      await api(`/cache/${key}`, { method: "PUT", body: JSON.stringify(body) })
    );
    await refreshAll();
  } catch (err) {
    showKeyResult("Error: " + err.message);
  }
}

async function deleteValue() {
  const key = getKey();
  if (!key) return;
  try {
    showKeyResult(await api(`/cache/${key}`, { method: "DELETE" }));
    await refreshAll();
  } catch (err) {
    showKeyResult("Error: " + err.message);
  }
}



async function loadNodes() {
  const data = await api("/admin/nodes");
  const body = $("nodes-body");
  body.innerHTML = "";

  for (const node of data.nodes) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${esc(node.name)}</td>
      <td>${esc(node.url)}</td>
      <td><button class="danger small">Remove</button></td>`;
    tr.querySelector("button").addEventListener("click", () =>
      removeNode(node.name)
    );
    body.appendChild(tr);
  }
}

async function addNode() {
  const name = $("new-name").value.trim();
  const url = $("new-url").value.trim();
  if (!name || !url) {
    showNodeMessage("Enter both a name and a URL.", false);
    return;
  }

  try {
    await api("/admin/nodes", {
      method: "POST",
      body: JSON.stringify({ name, url }),
    });
    showNodeMessage(`Node "${name}" added.`, true);
    $("new-name").value = "";
    $("new-url").value = "";
    await refreshAll();
  } catch (err) {
    showNodeMessage("Error: " + err.message, false);
  }
}

async function removeNode(name) {
  if (!confirm(`Remove node "${name}"? Its keys will be lost.`)) return;
  try {
    await api(`/admin/nodes/${encodeURIComponent(name)}`, { method: "DELETE" });
    showNodeMessage(`Node "${name}" removed.`, true);
    await refreshAll();
  } catch (err) {
    showNodeMessage("Error: " + err.message, false);
  }
}

async function refreshAll() {
  try {
    await Promise.all([loadStats(), loadNodes()]);
    setStatus("Connected to router", true);
  } catch (err) {
    setStatus("Router unreachable: " + err.message, false);
  }
}


$("btn-route").addEventListener("click", routeKey);
$("btn-get").addEventListener("click", getValue);
$("btn-set").addEventListener("click", setValue);
$("btn-delete").addEventListener("click", deleteValue);
$("btn-add-node").addEventListener("click", addNode);

refreshAll();
setInterval(refreshAll, REFRESH_MS);