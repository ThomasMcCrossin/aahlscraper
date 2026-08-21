// Browser-independent public display state. No captain/auth/sync state is imported.
export const DEFAULT_POLL_MS = 25000;
export function displayModel(game = {}) {
  const teams = game.teams || {};
  return {
    gameId: game.gameId || "",
    home: teams.home?.name || "Home",
    away: teams.away?.name || "Away",
    homeScore: Number(game.boxScore?.HOME?.goals ?? game.boxScore?.home?.goals ?? 0),
    awayScore: Number(game.boxScore?.AWAY?.goals ?? game.boxScore?.away?.goals ?? 0),
    status: game.status === "final" ? "final" : "live",
    scores: Array.isArray(game.scores) ? game.scores : [],
    penalties: Array.isArray(game.penalties) ? game.penalties : [],
  };
}
export function backoffDelay(attempt, random = Math.random) {
  const base = Math.min(120000, 1000 * 2 ** Math.max(0, attempt));
  return Math.round(base * (0.75 + Math.max(0, Math.min(1, random())) * 0.5));
}
export function nextPollDelay(errorAttempt = 0, random = Math.random) {
  return errorAttempt ? backoffDelay(errorAttempt, random) : DEFAULT_POLL_MS;
}
export function emptyDisplay() { return { games: [], error: null, loading: false }; }
