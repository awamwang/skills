(() => {
  "use strict";

  /** @type {any} */
  let data = null;
  /** skill -> platform -> original plan value */
  const original = new Map();
  /** skill -> platform -> current plan value (dirty tracking) */
  const current = new Map();

  const $ = (id) => document.getElementById(id);
  const logEl = $("log");
  const busyEl = $("busy");

  function log(msg) {
    const ts = new Date().toLocaleTimeString();
    logEl.textContent += `[${ts}] ${msg}\n`;
    logEl.scrollTop = logEl.scrollHeight;
  }

  function setBusy(on) {
    busyEl.classList.toggle("hidden", !on);
    document.querySelectorAll("button").forEach((b) => {
      if (b.id === "btnClearLog") return;
      b.disabled = on || (b.id === "btnSavePlan" && !hasDirty());
    });
  }

  function planKey(skill, platform) {
    return `${skill}\0${platform}`;
  }

  function getPlan(skill, platform) {
    return current.get(planKey(skill, platform));
  }

  function setPlanLocal(skill, platform, value) {
    current.set(planKey(skill, platform), value);
  }

  function hasDirty() {
    for (const [k, v] of current) {
      if (original.get(k) !== v) return true;
    }
    return false;
  }

  function collectDirtyChanges() {
    /** @type {{skill:string, plan: Record<string,string>}[]} */
    const bySkill = new Map();
    for (const [k, v] of current) {
      if (original.get(k) === v) continue;
      const [skill, platform] = k.split("\0");
      if (!bySkill.has(skill)) bySkill.set(skill, {});
      bySkill.get(skill)[platform] = v;
    }
    return [...bySkill.entries()].map(([skill, plan]) => ({ skill, plan }));
  }

  function updateDirtyUI() {
    const dirty = hasDirty();
    $("btnSavePlan").disabled = !dirty || !busyEl.classList.contains("hidden");
    $("dirtyHint").classList.toggle("hidden", !dirty);
    document.querySelectorAll("select.plan-sel").forEach((sel) => {
      const skill = sel.dataset.skill;
      const platform = sel.dataset.platform;
      const isDirty = original.get(planKey(skill, platform)) !== sel.value;
      sel.classList.toggle("dirty", isDirty);
      sel.className = `plan-sel ${sel.value}${isDirty ? " dirty" : ""}`;
    });
  }

  function selectedSkills() {
    return [...document.querySelectorAll("tbody input.row-sel:checked")]
      .map((el) => el.value);
  }

  function updateSelCount() {
    $("selCount").textContent = `已选 ${selectedSkills().length}`;
  }

  function statusBadge(status) {
    const label = (data.status_labels && data.status_labels[status]) || status || "—";
    const short = {
      done: "✅",
      not_started: "○",
      todo: "◐",
      blocked: "⚠",
      skip: "—",
    }[status] || "·";
    return `<span class="badge ${status || ""}" title="${escapeHtml(label)}">${short}</span>`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderReleasePlatforms() {
    const box = $("releasePlatforms");
    box.innerHTML = "";
    for (const pid of data.release_platforms || []) {
      const meta = (data.platforms || []).find((p) => p.id === pid);
      const label = document.createElement("label");
      label.className = "chk";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = pid;
      cb.className = "rel-plat";
      // 默认勾选：非 doubao 的 releasable（doubao 需人工导入，默认不勾）
      cb.checked = pid !== "doubao";
      label.appendChild(cb);
      label.appendChild(
        document.createTextNode(" " + (meta ? meta.name : pid))
      );
      box.appendChild(label);
    }
  }

  function renderTierFilter() {
    const sel = $("tierFilter");
    const keep = sel.value;
    sel.innerHTML = '<option value="">全部</option>';
    const tiers = data.tiers || {};
    for (const tid of Object.keys(tiers)) {
      const opt = document.createElement("option");
      opt.value = tid;
      opt.textContent = `${tid} · ${tiers[tid].label || tid}`;
      sel.appendChild(opt);
    }
    sel.value = keep;
  }

  function renderTable() {
    const platforms = data.platforms || [];
    const thead = $("thead");
    const tbody = $("tbody");

    thead.innerHTML = `
      <tr>
        <th></th>
        <th>技能</th>
        <th>tier</th>
        <th>version</th>
        <th>repo</th>
        ${platforms.map((p) => `<th title="${escapeHtml(p.name)}">${escapeHtml(p.id)}<br/><span class="muted">plan / status</span></th>`).join("")}
        <th>简介</th>
      </tr>`;

    original.clear();
    current.clear();
    tbody.innerHTML = "";

    for (const sk of data.skills || []) {
      for (const p of platforms) {
        const v = (sk.plan && sk.plan[p.id]) || "skip";
        original.set(planKey(sk.key, p.id), v);
        current.set(planKey(sk.key, p.id), v);
      }

      const tr = document.createElement("tr");
      tr.dataset.key = sk.key;
      tr.dataset.tier = sk.tier || "";
      tr.dataset.search = [
        sk.key, sk.repo, sk.summary, sk.name, sk.notes,
      ].join(" ").toLowerCase();

      const planCells = platforms.map((p) => {
        const val = getPlan(sk.key, p.id);
        const st = (sk.status && sk.status[p.id]) || "";
        const opts = ["publish", "optional", "skip"]
          .map((o) =>
            `<option value="${o}" ${o === val ? "selected" : ""}>${o}</option>`
          )
          .join("");
        return `<td>
          <select class="plan-sel ${val}" data-skill="${escapeHtml(sk.key)}" data-platform="${p.id}">${opts}</select>
          ${statusBadge(st)}
        </td>`;
      }).join("");

      const ver = sk.version
        ? escapeHtml(sk.version)
        : `<span class="muted" title="${escapeHtml(sk.version_reason || "无版本")}">—</span>`;

      tr.innerHTML = `
        <td><input type="checkbox" class="row-sel" value="${escapeHtml(sk.key)}" /></td>
        <td class="key">${escapeHtml(sk.key)}</td>
        <td>${escapeHtml(sk.tier || "—")}</td>
        <td class="ver">${ver}</td>
        <td>${escapeHtml(sk.repo || "—")}</td>
        ${planCells}
        <td class="summary">${escapeHtml(sk.summary || "")}</td>`;
      tbody.appendChild(tr);
    }

    tbody.querySelectorAll("select.plan-sel").forEach((sel) => {
      sel.addEventListener("change", () => {
        setPlanLocal(sel.dataset.skill, sel.dataset.platform, sel.value);
        updateDirtyUI();
      });
    });
    tbody.querySelectorAll("input.row-sel").forEach((cb) => {
      cb.addEventListener("change", () => {
        cb.closest("tr").classList.toggle("selected", cb.checked);
        syncSelectAll();
        updateSelCount();
      });
    });

    applyFilter();
    updateDirtyUI();
    updateSelCount();
  }

  function syncSelectAll() {
    const rows = [...document.querySelectorAll("tbody tr:not(.hidden-row) input.row-sel")];
    const all = rows.length > 0 && rows.every((r) => r.checked);
    $("selectAll").checked = all;
  }

  function applyFilter() {
    const q = ($("filter").value || "").trim().toLowerCase();
    const tier = $("tierFilter").value;
    document.querySelectorAll("#tbody tr").forEach((tr) => {
      const okQ = !q || (tr.dataset.search || "").includes(q);
      const okT = !tier || tr.dataset.tier === tier;
      tr.classList.toggle("hidden-row", !(okQ && okT));
    });
    syncSelectAll();
  }

  async function api(path, body) {
    const opts = body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : { method: "GET" };
    const res = await fetch(path, opts);
    let json;
    try {
      json = await res.json();
    } catch {
      throw new Error(`HTTP ${res.status}：响应非 JSON`);
    }
    if (!res.ok && json && json.error) {
      throw new Error(json.error);
    }
    return json;
  }

  async function reload() {
    data = await api("/api/skills");
    $("meta").textContent =
      `${(data.skills || []).length} 个技能 · 规划更新 ${data.updated || "—"}`;
    renderTierFilter();
    renderReleasePlatforms();
    renderTable();
  }

  async function savePlan() {
    const changes = collectDirtyChanges();
    if (!changes.length) {
      log("无规划改动");
      return;
    }
    if (!confirm(`保存 ${changes.length} 个技能的规划改动？\n（不会触发发布）`)) return;
    setBusy(true);
    try {
      log(`保存规划：${changes.length} 项…`);
      const r = await api("/api/plan", { changes });
      log(JSON.stringify(r, null, 2));
      if (r.view_log) log(r.view_log);
      await reload();
      log(r.ok ? "规划已保存" : "规划保存有失败项");
    } catch (e) {
      log(`保存失败：${e.message || e}`);
    } finally {
      setBusy(false);
      updateDirtyUI();
    }
  }

  async function doUpgrade() {
    const skills = selectedSkills();
    if (!skills.length) {
      alert("请先勾选技能");
      return;
    }
    const part = $("bumpPart").value;
    if (!confirm(`对 ${skills.length} 个技能执行升级（--part ${part}）？\n不自动 commit / 发布。`)) return;
    setBusy(true);
    try {
      log(`升级 ${skills.join(", ")} part=${part}`);
      const r = await api("/api/upgrade", { skills, part });
      for (const item of r.results || []) {
        log(`--- ${item.skill} exit=${item.exit} ---`);
        if (item.log) log(item.log);
      }
      await reload();
    } catch (e) {
      log(`升级失败：${e.message || e}`);
    } finally {
      setBusy(false);
      updateDirtyUI();
    }
  }

  async function doUnmanage() {
    const skills = selectedSkills();
    if (!skills.length) {
      alert("请先勾选技能");
      return;
    }
    if (!confirm(
      `将 ${skills.length} 个技能移出管理？\n${skills.join(", ")}\n\n不删本机目录 / 不改技能仓 git。`
    )) return;
    setBusy(true);
    try {
      log(`移出管理：${skills.join(", ")}`);
      const r = await api("/api/unmanage", { skills });
      for (const item of r.results || []) {
        log(`--- exit=${item.exit} ---`);
        if (item.log) log(item.log);
      }
      await reload();
    } catch (e) {
      log(`移出失败：${e.message || e}`);
    } finally {
      setBusy(false);
      updateDirtyUI();
    }
  }

  async function doRelease() {
    const skills = selectedSkills();
    if (!skills.length) {
      alert("请先勾选技能");
      return;
    }
    if (hasDirty()) {
      const go = confirm(
        "表格里有未保存的规划改动。\n发布使用的是已保存规划 / 本次勾选平台，不会带上未保存改动。\n\n继续发布？"
      );
      if (!go) return;
    }
    const platforms = [...document.querySelectorAll("input.rel-plat:checked")]
      .map((el) => el.value);
    if (!platforms.length) {
      alert("请至少勾选一个发布平台");
      return;
    }
    if (!confirm(
      `对 ${skills.length} 个技能串行发布到：${platforms.join(", ")}？\n需本机 path、凭据就绪；不替你 commit。`
    )) return;

    setBusy(true);
    try {
      log(`批量发布 skills=${skills.join(",")} platforms=${platforms.join(",")}`);
      const r = await api("/api/release", { skills, platforms });
      for (const item of r.results || []) {
        log(`--- ${item.skill} exit=${item.exit} ---`);
        if (item.cmd) log(item.cmd);
        if (item.log) log(item.log);
      }
      log(r.ok ? "批量发布全部成功" : "批量发布有失败");
      await reload();
    } catch (e) {
      log(`发布失败：${e.message || e}`);
    } finally {
      setBusy(false);
      updateDirtyUI();
    }
  }

  $("selectAll").addEventListener("change", () => {
    const on = $("selectAll").checked;
    document.querySelectorAll("tbody tr:not(.hidden-row) input.row-sel").forEach((cb) => {
      cb.checked = on;
      cb.closest("tr").classList.toggle("selected", on);
    });
    updateSelCount();
  });
  $("filter").addEventListener("input", applyFilter);
  $("tierFilter").addEventListener("change", applyFilter);
  $("btnSavePlan").addEventListener("click", savePlan);
  $("btnUpgrade").addEventListener("click", doUpgrade);
  $("btnUnmanage").addEventListener("click", doUnmanage);
  $("btnRelease").addEventListener("click", doRelease);
  $("btnClearLog").addEventListener("click", () => { logEl.textContent = ""; });

  reload().catch((e) => {
    log(`加载失败：${e.message || e}`);
  });
})();
