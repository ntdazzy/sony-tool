// Sony Debloat Tool — frontend (vanilla JS)

const API = "";

const STATE = {
  serial: null,
  packages: [],
  packagesByName: new Map(),
  stats: null,
  bloatData: null,
  selectedAll: new Set(),
  selectedTier: "safe",
};

const TIER_ORDER = { safe: 1, recommended: 2, aggressive: 3, optional: 4 };
const TIER_LABEL = {
  safe: "Safe",
  recommended: "Recommended",
  aggressive: "Aggressive",
  optional: "Optional",
};

// Preset áp dụng tự động ở 1-click. Chọn các cái khách quan tốt cho mọi user,
// bỏ qua các cái tuỳ sở thích (font, dark mode, auto-rotate, screen timeout...)
const ONE_CLICK_PRESETS = [
  "animations_off",
  "background_limit_3",
  "cached_processes_limit",
  "disable_wifi_scan_always",
  "wifi_avail_notif_off",
  "disable_telemetry",
  "disable_google_backup",
  "limit_ad_tracking",
  "network_suggestions_off",
  "always_on_display_off",
  "live_caption_off",
];

// ---------- theme ----------

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const btn = document.querySelector("#btn-theme");
  if (btn) btn.textContent = theme === "light" ? "🌙" : "☀️";
  try { localStorage.setItem("sony-tool-theme", theme); } catch (_) {}
}

(function initTheme() {
  let saved = "light";
  try { saved = localStorage.getItem("sony-tool-theme") || "light"; } catch (_) {}
  applyTheme(saved);
})();

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.querySelector("#btn-theme");
  if (!btn) return;
  btn.textContent = document.documentElement.getAttribute("data-theme") === "light" ? "🌙" : "☀️";
  btn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme");
    applyTheme(cur === "light" ? "dark" : "light");
  });
});

// ---------- helpers ----------

const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = `toast-item ${type}`;
  el.textContent = msg;
  $("#toast").appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

// ---------- activity log ----------

const MAX_LOG_ENTRIES = 500;
const LOG_BUFFER = [];

function _logTime(d) {
  const pad = n => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

const _LOG_ICONS = {
  info: "•",
  success: "✓",
  error: "✗",
  warn: "⚠",
  action: "▶",
};

function logEntry(message, type = "info") {
  const time = _logTime(new Date());
  LOG_BUFFER.push({ time, type, message, ts: Date.now() });
  if (LOG_BUFFER.length > MAX_LOG_ENTRIES) LOG_BUFFER.shift();

  const body = $("#log-body");
  if (!body) return;

  // Remove placeholder on first real entry
  const empty = body.querySelector(".log-empty");
  if (empty) empty.remove();

  const div = document.createElement("div");
  div.className = `log-entry ${type}`;
  const t = document.createElement("span"); t.className = "log-time"; t.textContent = time;
  const i = document.createElement("span"); i.className = "log-icon"; i.textContent = _LOG_ICONS[type] || "•";
  const m = document.createElement("span"); m.className = "log-message"; m.textContent = message;
  div.appendChild(t); div.appendChild(i); div.appendChild(m);
  body.appendChild(div);

  // Auto-scroll to newest
  body.scrollTop = body.scrollHeight;

  // Limit DOM nodes
  while (body.children.length > MAX_LOG_ENTRIES) body.removeChild(body.firstChild);

  const countEl = $("#log-count");
  if (countEl) countEl.textContent = `(${LOG_BUFFER.length})`;
}

document.addEventListener("DOMContentLoaded", () => {
  const panel = $("#activity-log");
  const header = $("#log-header");
  if (header && panel) {
    header.addEventListener("click", e => {
      if (e.target.closest(".log-btn")) return;
      panel.classList.toggle("collapsed");
    });
  }
  const clearBtn = $("#log-clear");
  if (clearBtn) clearBtn.addEventListener("click", e => {
    e.stopPropagation();
    LOG_BUFFER.length = 0;
    const body = $("#log-body");
    if (body) body.innerHTML = `<div class="log-empty">Đã xoá log.</div>`;
    $("#log-count").textContent = "(0)";
  });
  const dlBtn = $("#log-download");
  if (dlBtn) dlBtn.addEventListener("click", e => {
    e.stopPropagation();
    if (LOG_BUFFER.length === 0) { toast("Log trống", "warn"); return; }
    const text = LOG_BUFFER
      .map(e => `${e.time}  [${e.type.toUpperCase().padEnd(7)}] ${e.message}`)
      .join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    a.download = `sony-tool-log-${ts}.txt`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 100);
  });
});

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

function openModal({ title, body, confirmText = "Xác nhận", confirmClass = "btn-danger", onConfirm }) {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = body;
  const confirmBtn = $("#modal-confirm");
  confirmBtn.textContent = confirmText;
  confirmBtn.className = confirmClass;
  $("#modal-backdrop").hidden = false;

  const close = () => {
    $("#modal-backdrop").hidden = true;
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
  };

  const newBtn = confirmBtn.cloneNode(true);
  confirmBtn.replaceWith(newBtn);
  newBtn.addEventListener("click", async () => {
    close();
    if (onConfirm) await onConfirm();
  });
  $("#modal-cancel").onclick = close;
  $("#modal-backdrop").onclick = e => { if (e.target.id === "modal-backdrop") close(); };
}

function showLoading(text = "Đang xử lý…") {
  $("#loading-text").textContent = text;
  $("#progress-fill").style.width = "0%";
  $("#loading-overlay").hidden = false;
}
function updateProgress(done, total, text) {
  $("#progress-fill").style.width = `${(done / total) * 100}%`;
  if (text) $("#loading-text").textContent = text;
}
function hideLoading() { $("#loading-overlay").hidden = true; }

// ---------- tabs ----------

$$(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    const id = btn.dataset.tab;
    $$(".tab").forEach(b => b.classList.toggle("active", b === btn));
    $$(".tab-panel").forEach(p => p.classList.toggle("active", p.id === `tab-${id}`));
    if (id === "all" && STATE.packages.length === 0) loadPackages();
    if (id === "backup") loadBackups();
    if (id === "cleanup") refreshCleanupPreview();
    if (id === "optimize" && STATE.serial) loadPresetStates();
    if (id === "apn") loadApnData();
    if (id === "bootloader" && STATE.serial && !STATE.bootloaderChecked) checkBootloader();
    if (id === "rom" && STATE.serial && !STATE.romDetected) detectRomDevice();
  });
});

// ---------- status ----------

async function refreshStatus() {
  $("#status .status-text").textContent = "Đang kiểm tra…";
  $("#status .dot").className = "dot offline";

  try {
    const data = await api("/api/status");

    if (!data.adb_installed) {
      $("#status .status-text").textContent = "Chưa cài ADB";
      $("#device-info").innerHTML = `
        <p style="color: var(--danger)">⚠️ ADB chưa được cài.</p>
        <p>Mở Terminal, chạy:</p>
        <pre style="background:var(--bg-2);padding:10px;border-radius:6px"><code>cd ~/Desktop/sony-tool &amp;&amp; ./setup_adb.sh</code></pre>
      `;
      return;
    }

    if (data.multiple_devices) {
      $("#status .status-text").textContent = "Nhiều máy đang cắm";
      $("#status .dot").className = "dot warn";
      $("#device-info").innerHTML = `<p class="warn">Phát hiện nhiều thiết bị. Vui lòng chỉ cắm 1 máy Sony.</p>`;
      return;
    }

    if (!data.active_serial) {
      $("#status .status-text").textContent = "Chưa cắm máy";
      const devList = data.devices.length
        ? data.devices.map(d => `<li><code>${d.serial}</code> — ${d.state}${d.state==="unauthorized" ? " (mở popup trên máy để cho phép)" : ""}</li>`).join("")
        : "<li>Không thấy máy nào.</li>";
      $("#device-info").innerHTML = `<ul style="padding-left:20px">${devList}</ul><p class="muted">Đảm bảo cáp USB là <b>data cable</b> và đã bật USB Debugging.</p>`;
      return;
    }

    const wasConnected = STATE.serial === data.active_serial;
    STATE.serial = data.active_serial;
    $("#status .dot").className = "dot online";
    $("#status .status-text").textContent = `${data.device_info?.model || data.active_serial}`;
    if (!wasConnected) logEntry(`✓ Kết nối: ${data.device_info?.model || data.active_serial}`, "success");

    const info = data.device_info || {};
    $("#device-info").innerHTML = `
      <table>
        <tr><td>Hãng / Model</td><td><b>${info.manufacturer || "-"} ${info.model || "-"}</b></td></tr>
        <tr><td>Mã thiết bị</td><td><code>${info.device || "-"}</code></td></tr>
        <tr><td>Android</td><td>${info.android_version || "-"} (SDK ${info.sdk || "-"})</td></tr>
        <tr><td>Build</td><td><code>${info.build || "-"}</code></td></tr>
        <tr><td>Serial</td><td><code>${data.active_serial}</code></td></tr>
      </table>
    `;
  } catch (e) {
    $("#status .status-text").textContent = "Lỗi: " + e.message;
    $("#device-info").innerHTML = `<p style="color: var(--danger)">${e.message}</p>`;
  }
}

$("#btn-refresh").addEventListener("click", async () => {
  await refreshStatus();
  if (STATE.serial) {
    await loadPackages();
  }
});

// ---------- stats ----------

function renderStats() {
  if (!STATE.stats) {
    ["total","enabled","disabled","bloat"].forEach(k => $(`#stat-${k}`).textContent = "—");
    return;
  }
  $("#stat-total").textContent = STATE.stats.total;
  $("#stat-enabled").textContent = STATE.stats.enabled;
  $("#stat-disabled").textContent = STATE.stats.disabled;
  $("#stat-bloat").textContent = STATE.stats.bloat_active;
}

// ---------- packages ----------

async function loadPackages() {
  if (!STATE.serial) {
    toast("Chưa kết nối máy", "warn");
    return;
  }
  showLoading("Đang đọc danh sách app từ máy…");
  try {
    const data = await api(`/api/packages?serial=${encodeURIComponent(STATE.serial)}`);
    STATE.packages = data.packages;
    STATE.stats = data.stats;
    STATE.packagesByName = new Map(data.packages.map(p => [p.name, p]));
    renderStats();
    renderPackagesTable();
    refreshCleanupPreview();
    logEntry(`Đọc xong ${data.stats.total} app (${data.stats.enabled} bật, ${data.stats.disabled} tắt, ${data.stats.bloat_active} bloat còn chạy)`, "info");
  } catch (e) {
    toast("Lỗi tải app: " + e.message, "error");
    logEntry(`Đọc danh sách app lỗi: ${e.message}`, "error");
  } finally {
    hideLoading();
  }
}

function renderPackagesTable() {
  const search = $("#search-input").value.toLowerCase().trim();
  const filter = $("#filter-select").value;

  let list = STATE.packages;
  if (search) list = list.filter(p => p.name.toLowerCase().includes(search) || (p.label || "").toLowerCase().includes(search));
  if (filter === "user") list = list.filter(p => !p.is_system);
  else if (filter === "system") list = list.filter(p => p.is_system);
  else if (filter === "disabled") list = list.filter(p => !p.enabled);
  else if (filter === "enabled") list = list.filter(p => p.enabled);
  else if (filter === "bloat") list = list.filter(p => p.bloat_category);
  else if (filter === "critical") list = list.filter(p => p.is_critical);

  const tbody = $("#packages-table tbody");
  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted center">Không có app nào khớp.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(p => `
    <tr class="${p.is_critical ? "row-critical" : ""}">
      <td>
        <input type="checkbox" class="row-check"
               data-name="${p.name}"
               ${p.is_critical ? "disabled title='App cốt lõi — không cho tắt'" : ""}
               ${STATE.selectedAll.has(p.name) ? "checked" : ""}>
      </td>
      <td>
        ${p.label ? `<b>${p.label}</b><br>` : ""}
        <code>${p.name}</code>
      </td>
      <td>${p.is_system ? "Hệ thống" : "Tải về"}</td>
      <td>
        <span class="pkg-tag ${p.enabled ? "enabled" : "disabled"}">${p.enabled ? "Đang bật" : "Đã tắt"}</span>
        ${p.is_critical ? '<span class="pkg-tag critical">Cốt lõi</span>' : ""}
        ${p.bloat_tier ? `<span class="pkg-tag tier-${p.bloat_tier}">${TIER_LABEL[p.bloat_tier] || p.bloat_tier}</span>` : ""}
      </td>
      <td>
        ${p.enabled
          ? `<button class="btn-sm btn-danger" data-act="disable" data-name="${p.name}" ${p.is_critical ? "disabled" : ""}>Tắt</button>`
          : `<button class="btn-sm btn-secondary" data-act="enable" data-name="${p.name}">Bật</button>`}
      </td>
    </tr>
  `).join("");

  tbody.querySelectorAll(".row-check").forEach(cb => {
    cb.addEventListener("change", e => {
      const n = e.target.dataset.name;
      if (e.target.checked) STATE.selectedAll.add(n); else STATE.selectedAll.delete(n);
      $("#all-selection-count").textContent = `Đã chọn: ${STATE.selectedAll.size}`;
    });
  });

  tbody.querySelectorAll("button[data-act]").forEach(btn => {
    btn.addEventListener("click", () => doSingleAction(btn.dataset.act, btn.dataset.name));
  });
}

$("#search-input").addEventListener("input", () => renderPackagesTable());
$("#filter-select").addEventListener("change", () => renderPackagesTable());
$("#btn-reload-all").addEventListener("click", () => loadPackages());

$("#check-all").addEventListener("change", e => {
  $$("#packages-table tbody .row-check:not(:disabled)").forEach(cb => {
    cb.checked = e.target.checked;
    const n = cb.dataset.name;
    if (e.target.checked) STATE.selectedAll.add(n); else STATE.selectedAll.delete(n);
  });
  $("#all-selection-count").textContent = `Đã chọn: ${STATE.selectedAll.size}`;
});

async function doSingleAction(action, pkg) {
  const verb = action === "disable" ? "Tắt" : "Bật";
  const endpoint = action === "disable" ? "/api/packages/disable" : "/api/packages/enable";
  try {
    const data = await api(endpoint, {
      method: "POST",
      body: JSON.stringify({ packages: [pkg], serial: STATE.serial }),
    });
    const r = data.results[0];
    if (r.ok) {
      toast(`${verb} ${pkg}: OK`, "success");
      logEntry(`${verb} ${pkg}`, "success");
      const p = STATE.packagesByName.get(pkg);
      if (p) p.enabled = action === "enable";
      renderPackagesTable();
      renderStats();
      refreshCleanupPreview();
    } else {
      toast(`Lỗi: ${r.message}`, "error");
      logEntry(`${verb} ${pkg} thất bại: ${r.message}`, "error");
    }
  } catch (e) {
    toast("Lỗi: " + e.message, "error");
    logEntry(`${verb} ${pkg} lỗi: ${e.message}`, "error");
  }
}

async function bulkDisable(packages, label = "app") {
  if (packages.length === 0) {
    toast("Chưa chọn app nào", "warn");
    return;
  }

  logEntry(`▶ Bắt đầu tắt ${packages.length} ${label}`, "action");
  showLoading(`Đang tắt ${packages.length} ${label}…`);
  let done = 0;
  let ok = 0;
  let fail = 0;
  const failures = [];

  const batchSize = 10;
  for (let i = 0; i < packages.length; i += batchSize) {
    const batch = packages.slice(i, i + batchSize);
    try {
      const data = await api("/api/packages/disable", {
        method: "POST",
        body: JSON.stringify({ packages: batch, serial: STATE.serial }),
      });
      data.results.forEach(r => {
        if (r.ok) {
          ok++;
          logEntry(`Tắt ${r.package}`, "success");
        } else {
          fail++;
          failures.push(`${r.package}: ${r.message}`);
          logEntry(`Tắt ${r.package} lỗi: ${r.message}`, "error");
        }
      });
    } catch (e) {
      fail += batch.length;
      failures.push(`Batch lỗi: ${e.message}`);
      logEntry(`Batch ${i}-${i + batch.length} lỗi: ${e.message}`, "error");
    }
    done += batch.length;
    updateProgress(done, packages.length, `Đang tắt… ${done}/${packages.length}`);
  }

  hideLoading();
  toast(`Hoàn tất: ${ok} tắt, ${fail} lỗi`, fail === 0 ? "success" : "warn");
  logEntry(`Hoàn tất tắt: ${ok}/${packages.length} OK${fail ? `, ${fail} lỗi` : ""}`, fail === 0 ? "success" : "warn");
  if (failures.length) console.warn("Failures:\n" + failures.join("\n"));
  await loadPackages();
}

async function bulkEnable(packages) {
  if (packages.length === 0) {
    toast("Chưa chọn app nào", "warn");
    return;
  }
  logEntry(`▶ Bắt đầu bật ${packages.length} app`, "action");
  showLoading(`Đang bật ${packages.length} app…`);
  try {
    const data = await api("/api/packages/enable", {
      method: "POST",
      body: JSON.stringify({ packages, serial: STATE.serial }),
    });
    let ok = 0;
    data.results.forEach(r => {
      if (r.ok) { ok++; logEntry(`Bật ${r.package}`, "success"); }
      else logEntry(`Bật ${r.package} lỗi: ${r.message}`, "error");
    });
    toast(`Bật xong: ${ok}/${packages.length}`, "success");
    logEntry(`Hoàn tất bật: ${ok}/${packages.length}`, ok === packages.length ? "success" : "warn");
  } catch (e) {
    toast("Lỗi: " + e.message, "error");
    logEntry(`Bật lỗi: ${e.message}`, "error");
  } finally {
    hideLoading();
    await loadPackages();
  }
}

$("#btn-bulk-disable").addEventListener("click", () => {
  const pkgs = [...STATE.selectedAll];
  openModal({
    title: "Xác nhận tắt",
    body: `Bạn sẽ tắt <b>${pkgs.length}</b> app. App vẫn còn trong máy, có thể bật lại bất cứ lúc nào. Tiếp tục?`,
    confirmText: "Tắt",
    onConfirm: async () => {
      await bulkDisable(pkgs);
      STATE.selectedAll.clear();
    },
  });
});

$("#btn-bulk-enable").addEventListener("click", async () => {
  await bulkEnable([...STATE.selectedAll]);
  STATE.selectedAll.clear();
});

// ---------- bloat data & cleanup ----------

async function loadBloatData() {
  if (STATE.bloatData) return STATE.bloatData;
  STATE.bloatData = await api("/api/bloat-list");
  return STATE.bloatData;
}

function tierIncludedIn(packageTier, selectedTier) {
  // selectedTier: safe | recommended | aggressive | nuclear
  if (selectedTier === "safe") return packageTier === "safe";
  if (selectedTier === "recommended") return ["safe", "recommended"].includes(packageTier);
  if (selectedTier === "aggressive") return ["safe", "recommended", "aggressive"].includes(packageTier);
  if (selectedTier === "nuclear") return ["safe", "recommended", "aggressive", "optional"].includes(packageTier);
  return false;
}

async function refreshCleanupPreview() {
  const data = await loadBloatData();
  const selected = STATE.selectedTier;

  // Đếm cho từng tier card
  for (const tier of ["safe", "recommended", "aggressive", "nuclear"]) {
    let count = 0;
    for (const cat of data.categories) {
      for (const pkg of cat.packages) {
        if (!tierIncludedIn(pkg.tier, tier)) continue;
        const p = STATE.packagesByName.get(pkg.id);
        if (p && p.enabled) count++;
      }
    }
    const el = document.querySelector(`.tier-count[data-tier="${tier}"]`);
    if (el) el.textContent = `${count} app sẽ tắt`;
  }

  // Render preview list cho tier hiện tại
  const grouped = [];
  let totalCount = 0;
  for (const cat of data.categories) {
    const pkgsInCat = [];
    for (const pkg of cat.packages) {
      if (!tierIncludedIn(pkg.tier, selected)) continue;
      const p = STATE.packagesByName.get(pkg.id);
      if (!p || !p.enabled) continue;
      pkgsInCat.push(pkg);
      totalCount++;
    }
    if (pkgsInCat.length) grouped.push({ cat, pkgs: pkgsInCat });
  }

  $("#cleanup-count").textContent = totalCount;
  $("#btn-do-cleanup").disabled = totalCount === 0;

  let warning = "";
  if (totalCount === 0 && STATE.packages.length === 0) {
    warning = "⚠️ Chưa kết nối máy — bấm ↻ ở góc trên phải.";
  } else if (totalCount === 0) {
    warning = "✨ Không còn bloat ở mức này — máy đã sạch!";
  } else if (selected === "nuclear") {
    warning = "☢️ Mức tối đa — kiểm tra danh sách kỹ trước khi tắt.";
  } else if (selected === "aggressive") {
    warning = "⚠️ Mức mạnh — sẽ tắt cả service hệ thống phụ.";
  }
  $("#cleanup-warning").textContent = warning;

  // Cập nhật 1-click stats
  let nuclearCount = 0;
  for (const cat of data.categories) {
    for (const pkg of cat.packages) {
      if (!tierIncludedIn(pkg.tier, "nuclear")) continue;
      const p = STATE.packagesByName.get(pkg.id);
      if (p && p.enabled) nuclearCount++;
    }
  }
  const ocBloat = $("#oc-bloat-count");
  const ocPreset = $("#oc-preset-count");
  if (ocBloat) ocBloat.textContent = nuclearCount;
  if (ocPreset) ocPreset.textContent = ONE_CLICK_PRESETS.length;
  const oneClickBtn = $("#btn-one-click");
  if (oneClickBtn) oneClickBtn.disabled = !STATE.serial;

  const listEl = $("#cleanup-list");
  listEl.innerHTML = grouped.map(g => `
    <div class="preview-group">
      <div class="preview-group-title">${g.cat.icon || ""} ${g.cat.title} (${g.pkgs.length})</div>
      ${g.pkgs.map(p => `<div class="preview-pkg">${p.label} <code style="font-size:10px;color:var(--text-mute)">${p.id}</code></div>`).join("")}
    </div>
  `).join("");
}

document.querySelectorAll('input[name="tier"]').forEach(radio => {
  radio.addEventListener("change", e => {
    STATE.selectedTier = e.target.value;
    refreshCleanupPreview();
  });
});

$("#btn-toggle-preview").addEventListener("click", () => {
  const list = $("#cleanup-list");
  list.hidden = !list.hidden;
  $("#btn-toggle-preview").textContent = list.hidden ? "Xem danh sách ▾" : "Ẩn danh sách ▴";
});

$("#btn-do-cleanup").addEventListener("click", async () => {
  if (!STATE.serial) {
    toast("Chưa kết nối máy", "warn");
    return;
  }
  const data = await loadBloatData();
  const toDisable = [];
  for (const cat of data.categories) {
    for (const pkg of cat.packages) {
      if (!tierIncludedIn(pkg.tier, STATE.selectedTier)) continue;
      const p = STATE.packagesByName.get(pkg.id);
      if (p && p.enabled) toDisable.push(pkg.id);
    }
  }

  if (toDisable.length === 0) {
    toast("Không có gì để tắt", "warn");
    return;
  }

  openModal({
    title: `Dọn sạch — tắt ${toDisable.length} app?`,
    body: `
      <p>Tool sẽ tắt <b>${toDisable.length} app</b> ở mức "<b>${$("input[name='tier']:checked").nextElementSibling.querySelector(".tier-name").textContent.trim()}</b>".</p>
      <p>Mọi thao tác <b>khôi phục được</b>. Sau khi tắt nên:</p>
      <ol>
        <li>Khởi động lại máy</li>
        <li>Dùng 1-2 ngày để kiểm tra</li>
        <li>Nếu thiếu chức năng → vào "Tất cả app" → lọc "Đã tắt" → bật lại</li>
      </ol>
    `,
    confirmText: "🧹 Bắt đầu tắt",
    confirmClass: "btn-primary",
    onConfirm: () => bulkDisable(toDisable, "app rác"),
  });
});

// (Hero "Bắt đầu dọn sạch" button removed in v2 redesign — cleanup tab is now reached via top nav)
$("#btn-hero-cleanup")?.addEventListener("click", () => {
  $$(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === "cleanup"));
  $$(".tab-panel").forEach(p => p.classList.toggle("active", p.id === "tab-cleanup"));
  refreshCleanupPreview();
});

// ---------- 1-CLICK ----------

$("#btn-one-click").addEventListener("click", async () => {
  if (!STATE.serial) {
    toast("Chưa kết nối máy — bấm ↻ ở góc trên phải", "warn");
    return;
  }
  const data = await loadBloatData();
  const bloatPkgs = [];
  for (const cat of data.categories) {
    for (const pkg of cat.packages) {
      if (!tierIncludedIn(pkg.tier, "nuclear")) continue;
      const p = STATE.packagesByName.get(pkg.id);
      if (p && p.enabled) bloatPkgs.push(pkg.id);
    }
  }

  const mode = document.querySelector('input[name="oc-mode"]:checked').value;
  const modeLabel = mode === "uninstall" ? "🗑️ Gỡ hẳn" : "Tắt";

  openModal({
    title: `🚀 Tinh giản 1-click — ${modeLabel}?`,
    body: `
      <p>Tool sẽ tự động:</p>
      <ol>
        <li>💾 Tạo backup trạng thái hiện tại</li>
        <li>${mode === "uninstall" ? "🗑️" : "🧹"} <b>${modeLabel} ${bloatPkgs.length} app rác</b> ${mode === "uninstall" ? "(xoá app data, APK vẫn trong /system)" : "(ẩn app, dữ liệu vẫn còn)"}</li>
        <li>⚡ Áp dụng <b>${ONE_CLICK_PRESETS.length} tối ưu khách quan</b> (animation, RAM, Wi-Fi scan, telemetry…)</li>
        <li>🔄 Đề nghị khởi động lại máy</li>
      </ol>
      <p>App quan trọng (<b>CH Play, Google Services, Phone, Camera, System UI</b>) được bảo vệ — không bị động.</p>
      <p>Cần app gì sau khi xong → cài lại từ CH Play, app mới sạch.</p>
    `,
    confirmText: `🚀 Bắt đầu ${modeLabel}`,
    confirmClass: "btn-primary",
    onConfirm: () => doOneClick(bloatPkgs, mode),
  });
});

async function doOneClick(bloatPkgs, mode = "uninstall") {
  const endpoint = mode === "uninstall" ? "/api/packages/uninstall" : "/api/packages/disable";
  const verb = mode === "uninstall" ? "Gỡ" : "Tắt";
  const totalSteps = 1 + bloatPkgs.length + ONE_CLICK_PRESETS.length;
  let stepDone = 0;
  const tick = (label) => {
    stepDone++;
    updateProgress(stepDone, totalSteps, label);
  };

  logEntry(`🚀 Tinh giản 1-click bắt đầu (${verb} ${bloatPkgs.length} app + ${ONE_CLICK_PRESETS.length} preset)`, "action");

  // Auto-expand log nếu đang collapsed
  $("#activity-log")?.classList.remove("collapsed");

  showLoading(`Bước 1/3: Tạo backup…`);
  try {
    const backupData = await api(`/api/backup?serial=${encodeURIComponent(STATE.serial)}`);
    tick("Backup xong");
    logEntry(`💾 Backup tạo xong: ${backupData.file}`, "success");
  } catch (e) {
    hideLoading();
    toast("Backup thất bại: " + e.message, "error");
    logEntry(`💾 Backup thất bại: ${e.message}`, "error");
    return;
  }

  // Step 2: disable hoặc uninstall bloat theo batch 15
  const batchSize = 15;
  let okBloat = 0, failBloat = 0;
  const failures = [];
  for (let i = 0; i < bloatPkgs.length; i += batchSize) {
    const batch = bloatPkgs.slice(i, i + batchSize);
    try {
      const data = await api(endpoint, {
        method: "POST",
        body: JSON.stringify({ packages: batch, serial: STATE.serial }),
      });
      data.results.forEach(r => {
        if (r.ok) {
          okBloat++;
          logEntry(`${verb} ${r.package}`, "success");
        } else {
          failBloat++;
          failures.push(`${r.package}: ${r.message}`);
          logEntry(`${verb} ${r.package} lỗi: ${r.message}`, "error");
        }
      });
    } catch (e) {
      failBloat += batch.length;
      failures.push(`Batch error: ${e.message}`);
      logEntry(`Batch lỗi: ${e.message}`, "error");
    }
    stepDone += batch.length;
    updateProgress(stepDone, totalSteps, `Bước 2/3: ${verb} app rác (${okBloat}/${bloatPkgs.length})…`);
  }

  logEntry(`✅ ${verb} app rác xong: ${okBloat}/${bloatPkgs.length}${failBloat ? `, ${failBloat} lỗi` : ""}`, failBloat === 0 ? "success" : "warn");

  // Step 3: áp dụng presets
  let okPreset = 0, failPreset = 0;
  for (const presetId of ONE_CLICK_PRESETS) {
    try {
      const presetData = await api("/api/optimize/apply", {
        method: "POST",
        body: JSON.stringify({ preset_id: presetId, serial: STATE.serial }),
      });
      const stepFails = (presetData.results || []).filter(r => !r.ok).length;
      if (stepFails === 0) {
        okPreset++;
        logEntry(`⚡ Áp dụng ${presetId}`, "success");
      } else {
        failPreset++;
        logEntry(`⚡ ${presetId} áp dụng 1 phần (${stepFails} step lỗi)`, "warn");
      }
    } catch (e) {
      failPreset++;
      failures.push(`Preset ${presetId}: ${e.message}`);
      logEntry(`⚡ ${presetId} lỗi: ${e.message}`, "error");
    }
    tick(`Bước 3/3: Tối ưu (${okPreset}/${ONE_CLICK_PRESETS.length})…`);
  }

  hideLoading();

  logEntry(`✨ Hoàn tất 1-click: ${okBloat} app + ${okPreset} preset thành công`, "success");

  if (failures.length) console.warn("1-click failures:\n" + failures.join("\n"));

  await loadPackages();

  openModal({
    title: "✨ Tinh giản hoàn tất!",
    body: `
      <p><b>Kết quả:</b></p>
      <ul>
        <li>✅ ${verb} <b>${okBloat}</b> app rác${failBloat ? ` (${failBloat} không thành công — xem console)` : ""}</li>
        <li>✅ Áp dụng <b>${okPreset}</b> tối ưu${failPreset ? ` (${failPreset} không thành công)` : ""}</li>
        <li>💾 Backup lưu tại <code>~/Desktop/sony-tool/backups/</code></li>
      </ul>
      <p>Bấm <b>Khởi động lại máy</b> để áp dụng toàn bộ. Sau khi máy bật lại, bạn sẽ thấy:</p>
      <ul>
        <li>Animation tắt → chạm là phản hồi tức thì</li>
        <li>RAM trống nhiều → app mở nhanh</li>
        <li>Background ít → pin trâu hơn</li>
        <li>Không còn bloat trong app drawer</li>
      </ul>
    `,
    confirmText: "🔄 Khởi động lại máy",
    confirmClass: "btn-primary",
    onConfirm: async () => {
      try {
        await api(`/api/reboot?serial=${encodeURIComponent(STATE.serial)}`, { method: "POST" });
        toast("Máy đang khởi động lại… đợi 30-60s rồi bấm ↻", "success");
      } catch (e) {
        toast("Lỗi reboot: " + e.message + ". Khởi động lại thủ công.", "warn");
      }
    },
  });
}

// ---------- optimize presets ----------

async function loadPresets() {
  try {
    const data = await api("/api/optimize/presets");
    // Nhóm theo category
    const groups = {};
    data.presets.forEach(p => {
      const cat = p.category || "Khác";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(p);
    });

    const html = Object.entries(groups).map(([cat, items]) => `
      <div class="preset-group">
        <h3 class="preset-group-title">${cat}</h3>
        ${items.map(p => `
          <div class="preset-item" data-preset-id="${p.id}">
            <div class="preset-head">
              <span class="preset-icon">${p.icon || "⚙️"}</span>
              <h4>${p.title}</h4>
              <span class="preset-state preset-state-unknown" data-state-badge>—</span>
            </div>
            <p>${p.description}</p>
            ${p.warning ? `<p class="preset-warning">⚠️ ${p.warning}</p>` : ""}
            <div class="preset-actions">
              <button class="btn-primary btn-sm" data-action="apply" data-id="${p.id}">Áp dụng</button>
              <button class="btn-secondary btn-sm" data-action="revert" data-id="${p.id}">Khôi phục</button>
            </div>
          </div>
        `).join("")}
      </div>
    `).join("");

    $("#presets-list").innerHTML = html;

    $$(".preset-item button").forEach(btn => {
      btn.addEventListener("click", async () => {
        await applyPreset(btn.dataset.id, btn.dataset.action);
        // Refresh state badge sau khi apply/revert
        if (STATE.serial) loadPresetStates();
      });
    });

    // Load state ngay nếu có device
    if (STATE.serial) loadPresetStates();
  } catch (e) {
    $("#presets-list").innerHTML = `<p style="color: var(--danger)">Lỗi: ${e.message}</p>`;
  }
}

const STATE_LABEL = {
  applied: "Đã áp dụng",
  default: "Mặc định",
  partial: "1 phần",
  unknown: "—",
};

async function loadPresetStates() {
  if (!STATE.serial) return;
  try {
    const data = await api(`/api/optimize/state?serial=${encodeURIComponent(STATE.serial)}`);
    for (const ps of data.presets) {
      const item = document.querySelector(`.preset-item[data-preset-id="${ps.id}"]`);
      if (!item) continue;
      const badge = item.querySelector("[data-state-badge]");
      if (!badge) continue;
      badge.className = `preset-state preset-state-${ps.state}`;
      badge.textContent = STATE_LABEL[ps.state] || ps.state;
      // Tooltip với chi tiết
      const detail = ps.steps
        .filter(s => "matches" in s && s.matches !== null)
        .map(s => `${s.namespace || s.type}/${s.key || s.command}: ${s.current ?? "?"} → ${s.expected ?? "?"}`)
        .join("\n");
      if (detail) badge.title = detail;
    }
    logEntry(`Đọc state ${data.presets.length} preset từ máy`, "info");
  } catch (e) {
    // Không log lỗi to — chỉ silent fail, state vẫn unknown
    console.warn("loadPresetStates:", e.message);
  }
}

async function applyPreset(id, action) {
  if (!STATE.serial) {
    toast("Chưa kết nối máy", "warn");
    return;
  }
  const verb = action === "apply" ? "⚡ Áp dụng" : "↩ Khôi phục";
  try {
    const data = await api(`/api/optimize/${action}`, {
      method: "POST",
      body: JSON.stringify({ preset_id: id, serial: STATE.serial }),
    });
    const ok = data.results.filter(r => r.ok).length;
    const total = data.results.length;
    const fail = total - ok;
    toast(`${verb} "${data.preset}": ${ok} ok${fail ? ", " + fail + " lỗi" : ""}`, fail === 0 ? "success" : "warn");
    logEntry(`${verb} "${data.preset}" (${ok}/${total})`, fail === 0 ? "success" : "warn");
    // Chi tiết từng step nếu fail
    if (fail > 0) {
      data.results.filter(r => !r.ok).forEach(r => logEntry(`  ↳ step lỗi: ${r.step}: ${r.message}`, "error"));
    }
  } catch (e) {
    toast("Lỗi: " + e.message, "error");
    logEntry(`${verb} preset ${id} lỗi: ${e.message}`, "error");
  }
}

// ---------- backup ----------

$("#btn-export-full").addEventListener("click", async () => {
  if (!STATE.serial) {
    toast("Chưa kết nối máy", "warn");
    return;
  }
  showLoading("Đang đọc package + services + getprop + settings…");
  logEntry("📤 Bắt đầu export chi tiết…", "action");
  try {
    const data = await api(`/api/export-full?serial=${encodeURIComponent(STATE.serial)}`);
    $("#export-status").innerHTML = `
      <p style="color: var(--success);margin-top:12px">✅ Xong: <code>${data.file}</code> (${data.size_kb} KB, ${data.count} packages)</p>
      <p class="muted">Đường dẫn: <code>${data.path}</code></p>
      <p class="muted">📤 Gửi file này cho dev qua chat.</p>
    `;
    toast("Export OK", "success");
    logEntry(`📤 Export: ${data.file} (${data.size_kb} KB, ${data.count} packages)`, "success");
    loadBackups();
  } catch (e) {
    toast("Lỗi export: " + e.message, "error");
    logEntry(`📤 Export lỗi: ${e.message}`, "error");
  } finally {
    hideLoading();
  }
});

$("#btn-create-backup").addEventListener("click", async () => {
  if (!STATE.serial) {
    toast("Chưa kết nối máy", "warn");
    return;
  }
  try {
    const data = await api(`/api/backup?serial=${encodeURIComponent(STATE.serial)}`);
    $("#backup-status").innerHTML = `<p style="color: var(--success);margin-top:12px">✅ Đã tạo: <code>${data.file}</code> (${data.count} app)</p>`;
    toast("Backup OK", "success");
    logEntry(`💾 Backup: ${data.file} (${data.count} app)`, "success");
    loadBackups();
  } catch (e) {
    toast("Lỗi backup: " + e.message, "error");
    logEntry(`💾 Backup lỗi: ${e.message}`, "error");
  }
});

async function loadBackups() {
  try {
    const data = await api("/api/backups");
    if (data.backups.length === 0) {
      $("#backup-list").innerHTML = `<p class="muted">Chưa có backup nào.</p>`;
      return;
    }
    $("#backup-list").innerHTML = `
      <ul style="padding-left:20px">
        ${data.backups.map(b => `<li><code>${b.name}</code> <span class="muted">(${b.size_kb} KB)</span></li>`).join("")}
      </ul>
      <p class="muted" style="margin-top:10px">File lưu trong <code>~/Desktop/sony-tool/backups/</code></p>
    `;
  } catch (e) {
    $("#backup-list").innerHTML = `<p style="color: var(--danger)">Lỗi: ${e.message}</p>`;
  }
}

// ---------- INSIGHTS ----------

function _humanSize(bytes) {
  if (!bytes || bytes < 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0, v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`;
}

function _humanCpuTime(ms) {
  if (!ms || ms < 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)} s`;
  const min = sec / 60;
  if (min < 60) return `${min.toFixed(1)} min`;
  return `${(min / 60).toFixed(1)} h`;
}

async function loadStorageInsights() {
  if (!STATE.serial) { toast("Chưa kết nối máy", "warn"); return; }
  showLoading("Đang đọc disk stats (5-15s)…");
  logEntry("💾 Đang tải app storage stats…", "action");
  try {
    const data = await api(`/api/insights/storage?serial=${encodeURIComponent(STATE.serial)}`);
    const apps = data.apps || [];
    if (apps.length === 0) {
      $("#storage-list").innerHTML = `<p class="muted">${data.warning || "Không có dữ liệu"}</p>`;
      return;
    }
    const totalBytes = apps.reduce((s, a) => s + a.total_bytes, 0);
    $("#storage-summary").textContent = `${apps.length} app, tổng ${_humanSize(totalBytes)}`;
    $("#storage-list").innerHTML = `
      <div class="table-wrap" style="max-height:480px">
        <table>
          <thead><tr><th>#</th><th>App</th><th>APK</th><th>Data</th><th>Cache</th><th>Tổng</th></tr></thead>
          <tbody>
            ${apps.map((a, i) => `
              <tr>
                <td>${i + 1}</td>
                <td><code>${a.name}</code></td>
                <td>${_humanSize(a.apk_bytes)}</td>
                <td>${_humanSize(a.data_bytes)}</td>
                <td>${_humanSize(a.cache_bytes)}</td>
                <td><b>${_humanSize(a.total_bytes)}</b></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
    logEntry(`💾 Đã load ${apps.length} app, tổng ${_humanSize(totalBytes)}`, "success");
  } catch (e) {
    toast("Lỗi: " + e.message, "error");
    logEntry(`💾 Storage load lỗi: ${e.message}`, "error");
  } finally {
    hideLoading();
  }
}

async function loadBatteryInsights() {
  if (!STATE.serial) { toast("Chưa kết nối máy", "warn"); return; }
  showLoading("Đang đọc battery stats (10-30s)…");
  logEntry("🔋 Đang tải battery stats…", "action");
  try {
    const data = await api(`/api/insights/battery?serial=${encodeURIComponent(STATE.serial)}`);
    const apps = data.top || [];
    if (apps.length === 0) {
      $("#battery-list").innerHTML = `<p class="muted">Chưa có dữ liệu — chạy "Reset stats" rồi dùng máy 1 ngày.</p>`;
      return;
    }
    $("#battery-list").innerHTML = `
      <div class="table-wrap" style="max-height:400px;margin-top:12px">
        <table>
          <thead><tr><th>#</th><th>Package</th><th>UID</th><th>CPU time</th></tr></thead>
          <tbody>
            ${apps.map((a, i) => `
              <tr>
                <td>${i + 1}</td>
                <td><code>${a.package}</code></td>
                <td class="muted tiny">${a.uid}</td>
                <td><b>${_humanCpuTime(a.cpu_ms)}</b></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
    logEntry(`🔋 Đã load top ${apps.length} app tốn CPU`, "success");
  } catch (e) {
    toast("Lỗi: " + e.message, "error");
    logEntry(`🔋 Battery load lỗi: ${e.message}`, "error");
  } finally {
    hideLoading();
  }
}

async function resetBatteryStats() {
  if (!STATE.serial) { toast("Chưa kết nối máy", "warn"); return; }
  openModal({
    title: "Reset battery stats?",
    body: `<p>Sẽ xoá toàn bộ tracking cũ. Sau đó dùng máy bình thường 24h rồi quay lại đây bấm "Tải" để xem top app tốn pin.</p>`,
    confirmText: "⟲ Reset",
    confirmClass: "btn-warning",
    onConfirm: async () => {
      try {
        await api(`/api/insights/battery-reset?serial=${encodeURIComponent(STATE.serial)}`, { method: "POST" });
        toast("Battery stats đã reset", "success");
        logEntry("🔋 Battery stats reset", "success");
        $("#battery-list").innerHTML = `<p class="muted">✓ Đã reset. Dùng máy 24h rồi quay lại đây.</p>`;
      } catch (e) {
        toast("Lỗi: " + e.message, "error");
      }
    },
  });
}

async function loadNotificationInsights() {
  if (!STATE.serial) { toast("Chưa kết nối máy", "warn"); return; }
  showLoading("Đang đọc notification stats…");
  logEntry("🔔 Đang tải notification stats…", "action");
  try {
    const data = await api(`/api/insights/notifications?serial=${encodeURIComponent(STATE.serial)}`);
    const apps = data.top || [];
    if (apps.length === 0) {
      $("#notif-list").innerHTML = `<p class="muted">Không có notification gần đây (hoặc parser không nhận output).</p>`;
      return;
    }
    $("#notif-list").innerHTML = `
      <p class="muted tiny" style="margin-top:8px">${data.unique_apps} app khác nhau có gửi notification</p>
      <div class="table-wrap" style="max-height:360px;margin-top:8px">
        <table>
          <thead><tr><th>#</th><th>Package</th><th>Notification posts</th></tr></thead>
          <tbody>
            ${apps.map((a, i) => `
              <tr>
                <td>${i + 1}</td>
                <td><code>${a.package}</code></td>
                <td><b>${a.count}</b></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
    logEntry(`🔔 Đã load ${apps.length} app gửi notif`, "success");
  } catch (e) {
    toast("Lỗi: " + e.message, "error");
    logEntry(`🔔 Notification load lỗi: ${e.message}`, "error");
  } finally {
    hideLoading();
  }
}

$("#btn-load-storage")?.addEventListener("click", loadStorageInsights);
$("#btn-load-battery")?.addEventListener("click", loadBatteryInsights);
$("#btn-reset-battery")?.addEventListener("click", resetBatteryStats);
$("#btn-load-notif")?.addEventListener("click", loadNotificationInsights);

// ---------- APN ----------

let APN_DATA = null;

async function loadApnData() {
  if (!APN_DATA) {
    try {
      APN_DATA = await api("/api/apn-list");
    } catch (e) {
      $("#apn-config").innerHTML = `<p style="color:var(--danger)">Lỗi tải APN data: ${e.message}</p>`;
      return;
    }
  }
  renderApnTabs();
  renderApnSteps();
  // Hiển thị config nhà mạng đầu tiên mặc định
  if (APN_DATA.carriers.length > 0) {
    showApnCarrier(APN_DATA.carriers[0].id);
  }
}

function renderApnTabs() {
  const html = APN_DATA.carriers.map(c => `
    <button class="btn-secondary btn-sm apn-tab" data-carrier="${c.id}">${c.icon} ${c.name}</button>
  `).join("");
  $("#apn-carrier-tabs").innerHTML = html;
  $$(".apn-tab").forEach(b => {
    b.addEventListener("click", () => showApnCarrier(b.dataset.carrier));
  });
}

function showApnCarrier(carrierId) {
  const carrier = APN_DATA.carriers.find(c => c.id === carrierId);
  if (!carrier) return;
  // Highlight selected tab
  $$(".apn-tab").forEach(b => {
    b.classList.toggle("btn-primary", b.dataset.carrier === carrierId);
    b.classList.toggle("btn-secondary", b.dataset.carrier !== carrierId);
  });
  // Render config table
  const rows = Object.entries(carrier.settings).map(([k, v]) => `
    <tr>
      <td class="apn-label">${k}</td>
      <td><code class="apn-value" data-copy="${v}">${v}</code></td>
    </tr>
  `).join("");
  $("#apn-config").innerHTML = `
    <p class="muted" style="margin-top:14px"><b>${carrier.icon} ${carrier.name}</b> — ${carrier.note}</p>
    <div class="table-wrap" style="margin-top:8px">
      <table class="apn-table">
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p class="muted tiny" style="margin-top:6px">Bấm vào giá trị để copy.</p>
  `;
  // Copy on click
  $$(".apn-value").forEach(c => {
    c.addEventListener("click", () => {
      const text = c.dataset.copy;
      navigator.clipboard.writeText(text).then(() => {
        toast(`Đã copy: ${text}`, "success");
      }).catch(() => {
        toast("Trình duyệt chặn clipboard. Copy tay nhé.", "warn");
      });
    });
  });
}

function renderApnSteps() {
  if (!APN_DATA.instructions) return;
  const steps = APN_DATA.instructions.steps.map(s => `<li>${s}</li>`).join("");
  $("#apn-steps").innerHTML = steps;
  const tips = APN_DATA.instructions.tips.map(t => `<li>${t}</li>`).join("");
  $("#apn-tips").innerHTML = `<p class="muted" style="margin-top:12px;font-size:12px"><b>Lưu ý:</b></p><ul class="tip-list" style="font-size:12px">${tips}</ul>`;
}

$("#btn-open-apn")?.addEventListener("click", async () => {
  if (!STATE.serial) {
    toast("Chưa kết nối máy — bấm ↻ ở góc trên phải", "warn");
    return;
  }
  try {
    const data = await api(`/api/apn-open-settings?serial=${encodeURIComponent(STATE.serial)}`, { method: "POST" });
    $("#apn-open-status").textContent = "✓ " + (data.message || "Đã mở APN settings trên máy");
    $("#apn-open-status").style.color = "var(--success)";
    toast("Đã mở APN Settings trên máy Sony", "success");
    logEntry("📡 Mở APN settings trên máy", "success");
  } catch (e) {
    $("#apn-open-status").textContent = "✗ " + e.message;
    $("#apn-open-status").style.color = "var(--danger)";
    toast("Lỗi: " + e.message, "error");
  }
});

// ---------- BOOTLOADER ----------

async function checkBootloader() {
  if (!STATE.serial) {
    $("#bootloader-result").innerHTML = `<p class="muted" style="margin-top:12px">Chưa kết nối máy — bấm ↻ ở góc trên phải.</p>`;
    return;
  }
  $("#bootloader-result").innerHTML = `<p class="muted" style="margin-top:12px">Đang kiểm tra…</p>`;
  try {
    const d = await api(`/api/bootloader-status?serial=${encodeURIComponent(STATE.serial)}`);
    STATE.bootloaderChecked = true;
    logEntry(`🔓 Bootloader check: ${d.locked ? "locked" : "unlocked"} (${d.verified_boot_state})`, "info");

    const eligLabels = {
      no_jp_market: { text: "❌ Không thể unlock", color: "var(--danger)", note: "Máy nội địa Nhật — Sony chính sách không cấp mã unlock cho thị trường này." },
      already_unlocked: { text: "✓ Đã unlock", color: "var(--success)", note: "Bootloader đã ở trạng thái unlocked." },
      not_sony: { text: "⚠ Không phải Sony", color: "var(--warn)", note: "Manufacturer không phải Sony — tool này thiết kế cho Sony Xperia." },
      check_sony_site: { text: "🔍 Cần check Sony site", color: "var(--primary)", note: "Có thể đủ điều kiện. Lấy IMEI (bấm *#06# trên máy) và check ở Sony Developer site." },
    };
    const elig = eligLabels[d.eligibility] || { text: d.eligibility, color: "var(--text-3)", note: "" };

    const vbsColors = { green: "var(--success)", yellow: "var(--warn)", orange: "var(--warn)", red: "var(--danger)" };
    const vbsColor = vbsColors[d.verified_boot_state] || "var(--text-3)";

    $("#bootloader-result").innerHTML = `
      <div class="device-info" style="margin-top:14px">
        <table>
          <tr><td>Model</td><td><b>${d.model || "—"}</b></td></tr>
          <tr><td>Device code</td><td><code>${d.device || "—"}</code></td></tr>
          <tr><td>Manufacturer</td><td>${d.manufacturer || "—"}</td></tr>
          <tr><td>Build type</td><td><code>${d.build_type || "—"}</code></td></tr>
          <tr><td>Bootloader</td><td><b style="color:${d.locked ? "var(--danger)" : "var(--success)"}">${d.locked ? "🔒 LOCKED" : "🔓 UNLOCKED"}</b> <code class="muted">(${d.locked_raw})</code></td></tr>
          <tr><td>Verified Boot State</td><td><b style="color:${vbsColor}">${d.verified_boot_state.toUpperCase()}</b></td></tr>
          <tr><td>OEM unlock allowed</td><td>${d.oem_unlock_disallowed === "0" ? "✓ Cho phép" : d.oem_unlock_disallowed === "1" ? "✗ Bị cấm (carrier-locked)" : "—"}</td></tr>
          <tr><td>JP market?</td><td>${d.is_jp_market ? "🇯🇵 Có" : "🌐 Không"}</td></tr>
        </table>
      </div>
      <div class="warn" style="margin-top:14px;border-color:${elig.color};color:var(--text-2)">
        <b style="color:${elig.color}">${elig.text}</b><br>
        ${elig.note}
      </div>
      ${d.eligibility === "check_sony_site" ? `
        <p class="muted" style="margin-top:12px;font-size:12px">
          → Bấm <code>${d.imei_dial_code}</code> trên máy lấy IMEI, sau đó vào
          <a href="${d.sony_unlock_url}" target="_blank">Sony Developer Site</a> để check.
        </p>
      ` : ""}
    `;
  } catch (e) {
    $("#bootloader-result").innerHTML = `<p style="color:var(--danger);margin-top:12px">Lỗi: ${e.message}</p>`;
    logEntry(`🔓 Bootloader check lỗi: ${e.message}`, "error");
  }
}

$("#btn-check-bootloader")?.addEventListener("click", checkBootloader);

// ---------- ROM ----------

async function detectRomDevice() {
  if (!STATE.serial) {
    $("#rom-device-result").innerHTML = `<p class="muted">Chưa kết nối máy — bấm ↻ ở góc trên phải.</p>`;
    return;
  }
  $("#rom-device-result").innerHTML = `<p class="muted">Đang đọc model + customization (mất 5-10s lần đầu, tool sẽ tải database mapping)…</p>`;
  logEntry("📱 ROM: detecting model + customization", "action");

  try {
    const d = await api(`/api/rom/device?serial=${encodeURIComponent(STATE.serial)}`);
    STATE.romDetected = true;
    STATE.romDeviceInfo = d;

    if (!d.supported) {
      $("#rom-device-result").innerHTML = `
        <table>
          <tr><td>Model</td><td><b>${d.model_name || "—"}</b></td></tr>
          <tr><td>Build hiện tại</td><td><code>${d.current_build || "—"}</code></td></tr>
          <tr><td>Customization code</td><td><code>${d.device_cust_number || "—"}</code></td></tr>
          <tr><td>SPC</td><td><code>${d.device_spcode || "—"}</code></td></tr>
        </table>
        <div class="warn" style="margin-top:14px">⚠️ ${d.message || "Model chưa support."}</div>
      `;
      logEntry(`📱 ROM: model ${d.model_name} chưa có trong database`, "warn");
      return;
    }

    const m = d.model;
    const custList = m.customizations.map(c => {
      const isAuto = c.id === d.auto_cust_id;
      return `<li>${isAuto ? "✓ " : ""}<b>${c.name}</b> — SPC <code>${c.spc || "—"}</code>${isAuto ? " <span class='muted'>(khớp máy của bạn)</span>" : ""}</li>`;
    }).join("");

    $("#rom-device-result").innerHTML = `
      <table>
        <tr><td>Model</td><td><b>${m.name}</b></td></tr>
        <tr><td>Product code</td><td><code>${m.product_name}</code></td></tr>
        <tr><td>Group</td><td>${m.group_name}</td></tr>
        <tr><td>Build hiện tại</td><td><code>${d.current_build || "—"}</code></td></tr>
        <tr><td>Customization của máy</td><td><code>${d.device_cust_number || "—"}</code> (SPC <code>${d.device_spcode || "—"}</code>)</td></tr>
      </table>
      <p class="muted" style="margin-top:12px"><b>${m.customizations.length}</b> customization variant tồn tại cho model này:</p>
      <ul style="padding-left:20px;font-size:13px">${custList}</ul>
    `;
    $("#rom-firmware-card").hidden = false;
    logEntry(`📱 ROM: detected ${m.name} (${m.customizations.length} cust variants)`, "success");
  } catch (e) {
    $("#rom-device-result").innerHTML = `<p style="color:var(--danger)">Lỗi: ${e.message}</p>`;
    logEntry(`📱 ROM detect lỗi: ${e.message}`, "error");
  }
}

async function loadRomFirmwareList() {
  if (!STATE.romDeviceInfo?.supported) {
    toast("Phát hiện máy trước", "warn");
    return;
  }
  const model = STATE.romDeviceInfo.model;
  const cust = STATE.romDeviceInfo.auto_cust_id || (model.customizations[0]?.id);

  showLoading("Đang query Sony API để lấy danh sách ROM…");
  logEntry(`📱 ROM: querying Sony GCS for ${model.name}`, "action");

  try {
    const data = await api(`/api/rom/firmware-list?model_name=${encodeURIComponent(model.name)}${cust ? "&cust_id=" + encodeURIComponent(cust) : ""}`);

    const html = data.results.map(r => {
      if (!r.ok) {
        return `<div class="preset-warning" style="margin-top:8px">❌ ${r.cust_name}: ${r.device_problem}</div>`;
      }
      // Group entries by version, show KEEP / WIPE per version
      const byVer = new Map();
      for (const e of r.entries) {
        if (!byVer.has(e.version)) byVer.set(e.version, []);
        byVer.get(e.version).push(e);
      }
      const rows = [...byVer.entries()].map(([ver, entries]) => `
        <tr>
          <td><b>${ver}</b>${entries[0].revision ? ` <span class="muted">-${entries[0].revision}</span>` : ""}</td>
          <td>${entries[0].release_state}</td>
          <td>${entries[0].android_update_type === "NA" ? "—" : entries[0].android_update_type}</td>
          <td>
            ${entries.map(e => `
              <button class="btn-sm btn-secondary"
                      data-rom-action="download"
                      data-url="${e.download_url.replace(/"/g, "&quot;")}"
                      data-version="${ver}"
                      data-mode="${e.is_factory_reset ? 'wipe' : 'keep'}"
                      title="${e.is_factory_reset ? 'Cài lại sạch (factory reset)' : 'Giữ data hiện có'}">
                ${e.is_factory_reset ? '🧹 Wipe' : '💾 Keep'}
              </button>
            `).join(" ")}
          </td>
        </tr>
      `).join("");
      return `
        <div style="margin-top:14px">
          <h4 style="margin:0 0 6px 0">📦 ${r.cust_name} <span class="muted">(${byVer.size} version)</span></h4>
          <div class="table-wrap"><table>
            <thead><tr><th>Version</th><th>State</th><th>Android update</th><th>Mode flash</th></tr></thead>
            <tbody>${rows}</tbody>
          </table></div>
        </div>
      `;
    }).join("");

    $("#rom-firmware-list").innerHTML = html || `<p class="muted">Không có firmware cho máy này.</p>`;

    // Wire up download buttons
    $$("#rom-firmware-list button[data-rom-action='download']").forEach(btn => {
      btn.addEventListener("click", () => startRomDownload({
        url: btn.dataset.url,
        version: btn.dataset.version,
        mode: btn.dataset.mode,
      }));
    });

    logEntry(`📱 ROM: ${data.results.reduce((s, r) => s + r.entries.length, 0)} firmware entries`, "success");
  } catch (e) {
    $("#rom-firmware-list").innerHTML = `<p style="color:var(--danger)">Lỗi: ${e.message}</p>`;
    logEntry(`📱 ROM list lỗi: ${e.message}`, "error");
  } finally {
    hideLoading();
  }
}

// ROM download — SSE progress streaming

let _romDownloadState = { jobId: null, eventSource: null };

function _humanBytes(n) {
  if (!n || n < 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0, v = n;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`;
}

function _humanDuration(seconds) {
  if (!seconds || seconds < 0 || !isFinite(seconds)) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60), rs = s % 60;
  if (m < 60) return `${m}m ${rs}s`;
  const h = Math.floor(m / 60), rm = m % 60;
  return `${h}h ${rm}m`;
}

function _updateRomDownloadUI(p) {
  const wrap = $("#rom-dl-modal-body");
  if (!wrap) return;
  if (p.state === "list_files") {
    wrap.innerHTML = `<p class="muted">Đang lấy danh sách file từ Sony…</p>`;
    return;
  }
  if (p.state === "error") {
    wrap.innerHTML = `<p style="color:var(--danger)"><b>❌ Lỗi:</b> ${p.error || "Không rõ"}</p>`;
    return;
  }
  if (p.state === "cancelled") {
    wrap.innerHTML = `<p class="muted">⏹️ Đã huỷ download.</p>`;
    return;
  }
  if (p.state === "done") {
    wrap.innerHTML = `
      <p style="color:var(--success);font-size:16px"><b>✅ Tải xong!</b></p>
      <p>ROM đã lưu vào:</p>
      <p><code style="font-size:11px;word-break:break-all">${p.output_dir || "—"}</code></p>
      <p class="muted">Bấm <b>Sang Flash</b> để vào wizard cài ROM (Day 3-4 sẽ làm phần đẹp).</p>
    `;
    $("#btn-rom-dl-cancel").hidden = true;
    $("#btn-rom-dl-flash").hidden = false;
    $("#btn-rom-dl-close").textContent = "Đóng";
    return;
  }
  // downloading
  const pct = p.percent || 0;
  const speed = p.speed_bps ? _humanBytes(p.speed_bps) + "/s" : "—";
  wrap.innerHTML = `
    <div style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;font-size:13px">
        <span>${p.current_file || "…"}</span>
        <span><b>${pct.toFixed(1)}%</b></span>
      </div>
      <div class="progress-bar" style="margin-top:6px"><div class="progress-fill" style="width:${pct}%"></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:13px">
      <div><span class="muted">File:</span> ${p.files_done}/${p.files_total}</div>
      <div><span class="muted">Tốc độ:</span> ${speed}</div>
      <div><span class="muted">Đã tải:</span> ${_humanBytes(p.bytes_done)} / ${_humanBytes(p.bytes_total)}</div>
      <div><span class="muted">ETA:</span> ${_humanDuration(p.eta_seconds)}</div>
    </div>
  `;
}

async function startRomDownload({ url, version, mode }) {
  if (!url) {
    toast("Không có URL download", "error");
    return;
  }
  const label = `${STATE.romDeviceInfo?.model?.name || "ROM"}_${version}_${mode}`;
  logEntry(`📥 Bắt đầu download ROM ${version} (${mode})`, "action");

  // Open modal
  $("#rom-dl-modal").hidden = false;
  $("#rom-dl-modal-title").textContent = `Đang tải ROM ${version}`;
  $("#btn-rom-dl-cancel").hidden = false;
  $("#btn-rom-dl-flash").hidden = true;
  $("#btn-rom-dl-close").textContent = "Đóng (chạy nền)";
  _updateRomDownloadUI({ state: "list_files" });

  // Start job
  let job;
  try {
    job = await api("/api/rom/download/start", {
      method: "POST",
      body: JSON.stringify({ firmware_url: url, label }),
    });
  } catch (e) {
    _updateRomDownloadUI({ state: "error", error: e.message });
    return;
  }
  _romDownloadState.jobId = job.job_id;

  // Subscribe SSE
  const es = new EventSource(`/api/rom/download/stream?job_id=${encodeURIComponent(job.job_id)}`);
  _romDownloadState.eventSource = es;
  es.onmessage = (ev) => {
    try {
      const p = JSON.parse(ev.data);
      _updateRomDownloadUI(p);
      if (["done", "error", "cancelled"].includes(p.state)) {
        es.close();
        _romDownloadState.eventSource = null;
        if (p.state === "done") logEntry(`✅ ROM download xong: ${p.output_dir}`, "success");
        else if (p.state === "error") logEntry(`❌ ROM download lỗi: ${p.error}`, "error");
        else logEntry(`⏹️ ROM download huỷ`, "warn");
      }
    } catch (e) {
      console.warn("SSE parse:", e);
    }
  };
  es.onerror = (e) => {
    console.warn("SSE error", e);
    // EventSource auto-reconnect; chỉ log nếu thread đã chết
  };
}

async function cancelRomDownload() {
  if (!_romDownloadState.jobId) return;
  try {
    await api(`/api/rom/download/cancel/${_romDownloadState.jobId}`, { method: "POST" });
    toast("Đã yêu cầu huỷ — đợi vài giây", "warn");
  } catch (e) {
    toast("Lỗi huỷ: " + e.message, "error");
  }
}

function closeRomDownloadModal() {
  $("#rom-dl-modal").hidden = true;
  // Không close EventSource — cho download tiếp tục background
}

async function refreshRomCache() {
  openModal({
    title: "Refresh database mapping?",
    body: `<p>Tool sẽ tải lại file metadata từ server XperiFirm community. Cần khi Sony release model mới hoặc Sony đổi format.</p><p class="muted">~50KB, mất 2-5 giây.</p>`,
    confirmText: "⟲ Refresh",
    confirmClass: "btn-primary",
    onConfirm: async () => {
      showLoading("Đang tải resources mới…");
      try {
        const d = await api("/api/rom/refresh-resources", { method: "POST" });
        toast(`✓ Refresh OK — ${d.model_count} model trong database`, "success");
        logEntry(`📱 ROM resources refresh: ${d.model_count} models, ${d.xml_size} bytes`, "success");
        STATE.romDetected = false;  // force re-detect
        if (STATE.serial) detectRomDevice();
      } catch (e) {
        toast("Lỗi: " + e.message, "error");
        logEntry(`📱 ROM refresh lỗi: ${e.message}`, "error");
      } finally {
        hideLoading();
      }
    },
  });
}

$("#btn-rom-detect")?.addEventListener("click", () => {
  STATE.romDetected = false;
  detectRomDevice();
});
$("#btn-rom-load-firmware")?.addEventListener("click", loadRomFirmwareList);
$("#btn-rom-refresh-cache")?.addEventListener("click", refreshRomCache);
$("#btn-rom-dl-cancel")?.addEventListener("click", cancelRomDownload);
$("#btn-rom-dl-close")?.addEventListener("click", closeRomDownloadModal);
$("#btn-rom-dl-flash")?.addEventListener("click", () => {
  toast("Day 3-4 chưa làm — wizard flash sẽ implement sau", "warn");
});

// ---------- init ----------

(async function init() {
  await refreshStatus();
  loadPresets();
  await loadBloatData();
  refreshCleanupPreview();
  if (STATE.serial) {
    await loadPackages();
  }
})();
