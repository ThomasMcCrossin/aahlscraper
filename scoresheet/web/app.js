/* AAHL Live Scoresheet — PWA front-end (vanilla JS, offline-first).
 *
 * The tablet is the durable buffer: every goal/penalty is written to
 * localStorage immediately, so scoring never blocks on the network. A debounced
 * sync re-POSTs the FULL summary arrays to the proxy (HomeTeamsOnline replace
 * semantics), so retries after flaky rink wifi are always safe.
 *
 * DOM is built with the h() helper + textContent (no markup-from-strings), so
 * roster/team names can never be interpreted as HTML. */

import { apiHeaders, createGameState, createSyncQueue, createLeaseClient, normalizeApiError, resumeGame, validateGoal, validatePenalty, deleteEvent, undoDeletion, editEvent, exportRecovery, importRecovery, confirmGameIdentity, recomputeRunningScore, syncPayload } from "./state.js";

const CFG_KEY = "aahl_cfg";
const PERIODS = ["1", "2", "3", "OT", "2OT", "SO"];
const STRENGTHS = ["ES", "PP", "SH", "EN", "EA", "PS"];
const PEN_LENGTHS = ["2", "3", "4", "5", "10"];

let cfg = loadCfg();
let activeGameId = null;
let syncTimer = null;
const gameQueues = new Map();
const gameLeases = new Map();

const $ = (id) => document.getElementById(id);
const screens = ["settings", "games", "game"];

// ---------------------------------------------------------------------------
// DOM helpers (XSS-safe by construction)
// ---------------------------------------------------------------------------
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v == null) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k === "dataset") Object.assign(el.dataset, v);
      else if (k.startsWith("on") && typeof v === "function") el[k.toLowerCase()] = v;
      else el.setAttribute(k, v);
    }
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.appendChild(typeof kid === "string" || typeof kid === "number" ? document.createTextNode(String(kid)) : kid);
  }
  return el;
}
function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
function opt(value, label, selected) { const o = h("option", { value }); o.textContent = label; if (selected) o.selected = true; return o; }
function select(props, items, selVal) {
  const s = h("select", props);
  for (const it of items) s.appendChild(opt(it.value, it.label, it.value === selVal));
  return s;
}

// ---------------------------------------------------------------------------
// Config / storage
// ---------------------------------------------------------------------------
function loadCfg() { try { return JSON.parse(localStorage.getItem(CFG_KEY)) || {}; } catch { return {}; } }
function saveCfg(c) { cfg = c; localStorage.setItem(CFG_KEY, JSON.stringify(c)); }
function gameKey(id) { return `aahl_game_${id}`; }
function loadGame(id) { try { return JSON.parse(localStorage.getItem(gameKey(id))); } catch { return null; } }
function saveGame(s) { localStorage.setItem(gameKey(s.gameId), JSON.stringify(s)); }

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------
async function api(path, opts = {}) {
  const res = await fetch(cfg.api.replace(/\/$/, "") + path, {
    ...opts,
    headers: apiHeaders(cfg, opts.headers),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw normalizeApiError(data, res.status);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
function show(name) {
  screens.forEach((s) => { $(`screen-${s}`).hidden = s !== name; });
  $("backBtn").hidden = name !== "game";
  if (name === "games") $("title").textContent = "AAHL Scoresheet";
}
function badge(state) { $("syncBadge").className = "badge " + (state || ""); }

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
function initSettings() {
  $("cfgApi").value = cfg.api || "";
  $("cfgToken").value = cfg.token || "";
  $("cfgOperator").value = cfg.operatorId || "";
  $("cfgSave").onclick = () => {
    saveCfg({ api: $("cfgApi").value.trim(), token: $("cfgToken").value.trim(), operatorId: $("cfgOperator").value.trim() });
    if (cfg.api && cfg.token && cfg.operatorId) showGames();
    else { alert("Proxy URL, access code, and operator label are all required."); show("settings"); }
  };
}

// ---------------------------------------------------------------------------
// Games list
// ---------------------------------------------------------------------------
async function showGames() {
  if (!cfg.api || !cfg.token || !cfg.operatorId) { show("settings"); return; }
  show("games");
  clear($("gamesList"));
  $("gamesEmpty").hidden = true;
  try {
    const games = await api("/api/games");
    localStorage.setItem("aahl_games", JSON.stringify(games));
    renderGames(games);
  } catch (e) {
    const cached = JSON.parse(localStorage.getItem("aahl_games") || "[]");
    if (cached.length) renderGames(cached);
    else { $("gamesEmpty").hidden = false; $("gamesEmpty").textContent = "Can't reach proxy: " + e.message; }
  }
}
function renderGames(games) {
  const list = $("gamesList");
  clear(list);
  $("gamesEmpty").hidden = games.length > 0;
  for (const g of games) {
    const local = loadGame(g.gameId);
    const card = h("div", { class: "card tappable", onclick: () => openGame(g) },
      h("div", null,
        h("div", { class: "gname" }, g.away || "?", h("span", { class: "muted" }, " @ "), g.home || "?"),
        h("div", { class: "gmeta" }, `${fmtDate(g.startMs)} · ${g.location || ""}${local ? " · 📝 saved" : ""}`)),
      h("div", { class: "muted" }, "›"));
    list.appendChild(card);
  }
}

// ---------------------------------------------------------------------------
// Scoring screen
// ---------------------------------------------------------------------------
async function openGame(g) {
  if (!cfg.api || !cfg.token || !cfg.operatorId) {
    alert("Proxy URL, access code, and operator label are required before opening a protected game.");
    show("settings"); return;
  }
  let store = loadGame(g.gameId);
  const previousIdentity = store && store.gameIdentity;
  if (!store) store = createGameState(g);
  store.gameIdentity = { gameId: g.gameId, date: g.date || fmtDate(g.startMs).split(" ").slice(0, 2).join(" "), time: g.time || (g.startMs ? new Date(g.startMs).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : ""), rink: g.rink || g.location || "", away: g.away || "", home: g.home || "" };
  if (previousIdentity && JSON.stringify(previousIdentity) !== JSON.stringify(store.gameIdentity)) {
    store.resume = { required: true, confirmed: false }; store.remoteBaseline = null;
  }
  activeGameId = g.gameId;
  try {
    const setup = await api(`/api/games/${g.gameId}/setup?div=${encodeURIComponent(g.homeDiv)}&g2=${encodeURIComponent(g.gameId2)}`);
    if (g.seasonMapId && setup.seasonMapId !== g.seasonMapId) {
      alert("Season/team map changed; setup is blocked until the schedule is refreshed.");
      return;
    }
    store.setup = setup;
    store.seasonMapId = setup.seasonMapId || g.seasonMapId;
    const current = setup.current || {};
    const remote = { goals: current.goals || [], penalties: current.penalties || [], comparisonToken: current.comparisonToken };
    const sameBaseline = store.remoteBaseline && store.remoteBaseline.comparisonToken === remote.comparisonToken;
    if (!sameBaseline || store.resume?.confirmed !== true) {
      const identity = store.gameIdentity;
      const label = `${identity.date} ${identity.time} · ${identity.rink} · ${identity.away} @ ${identity.home} · game ${identity.gameId}`;
      if (!confirm(`Confirm exact game:\n${label}\n\nImport authoritative events before editing?`)) {
        alert("Resume/import cancelled; no replacement is allowed."); return;
      }
      if (!confirmGameIdentity(identity, { ...identity, confirmed: true })) { alert("Exact-game confirmation failed."); return; }
      resumeGame(store, remote, { gameId: g.gameId, confirmed: true });
    }
    const lease = leaseFor(g.gameId);
    const acquired = await lease.ensure();
    store.leaseId = acquired.leaseId;
    store.leaseExpiresAt = acquired.expiresAt;
    const f = current.finals;
    store._existingWarn = (remote.goals.length || remote.penalties.length || (f && (f.h || f.a))) ? "Authoritative events imported; local edits use its comparison token." : "";
  } catch (e) {
    if (e.status === "conflict" || e.reason === "lease_owned" || e.reason === "lease_conflict" || e.reason === "identity_required") {
      alert("This game is not available for protected scoring: " + e.message);
      return;
    }
    if (!store.setup) { alert("Couldn't load rosters: " + e.message); return; }
  }
  saveGame(store);
  show("game");
  $("title").textContent = "Scoring";
  renderGame();
}

function renderGame() {
  const s = loadGame(activeGameId);
  if (!s) return;
  $("sbAway").textContent = s.away || "Away";
  $("sbHome").textContent = s.home || "Home";
  const sc = computeScore(s);
  $("sbAwayScore").textContent = sc.away;
  $("sbHomeScore").textContent = sc.home;
  $("sbMeta").textContent = (s._existingWarn ? "⚠ " : "") + (s.location || "");
  $("sbMeta").title = s._existingWarn || "";

  const ev = $("events");
  clear(ev);
  const items = [
    ...s.scoreSummary.map((g, i) => ({ kind: "goal", i, g })),
    ...s.penaltySummary.map((p, i) => ({ kind: "pen", i, p })),
  ].reverse();
  for (const it of items) ev.appendChild(it.kind === "goal" ? goalEl(s, it.g, it.i) : penEl(s, it.p, it.i));

  const labels = {
    pending: "Pending",
    verifying: "Verifying authoritative state…",
    "goal-published/partial": "Goal published · penalty pending",
    "penalty-published": "Penalty published · verification pending",
    published: "Published",
    conflict: "Conflict — retry after review",
    "goal-failed": "Goal phase failed — retry",
    error: "Publication failed — retry",
  };
  const t = s.dirty ? (labels[s.syncStatus] || "Unsynced changes") : s.syncStatus === "published" ? "Published " + (s.lastSyncedAt ? timeAgo(s.lastSyncedAt) : "") : s.lastSyncedAt ? "Published " + timeAgo(s.lastSyncedAt) : "Nothing synced yet";
  $("syncText").textContent = (navigator.onLine ? "" : "Offline · ") + t;
  $("syncText").title = s.syncError || "";
  $("undoBtn").hidden = !s.undo || Date.now() > s.undo.expiresAt;
  $("undoBtn").textContent = s.undo ? `Undo deletion (${Math.max(0, Math.ceil((s.undo.expiresAt - Date.now()) / 1000))}s)` : "Undo deletion";
}

function computeScore(s) {
  let home = 0, away = 0;
  for (const g of s.scoreSummary) (g.scoreTeam === s.homeDiv ? home++ : away++);
  return { home, away };
}
function nameOf(s, div, id) {
  const team = div === s.homeDiv ? s.setup.home : s.setup.away;
  const p = (team.players || []).find((x) => x.id === id);
  return p ? `${p.number} ${p.name}` : "";
}
function delBtn(onclick) { return h("button", { class: "edel", onclick }, "✕"); }
function editBtn(onclick) { return h("button", { class: "edel", onclick }, "Edit"); }

function editPrompt(s, kind, index) {
  const key = kind === "goal" ? "scoreSummary" : "penaltySummary";
  const raw = prompt("Edit event as JSON", JSON.stringify(s[key][index]));
  if (raw == null) return;
  try { editEvent(s, kind, index, JSON.parse(raw)); saveGame(s); scheduleSync(); renderGame(); }
  catch (e) { alert(`Invalid event: ${e.message}`); }
}

function goalEl(s, g, i) {
  const team = g.scoreTeam === s.homeDiv ? s.home : s.away;
  const assists = [g.assists1, g.assists2].filter(Boolean).map((id) => nameOf(s, g.scoreTeam, id)).join(", ");
  return h("div", { class: "event goal" },
    h("div", { class: "etop" }, h("span", { class: "etag" }, `GOAL · ${team}`),
      editBtn(() => editPrompt(s, "goal", i)),
      delBtn(() => { try { deleteEvent(s, "goal", i); saveGame(s); scheduleSync(); renderGame(); } catch (e) { alert(e.message); } })),
    h("div", { class: "edetail" }, `P${g.period} ${g.scoreTime} ${g.strength} · ${nameOf(s, g.scoreTeam, g.scorer)}${assists ? " (A: " + assists + ")" : ""}`));
}
function penEl(s, p, i) {
  const team = p.penaltyTeam === s.homeDiv ? s.home : s.away;
  const inf = (s.setup.infractions.find((x) => x.code === p.infraction) || {}).label || p.infraction;
  return h("div", { class: "event pen" },
    h("div", { class: "etop" }, h("span", { class: "etag" }, `PEN · ${team}`),
      editBtn(() => editPrompt(s, "penalty", i)),
      delBtn(() => { try { deleteEvent(s, "penalty", i); saveGame(s); scheduleSync(); renderGame(); } catch (e) { alert(e.message); } })),
    h("div", { class: "edetail" }, `P${p.period} ${p.penaltyTime} · ${nameOf(s, p.penaltyTeam, p.penaltyPlayer)} · ${inf} ${p.penaltyLength}m`));
}

// ---------------------------------------------------------------------------
// Add Goal / Penalty (modal)
// ---------------------------------------------------------------------------
function playerItems(s, div) {
  const team = div === s.homeDiv ? s.setup.home : s.setup.away;
  return [{ value: "", label: "- player -" }].concat((team.players || []).map((p) => ({ value: p.id, label: `${p.number} ${p.name}` })));
}
function listItems(arr) { return arr.map((v) => ({ value: v, label: v })); }

function teamSeg(s, div, onpick) {
  const seg = h("div", { class: "seg" });
  for (const t of [{ div: s.awayDiv, name: s.away }, { div: s.homeDiv, name: s.home }]) {
    const b = h("button", { class: t.div === div ? "on" : "" }, t.name);
    b.onclick = () => { seg.querySelectorAll("button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); onpick(t.div); };
    seg.appendChild(b);
  }
  return seg;
}
function field(labelText, control) { return h("label", null, labelText, control); }

function openModal(title, bodyNode, onOk) {
  $("modalTitle").textContent = title;
  clear($("modalBody"));
  $("modalBody").appendChild(bodyNode);
  $("modal").hidden = false;
  $("modalCancel").onclick = () => ($("modal").hidden = true);
  $("modalOk").onclick = () => { if (onOk() !== false) $("modal").hidden = true; };
}

function addGoalModal() {
  const s = loadGame(activeGameId);
  let div = s.homeDiv;
  const scorer = select({ id: "mScorer" }, playerItems(s, div));
  const a1 = select({ id: "mA1" }, playerItems(s, div));
  const a2 = select({ id: "mA2" }, playerItems(s, div));
  const period = select({ id: "mPeriod" }, listItems(PERIODS), "1");
  const time = h("input", { id: "mTime", inputmode: "numeric", placeholder: "mm:ss" });
  const strength = select({ id: "mStrength" }, listItems(STRENGTHS), "ES");

  const body = h("div", null,
    teamSeg(s, div, (d) => {
      div = d;
      [scorer, a1, a2].forEach((sel) => { clear(sel); for (const it of playerItems(s, d)) sel.appendChild(opt(it.value, it.label)); });
    }),
    field("Scorer", scorer),
    h("div", { class: "grid2" }, field("Assist 1", a1), field("Assist 2", a2)),
    h("div", { class: "grid2" }, field("Period", period), field("Time", time)),
    field("Strength", strength));

  openModal("Add Goal", body, () => {
    if (!scorer.value) { alert("Pick a scorer"); return false; }
    const event = {
      assists1: a1.value, assists2: a2.value, period: period.value, scoreTeam: div,
      scoreTime: normTime(time.value), scorer: scorer.value, strength: strength.value, scoreTotalText: "",
    };
    const checked = validateGoal(event, s.setup); if (!checked.valid) { alert(checked.errors.join("\n")); return false; }
    s.scoreSummary.push(event);
    recomputeTotals(s); markDirty(s); renderGame();
  });
}

function addPenaltyModal() {
  const s = loadGame(activeGameId);
  let div = s.homeDiv;
  const player = select({ id: "mPlayer" }, playerItems(s, div));
  const inf = h("select", { id: "mInf" });
  for (const x of s.setup.infractions) { const o = opt(x.code, x.label); o.dataset.sev = x.severity; inf.appendChild(o); }
  const len = select({ id: "mLen" }, listItems(PEN_LENGTHS), "3");
  const period = select({ id: "mPeriod" }, listItems(PERIODS), "1");
  const time = h("input", { id: "mTime", inputmode: "numeric", placeholder: "mm:ss" });

  const body = h("div", null,
    teamSeg(s, div, (d) => { div = d; clear(player); for (const it of playerItems(s, d)) player.appendChild(opt(it.value, it.label)); }),
    field("Player", player),
    field("Infraction", inf),
    h("div", { class: "grid2" }, field("Length", len), field("Period", period)),
    field("Time", time));

  openModal("Add Penalty", body, () => {
    if (!player.value) { alert("Pick a player"); return false; }
    const event = {
      period: period.value, penaltyTeam: div, penaltyTime: normTime(time.value),
      penaltyPlayer: player.value, servedPlayer: player.value,
      infraction: inf.value, severity: inf.selectedOptions[0] ? inf.selectedOptions[0].dataset.sev : "minor",
      penaltyLength: Number(len.value),
    };
    const checked = validatePenalty(event, s.setup); if (!checked.valid) { alert(checked.errors.join("\n")); return false; }
    s.penaltySummary.push(event);
    markDirty(s); renderGame();
  });
}

// running score text "(home-away)" in chronological (array) order
function recomputeTotals(s) {
  s.scoreSummary = recomputeRunningScore(s.scoreSummary, s.homeDiv);
}

// ---------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------
function markDirty(s) { s.revision = (s.revision || 0) + 1; s.dirty = true; s.syncStatus = "pending"; saveGame(s); scheduleSync(); }
function scheduleSync() { clearTimeout(syncTimer); badge("pending"); syncTimer = setTimeout(syncActive, 1200); }

function queueFor(s) {
  if (!gameQueues.has(s.gameId)) gameQueues.set(s.gameId, createSyncQueue({
    isOnline: () => navigator.onLine,
    persist: (state) => { if (state.syncStatus === "published") state.lastSyncedAt = Date.now(); saveGame(state); if (state.gameId === activeGameId) renderGame(); },
    prepare: async (state) => {
      const activeLease = await leaseFor(state.gameId).ensure();
      state.leaseId = activeLease.leaseId;
      state.leaseExpiresAt = activeLease.expiresAt;
      saveGame(state);
      return syncPayload(state);
    },
    send: (payload) => api(`/api/games/${payload.gameId}/sync`, { method: "POST", body: JSON.stringify({ username: s.homeDiv, ...payload }) }),
  }));
  return gameQueues.get(s.gameId);
}

async function syncActive() {
  const s = loadGame(activeGameId);
  if (!s || !s.dirty) { badge(s && s.lastSyncedAt ? "ok" : ""); return; }
  if (!navigator.onLine) { badge("pending"); renderGame(); return; }
  try {
    recomputeTotals(s); queueFor(s).enqueue(s); badge("pending");
  } catch (e) {
    badge("err"); $("syncText").textContent = "Sync failed: " + e.message + " (will retry)";
    return;
  }
  renderGame();
}

function leaseFor(gameId) {
  const key = `${gameId}:${cfg.operatorId}`;
  if (!gameLeases.has(key)) gameLeases.set(key, createLeaseClient({
    gameId, operatorId: cfg.operatorId,
    request: ({ action, leaseId, ttlMs }) => api(`/api/games/${gameId}/lease`, { method: "POST", body: JSON.stringify({ action, leaseId, ttlMs }) }),
  }));
  return gameLeases.get(key);
}

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------
function normTime(v) { v = (v || "").trim(); if (/^\d{1,2}$/.test(v)) return v + ":00"; return v || "0:00"; }
function fmtDate(ms) {
  if (!ms) return "";
  const d = new Date(ms);
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) + " " +
         d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}
function timeAgo(ms) { const s = Math.round((Date.now() - ms) / 1000); if (s < 60) return s + "s ago"; if (s < 3600) return Math.round(s / 60) + "m ago"; return Math.round(s / 3600) + "h ago"; }

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
function boot() {
  initSettings();
  $("backBtn").onclick = showGames;
  $("refreshGames").onclick = showGames;
  $("addGoal").onclick = addGoalModal;
  $("addPenalty").onclick = addPenaltyModal;
  $("syncNow").onclick = syncActive;
  $("undoBtn").onclick = () => { const s = loadGame(activeGameId); try { undoDeletion(s); saveGame(s); scheduleSync(); renderGame(); } catch (e) { alert(e.message); } };
  $("exportBtn").onclick = () => { const s = loadGame(activeGameId); const blob = new Blob([exportRecovery(s)], { type: "application/json" }); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `aahl-${s.gameId}-recovery.json`; a.click(); URL.revokeObjectURL(a.href); };
  $("importInput").onchange = async (event) => { const s = loadGame(activeGameId); const file = event.target.files[0]; if (!file) return; try { const next = importRecovery(s, await file.text(), s.gameIdentity); saveGame(next); scheduleSync(); renderGame(); } catch (e) { alert(`Recovery rejected: ${e.message}`); } event.target.value = ""; };
  window.addEventListener("online", () => { badge("pending"); syncActive(); });
  window.addEventListener("offline", () => { badge("pending"); if (activeGameId) renderGame(); });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  if (cfg.api && cfg.token && cfg.operatorId) showGames(); else show("settings");
}
boot();
