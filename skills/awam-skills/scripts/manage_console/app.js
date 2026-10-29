(() => {
  "use strict";

  /** @type {any} */
  let data = null;
  /** skill -> platform -> 原始 plan 值 */
  const original = new Map();
  /** skill -> platform -> 当前 plan 值（脏值跟踪） */
  const current = new Map();

  const $ = (id) => document.getElementById(id);
  const logEl = $("log");
  const busyEl = $("busy");
  const progressEl = $("progress");
  const tbody = $("tbody");
  const emptyState = $("emptyState");
  const emptyText = emptyState.querySelector("span");

  const PLAN_ORDER = ["publish", "optional", "skip"];
  const STATUS_RING = {
    done: "is-done",
    todo: "is-todo",
    blocked: "is-blocked",
  };

  /* ---------------- 主题 ---------------- */

  const THEME_KEY = "awam-console-theme";

  function applyTheme(mode) {
    document.documentElement.dataset.theme = mode;
    $("btnTheme").setAttribute("aria-pressed", String(mode === "dark"));
  }

  function initTheme() {
    let saved = null;
    try {
      saved = localStorage.getItem(THEME_KEY);
    } catch { /* 隐私模式下忽略 */ }
    if (saved !== "light" && saved !== "dark") {
      saved = window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    }
    applyTheme(saved);
  }

  /* ---------------- 基础工具 ---------------- */

  function log(msg) {
    const ts = new Date().toLocaleTimeString();
    logEl.textContent += `[${ts}] ${msg}\n`;
    logEl.scrollTop = logEl.scrollHeight;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setBusy(on, text) {
    busyEl.classList.toggle("hidden", !on);
    progressEl.classList.toggle("hidden", !on);
    if (on && text) $("busyText").textContent = text;
    document.querySelectorAll("button, select, input").forEach((el) => {
      if (el.id === "btnClearLog") return;
      el.disabled = on || (el.id === "btnSavePlan" && !hasDirty());
    });
  }

  let snackTimer = null;
  function snack(msg) {
    $("snackbarText").textContent = msg;
    const bar = $("snackbar");
    bar.classList.add("is-visible");
    clearTimeout(snackTimer);
    snackTimer = setTimeout(() => bar.classList.remove("is-visible"), 4000);
  }

  /** MD3 基本对话框；返回 Promise<boolean>，替代 window.confirm */
  function confirmDialog(title, body, okLabel) {
    return new Promise((resolve) => {
      const scrim = $("dialog");
      const okBtn = $("dialogOk");
      const cancelBtn = $("dialogCancel");
      const prevFocus = document.activeElement;

      $("dialogTitle").textContent = title;
      $("dialogBody").textContent = body;
      okBtn.textContent = okLabel || "确定";
      scrim.classList.remove("hidden");

      const close = (result) => {
        scrim.classList.add("hidden");
        okBtn.removeEventListener("click", onOk);
        cancelBtn.removeEventListener("click", onCancel);
        scrim.removeEventListener("click", onScrim);
        document.removeEventListener("keydown", onKey, true);
        if (prevFocus instanceof HTMLElement) prevFocus.focus();
        resolve(result);
      };
      const onOk = () => close(true);
      const onCancel = () => close(false);
      const onScrim = (e) => { if (e.target === scrim) close(false); };
      const onKey = (e) => {
        if (e.key === "Escape") { e.preventDefault(); close(false); }
        if (e.key === "Tab") {
          const items = [cancelBtn, okBtn];
          const i = items.indexOf(document.activeElement);
          e.preventDefault();
          items[(i + (e.shiftKey ? items.length - 1 : 1)) % items.length].focus();
        }
      };

      okBtn.addEventListener("click", onOk);
      cancelBtn.addEventListener("click", onCancel);
      scrim.addEventListener("click", onScrim);
      document.addEventListener("keydown", onKey, true);
      okBtn.focus();
    });
  }

  /* ---------------- plan 脏值 ---------------- */

  const planKey = (skill, platform) => `${skill}\0${platform}`;

  function hasDirty() {
    for (const [k, v] of current) {
      if (original.get(k) !== v) return true;
    }
    return false;
  }

  function dirtyCount() {
    let n = 0;
    for (const [k, v] of current) {
      if (original.get(k) !== v) n += 1;
    }
    return n;
  }

  function collectDirtyChanges() {
    /** @type {Map<string, Record<string,string>>} */
    const bySkill = new Map();
    for (const [k, v] of current) {
      if (original.get(k) === v) continue;
      const [skill, platform] = k.split("\0");
      if (!bySkill.has(skill)) bySkill.set(skill, {});
      bySkill.get(skill)[platform] = v;
    }
    return [...bySkill.entries()].map(([skill, plan]) => ({ skill, plan }));
  }

  /* ---------------- 渲染 ---------------- */

  function planOptions() {
    const labels = (data && data.plan_labels) || {};
    const keys = Object.keys(labels);
    return keys.length ? keys : PLAN_ORDER;
  }

  function renderReleasePlatforms() {
    const box = $("releasePlatforms");
    box.innerHTML = "";
    for (const pid of data.release_platforms || []) {
      const meta = (data.platforms || []).find((p) => p.id === pid);
      const label = document.createElement("label");
      label.className = "chip chip--filter";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = pid;
      cb.className = "rel-plat sr-only";
      // doubao 需人工导入，默认不勾
      cb.checked = pid !== "doubao";
      cb.addEventListener("change", () => {
        label.classList.toggle("is-selected", cb.checked);
      });
      label.appendChild(cb);
      label.appendChild(
        document.createTextNode(" " + (meta ? meta.name : pid))
      );
      if (cb.checked) label.classList.add("is-selected");
      box.appendChild(label);
    }
  }

  function renderTierFilter() {
    const sel = $("tierFilter");
    const keep = sel.value;
    sel.innerHTML = '<option value="">全部 tier</option>';
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

    thead.innerHTML =
      "<tr>" +
      '<th class="col-sticky-1" scope="col"><span class="sr-only">选择</span></th>' +
      '<th class="col-sticky-2" scope="col">技能</th>' +
      '<th class="col-tier" scope="col">tier</th>' +
      '<th class="col-version" scope="col">版本</th>' +
      platforms
        .map(
          (p) =>
            `<th class="col-platform" scope="col" title="${escapeHtml(p.name)}">${escapeHtml(p.id)}</th>`
        )
        .join("") +
      "</tr>";

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
      tr.dataset.search = [sk.key, sk.repo, sk.summary, sk.name, sk.notes]
        .join(" ")
        .toLowerCase();

      const planCells = platforms
        .map((p) => {
          const val = (sk.plan && sk.plan[p.id]) || "skip";
          const st = (sk.status && sk.status[p.id]) || "";
          const ring = STATUS_RING[st] || "";
          const planLabel =
            (data.plan_labels && data.plan_labels[val]) || val;
          const statusLabel =
            (data.status_labels && data.status_labels[st]) || st || "无状态";
          const opts = planOptions()
            .map(
              (o) =>
                `<option value="${escapeHtml(o)}"${o === val ? " selected" : ""}>${escapeHtml(o)}</option>`
            )
            .join("");
          const title = `plan：${planLabel} · status：${statusLabel}`;
          return (
            `<td class="cell-platform">` +
            `<select class="plan-sel ${escapeHtml(val)} ${ring}" ` +
            `data-skill="${escapeHtml(sk.key)}" data-platform="${escapeHtml(p.id)}" ` +
            `title="${escapeHtml(title)}" aria-label="${escapeHtml(sk.key)} 在 ${escapeHtml(p.id)} 的规划（当前 ${escapeHtml(planLabel)}，状态 ${escapeHtml(statusLabel)}）">` +
            opts +
            "</select></td>"
          );
        })
        .join("");

      const ver = sk.version
        ? escapeHtml(sk.version)
        : `<span class="muted" title="${escapeHtml(sk.version_reason || "无版本")}">—</span>`;

      tr.innerHTML =
        '<td class="col-sticky-1">' +
        `<label class="checkbox"><input type="checkbox" class="row-sel" value="${escapeHtml(sk.key)}" ` +
        `aria-label="选择技能 ${escapeHtml(sk.key)}" /><span class="checkbox__box"></span></label>` +
        "</td>" +
        '<td class="col-sticky-2">' +
        '<span class="cell-key">' +
        `<span class="cell-key__name" title="${escapeHtml(sk.key)}">${escapeHtml(sk.key)}</span>` +
        `<span class="cell-key__sub" title="${escapeHtml(sk.summary || sk.notes || "")}">` +
        `${escapeHtml(sk.summary || sk.notes || "—")}</span>` +
        `<span class="cell-key__repo" title="${escapeHtml(sk.repo || "")}">` +
        `${escapeHtml(sk.repo || "—")}</span>` +
        "</span></td>" +
        `<td class="col-tier">${escapeHtml(sk.tier || "—")}</td>` +
        `<td class="col-version cell-mono">${ver}</td>` +
        planCells;

      tbody.appendChild(tr);
    }

    tbody.querySelectorAll("select.plan-sel").forEach((sel) => {
      sel.addEventListener("change", () => {
        const skill = sel.dataset.skill;
        const platform = sel.dataset.platform;
        current.set(planKey(skill, platform), sel.value);
        syncRowDirty(sel);
        updateDirtyUI();
      });
    });
    tbody.querySelectorAll("input.row-sel").forEach((cb) => {
      cb.addEventListener("change", () => {
        cb.closest("tr").classList.toggle("is-selected", cb.checked);
        syncSelectAll();
        updateSelCount();
      });
    });

    applyFilter();
    updateDirtyUI();
    updateSelCount();
  }

  function syncRowDirty(sel) {
    const skill = sel.dataset.skill;
    const platform = sel.dataset.platform;
    const isDirty =
      original.get(planKey(skill, platform)) !== sel.value;
    sel.classList.toggle("is-dirty", isDirty);
  }

  function visibleRows() {
    return [...tbody.querySelectorAll("tr:not(.is-hidden)")];
  }

  function selectedSkills() {
    return visibleRows()
      .filter((tr) => tr.classList.contains("is-selected"))
      .map((tr) => tr.dataset.key);
  }

  function updateSelCount() {
    $("selCount").textContent = `已选 ${selectedSkills().length} 个`;
  }

  function syncSelectAll() {
    const rows = visibleRows();
    const boxes = rows.map((tr) => tr.querySelector("input.row-sel"));
    const all = boxes.filter((b) => b && b.checked);
    const box = $("selectAll");
    box.checked = rows.length > 0 && all.length === rows.length;
    box.indeterminate = all.length > 0 && all.length < rows.length;
  }

  function updateDirtyUI() {
    const n = dirtyCount();
    const dirty = n > 0;
    $("btnSavePlan").disabled = !dirty;
    const hint = $("dirtyHint");
    hint.classList.toggle("hidden", !dirty);
    hint.textContent = `${n} 项未保存改动`;
  }

  function applyFilter() {
    const q = ($("filter").value || "").trim().toLowerCase();
    const tier = $("tierFilter").value;
    let shown = 0;
    tbody.querySelectorAll("tr").forEach((tr) => {
      const okQ = !q || (tr.dataset.search || "").includes(q);
      const okT = !tier || tr.dataset.tier === tier;
      const ok = okQ && okT;
      tr.classList.toggle("is-hidden", !ok);
      if (ok) shown += 1;
    });
    emptyState.classList.toggle("hidden", shown > 0);
    syncSelectAll();
    updateSelCount();
  }

  /* ---------------- 接口 ---------------- */

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
    $("chipCount").textContent = `${(data.skills || []).length} 个技能`;
    $("chipUpdated").textContent = `规划更新 ${data.updated || "—"}`;
    renderTierFilter();
    renderReleasePlatforms();
    renderTable();
  }

  const bumpPart = () =>
    $("bumpPart").querySelector(".is-selected").dataset.part;

  const releasePlatforms = () =>
    [...document.querySelectorAll("input.rel-plat:checked")].map(
      (el) => el.value
    );

  /* ---------------- 操作 ---------------- */

  async function savePlan() {
    const changes = collectDirtyChanges();
    if (!changes.length) {
      snack("没有需要保存的改动");
      return;
    }
    const go = await confirmDialog(
      `保存 ${changes.length} 个技能的规划改动？`,
      "只写 publishing-plan.json 并刷新 md 视图，不会触发发布。"
    );
    if (!go) return;
    setBusy(true, "正在保存规划…");
    try {
      log(`保存规划：${changes.length} 项…`);
      const r = await api("/api/plan", { changes });
      if (r.view_log) log(r.view_log);
      if (r.failed && r.failed.length) {
        log(JSON.stringify(r.failed, null, 2));
      }
      await reload();
      log(r.ok ? "规划已保存" : "规划保存有失败项");
      snack(r.ok ? "规划已保存" : "规划保存有失败项，见日志");
    } catch (e) {
      log(`保存失败：${e.message || e}`);
      snack("保存失败，见日志");
    } finally {
      setBusy(false);
      updateDirtyUI();
    }
  }

  function requireSelection() {
    const skills = selectedSkills();
    if (!skills.length) {
      snack("请先勾选技能");
      return null;
    }
    return skills;
  }

  async function doUpgrade() {
    const skills = requireSelection();
    if (!skills) return;
    const part = bumpPart();
    const go = await confirmDialog(
      `对 ${skills.length} 个技能执行升级（--part ${part}）？`,
      "工作区必须干净；升号后会自动 commit（不 push、不发布）。\n" +
        skills.join("、")
    );
    if (!go) return;
    setBusy(true, "正在升级…");
    try {
      log(`升级 ${skills.join(", ")} part=${part}`);
      const r = await api("/api/upgrade", { skills, part });
      for (const item of r.results || []) {
        log(`--- ${item.skill} exit=${item.exit} ---`);
        if (item.log) log(item.log);
      }
      await reload();
      snack(r.ok ? "升级完成" : "升级有失败项，见日志");
    } catch (e) {
      log(`升级失败：${e.message || e}`);
      snack("升级失败，见日志");
    } finally {
      setBusy(false);
      updateDirtyUI();
    }
  }

  async function doUnmanage() {
    const skills = requireSelection();
    if (!skills) return;
    const go = await confirmDialog(
      `将 ${skills.length} 个技能移出管理？`,
      "不删本机目录，也不改技能仓 git。\n" + skills.join("、")
    );
    if (!go) return;
    setBusy(true, "正在移出管理…");
    try {
      log(`移出管理：${skills.join(", ")}`);
      const r = await api("/api/unmanage", { skills });
      for (const item of r.results || []) {
        log(`--- exit=${item.exit} ---`);
        if (item.log) log(item.log);
      }
      await reload();
      snack(r.ok ? "已移出管理" : "移出管理有失败，见日志");
    } catch (e) {
      log(`移出失败：${e.message || e}`);
      snack("移出失败，见日志");
    } finally {
      setBusy(false);
      updateDirtyUI();
    }
  }

  async function doRelease() {
    const skills = requireSelection();
    if (!skills) return;
    const platforms = releasePlatforms();
    if (!platforms.length) {
      snack("请至少勾选一个发布平台");
      return;
    }
    let body =
      `目标平台：${platforms.join("、")}\n` +
      "需本机 path 与凭据就绪；不替你 commit，也不跳过 preflight。";
    if (hasDirty()) {
      body +=
        "\n\n注意：表里有未保存的规划改动，发布不会带上这些改动。";
    }
    const go = await confirmDialog(
      `批量发布 ${skills.length} 个技能？`,
      body,
      "确认发布"
    );
    if (!go) return;

    setBusy(true, `正在发布到 ${platforms.join("、")}…`);
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
      snack(r.ok ? "批量发布完成" : "批量发布有失败，见日志");
    } catch (e) {
      log(`发布失败：${e.message || e}`);
      snack("发布失败，见日志");
    } finally {
      setBusy(false);
      updateDirtyUI();
    }
  }

  async function showHelp() {
    await confirmDialog(
      "这个控制台做什么",
      [
        "· 保存规划：只改 publishing-plan.json 的 plan 值并刷新 md 视图，不发布。",
        "· 升级：跑 upgrade_skill.py，工作区须干净，升号后自动 commit（不 push）。",
        "· 移出管理：从管理面摘掉技能，不动本机目录与 git。",
        "· 批量发布：串行跑 release.py，需本机 path 与凭据就绪。",
        "",
        "规划保存与真正发版始终是两个独立操作。",
      ].join("\n"),
      "知道了"
    );
  }

  /* ---------------- 事件绑定 ---------------- */

  $("selectAll").addEventListener("change", () => {
    const on = $("selectAll").checked;
    visibleRows().forEach((tr) => {
      const cb = tr.querySelector("input.row-sel");
      cb.checked = on;
      tr.classList.toggle("is-selected", on);
    });
    updateSelCount();
  });

  $("bumpPart").addEventListener("click", (e) => {
    const btn = e.target.closest(".segmented__item");
    if (!btn) return;
    $("bumpPart")
      .querySelectorAll(".segmented__item")
      .forEach((b) => {
        const on = b === btn;
        b.classList.toggle("is-selected", on);
        b.setAttribute("aria-pressed", String(on));
      });
  });

  $("filter").addEventListener("input", applyFilter);
  $("tierFilter").addEventListener("change", applyFilter);

  $("btnSavePlan").addEventListener("click", savePlan);
  $("btnUpgrade").addEventListener("click", doUpgrade);
  $("btnUnmanage").addEventListener("click", doUnmanage);
  $("btnRelease").addEventListener("click", doRelease);
  $("btnClearLog").addEventListener("click", () => {
    logEl.textContent = "";
  });

  $("btnTheme").addEventListener("click", () => {
    const next =
      document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch { /* 忽略 */ }
  });

  $("btnReload").addEventListener("click", () => {
    setBusy(true, "正在加载…");
    reload()
      .then(() => snack("已重新加载"))
      .catch((e) => {
        log(`加载失败：${e.message || e}`);
        emptyText.innerHTML = `加载失败：${escapeHtml(e.message || e)}，详见运行日志。`;
        emptyState.classList.remove("hidden");
        snack("加载失败，见日志");
      })
      .finally(() => setBusy(false));
  });

  $("btnHelp").addEventListener("click", showHelp);

  /* ---------------- 启动 ---------------- */

  initTheme();
  emptyText.textContent = "正在加载规划…";
  emptyState.classList.remove("hidden");

  reload()
    .catch((e) => {
      log(`加载失败：${e.message || e}`);
      emptyText.innerHTML = `加载失败：${escapeHtml(e.message || e)}，详见运行日志。`;
      emptyState.classList.remove("hidden");
      snack("加载失败，见日志");
    });
})();
