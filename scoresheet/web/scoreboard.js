import { displayModel, nextPollDelay } from "./scoreboard-state.js";

export function renderScoreboard(root, payload) {
  const doc = root.ownerDocument || globalThis.document;
  root.replaceChildren();
  const games = payload?.games || [];
  if (!games.length) {
    const empty = doc.createElement("section"); empty.className = "empty-panel"; empty.textContent = "No games are currently available."; root.append(empty); return;
  }
  for (const game of games) {
    const m = displayModel(game), card = doc.createElement("article"); card.className = "score-card";
    card.innerHTML = `<div class="score-head"><span class="game-id">Game ${escapeHtml(m.gameId)}</span><span class="status ${m.status}">${m.status === "final" ? "FINAL" : "LIVE · UNOFFICIAL"}</span></div><div class="teams"><div><strong>${escapeHtml(m.away)}</strong><b>${m.awayScore}</b></div><div><strong>${escapeHtml(m.home)}</strong><b>${m.homeScore}</b></div></div>`;
    const meta = doc.createElement("p"); meta.className = "summary";
    const summaries = [];
    if (m.periodSummary.length) summaries.push(`Periods: ${m.periodSummary.map((p) => `P${p.period} ${p.homeScore ?? p.home ?? 0}-${p.awayScore ?? p.away ?? 0}`).join(" · ")}`);
    if (m.penalties.length) summaries.push(`${m.penalties.length} penalty${m.penalties.length === 1 ? "" : "ies"}`);
    meta.textContent = summaries.join(" · ");
    card.append(meta); root.append(card);
  }
}
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

export function startPolling({ root, endpoint = "/api/public/scoreboard", fetcher = fetch, timer = window, random = Math.random, AbortControllerClass = globalThis.AbortController } = {}) {
  let attempt = 0, stopped = false, timeout;
  const controller = new AbortControllerClass();
  const run = async () => {
    try {
      const response = await fetcher(endpoint, { signal: controller.signal }); if (!response.ok) throw new Error("scoreboard unavailable");
      renderScoreboard(root, await response.json()); attempt = 0;
    } catch { attempt += 1; if (!root.childElementCount) renderScoreboard(root, { games: [] }); }
    if (!stopped) timeout = timer.setTimeout(run, nextPollDelay(attempt, random));
  };
  run();
  return () => { stopped = true; controller.abort(); if (timeout !== undefined) timer.clearTimeout(timeout); };
}

if (typeof document !== "undefined") startPolling({ root: document.querySelector("#scoreboard-list") });
