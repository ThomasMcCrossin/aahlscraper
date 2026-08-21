import { displayModel, nextPollDelay } from "./scoreboard-state.js";

export function renderScoreboard(root, payload) {
  root.replaceChildren();
  const games = payload?.games || [];
  if (!games.length) {
    const empty = document.createElement("section"); empty.className = "empty-panel"; empty.textContent = "No games are currently available."; root.append(empty); return;
  }
  for (const game of games) {
    const m = displayModel(game), card = document.createElement("article"); card.className = "score-card";
    card.innerHTML = `<div class="score-head"><span class="game-id">Game ${escapeHtml(m.gameId)}</span><span class="status ${m.status}">${m.status === "final" ? "FINAL" : "LIVE · UNOFFICIAL"}</span></div><div class="teams"><div><strong>${escapeHtml(m.away)}</strong><b>${m.awayScore}</b></div><div><strong>${escapeHtml(m.home)}</strong><b>${m.homeScore}</b></div></div>`;
    const meta = document.createElement("p"); meta.className = "summary";
    meta.textContent = m.penalties.length ? `${m.penalties.length} penalty${m.penalties.length === 1 ? "" : "ies"}` : "";
    card.append(meta); root.append(card);
  }
}
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

export function startPolling({ root, endpoint = "/api/public/scoreboard", fetcher = fetch, timer = window, random = Math.random } = {}) {
  let attempt = 0, stopped = false, timeout;
  const run = async () => {
    try {
      const response = await fetcher(endpoint); if (!response.ok) throw new Error("scoreboard unavailable");
      renderScoreboard(root, await response.json()); attempt = 0;
    } catch { attempt += 1; if (!root.childElementCount) renderScoreboard(root, { games: [] }); }
    if (!stopped) timeout = timer.setTimeout(run, nextPollDelay(attempt, random));
  };
  run();
  return () => { stopped = true; if (timeout) timer.clearTimeout(timeout); };
}

if (typeof document !== "undefined") startPolling({ root: document.querySelector("#scoreboard-list") });
