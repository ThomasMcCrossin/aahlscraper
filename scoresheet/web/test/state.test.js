import assert from "node:assert/strict";
import test from "node:test";
import { apiHeaders, captureEvent, createGameState, createLeaseClient, createSyncQueue, normalizeApiError, normalizeGameCode, gameCodeKey, storeGameCode, getGameCode, removeGameCode, isAuthorizationError, resumeGame, syncPayload, validateGoal, validatePenalty, validateEvents, deleteEvent, undoDeletion, editEvent, exportRecovery, importRecovery, confirmGameIdentity, recomputeRunningScore } from "../state.js";

const game = { gameId: "g-1", homeDiv: "H", awayDiv: "A" };
const remote = { goals: [{ id: "old" }], penalties: [{ id: "pen" }], comparisonToken: "token-1" };
function ready() { return resumeGame(createGameState(game), remote, { gameId: "g-1", confirmed: true }); }
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test("HomeTeamsOnline running-score fixture convention is recomputed home-away", () => {
  const events = recomputeRunningScore([{ period: "1", scoreTeam: "H" }, { period: "1", scoreTeam: "A" }, { period: "2", scoreTeam: "A" }], "H");
  assert.deepEqual(events.map((event) => event.scoreTotalText), ["(1-0)", "(1-1)", "(1-2)"]);
});

test("sync payload carries only display-safe home/away identity", () => {
  const s = ready(); s.home = "Real Home"; s.away = "Real Away";
  const payload = syncPayload(s);
  assert.deepEqual(payload.displayTeams, { home: { name: "Real Home", key: "H" }, away: { name: "Real Away", key: "A" } });
  assert.equal(payload.displayTeams.home.setup, undefined);
});

test("resume refuses blind replacement and requires exact-game confirmation", () => {
  const s = createGameState(game);
  assert.throws(() => resumeGame(s, remote, { gameId: "g-2", confirmed: true }), /exact-game/);
  assert.throws(() => captureEvent(s, "goal", { id: "new" }), /confirmation/);
  assert.deepEqual(s.scoreSummary, []);
});

test("offline capture persists immediately and reconnect drains latest revision", async () => {
  const s = ready(); let online = false; const sent = [];
  const q = createSyncQueue({ isOnline: () => online, send: async (p) => sent.push(p), persist: (x) => x.persisted = true });
  captureEvent(s, "goal", { id: "new" }); q.enqueue(s);
  assert.equal(s.persisted, true); assert.equal(sent.length, 0); assert.equal(s.dirty, true);
  online = true; q.reconnect(); await tick();
  assert.equal(sent[0].revision, 1); assert.equal(s.dirty, false);
});

test("mid-sync edit queues later revision and stale completion cannot clear it", async () => {
  const s = ready(); let resolve; const sent = [];
  const q = createSyncQueue({ send: async (p) => { sent.push(p); await new Promise(r => { resolve = r; }); } });
  captureEvent(s, "goal", { id: "one" }); q.enqueue(s);
  await tick(); captureEvent(s, "goal", { id: "two" }); q.enqueue(s);
  resolve();
  while (sent.length < 2) await tick();
  resolve(); await tick();
  assert.equal(sent.length, 2); assert.equal(sent[0].revision, 1); assert.equal(sent[1].revision, 2);
  assert.equal(s.syncedRevision, 2); assert.equal(s.dirty, false);
});

test("stale completion never persists over a separately loaded newer game object", async () => {
  const first = ready(); let resolveFirst; const persisted = [];
  const q = createSyncQueue({
    send: async (payload) => {
      if (payload.revision === 1) await new Promise((resolve) => { resolveFirst = resolve; });
    },
    persist: (state) => persisted.push({ revision: state.revision, dirty: state.dirty }),
  });
  captureEvent(first, "goal", { id: "one" }); q.enqueue(first); await tick();
  const newer = structuredClone(first);
  captureEvent(newer, "goal", { id: "two" }); q.enqueue(newer);
  persisted.length = 0;
  resolveFirst();
  while (newer.dirty) await tick();
  assert.deepEqual(persisted, [{ revision: 2, dirty: false }]);
});

test("stale response leaves a newer revision pending", async () => {
  const s = ready(); let resolve; const q = createSyncQueue({ send: async () => new Promise(r => { resolve = r; }) });
  captureEvent(s, "goal", { id: "one" }); q.enqueue(s); await tick();
  captureEvent(s, "goal", { id: "two" }); resolve(); await tick();
  assert.equal(s.dirty, true); assert.equal(s.syncStatus, "pending");
});

test("queues are isolated per game", async () => {
  const a = ready(); const b = resumeGame(createGameState({ ...game, gameId: "g-2" }), remote, { gameId: "g-2", confirmed: true });
  const sent = []; const qa = createSyncQueue({ send: async p => sent.push(["a", p]) }); const qb = createSyncQueue({ send: async p => sent.push(["b", p]) });
  captureEvent(a, "goal", { id: "a" }); captureEvent(b, "goal", { id: "b" }); qa.enqueue(a); qb.enqueue(b); await tick();
  assert.deepEqual(sent.map(x => x[0]).sort(), ["a", "b"]);
  assert.equal(syncPayload(a).gameId, "g-1");
});

test("R1 lease client acquires, renews before expiry, and reacquires after expiry", async () => {
  let now = 1000; const calls = [];
  const responses = [
    { ok: true, leaseId: "lease-1", expiresAt: 4000 },
    { ok: true, leaseId: "lease-1", expiresAt: 7000 },
    { ok: true, leaseId: "lease-2", expiresAt: 9000 },
  ];
  const lease = createLeaseClient({ gameId: "g-1", operatorId: "op-a", now: () => now, renewLeadMs: 1000,
    request: (input) => { calls.push(input); return responses.shift(); } });
  assert.equal((await lease.ensure()).leaseId, "lease-1");
  now = 3500; assert.equal((await lease.ensure()).leaseId, "lease-1");
  assert.equal(calls[1].action, "renew"); assert.equal(calls[1].leaseId, "lease-1");
  now = 8000; assert.equal((await lease.ensure()).leaseId, "lease-2");
  assert.equal(calls[2].action, "acquire"); assert.equal(calls[2].leaseId, undefined);
});

test("R1 lease conflict keeps revision dirty and sync payload carries exact lease ID", async () => {
  const s = ready(); s.leaseId = "lease-1"; let sent;
  const q = createSyncQueue({ send: async (payload) => { sent = payload; const e = new Error("lease owned"); e.status = "conflict"; e.reason = "lease_owned"; throw e; } });
  captureEvent(s, "goal", { id: "g" }); q.enqueue(s); await tick();
  assert.equal(sent.leaseId, "lease-1");
  assert.equal(s.dirty, true); assert.equal(s.syncStatus, "conflict");
  assert.equal(s.syncedRevision, 0);
});

test("game code headers have no APP_TOKEN or operator fallback", () => {
  const headers = apiHeaders({ token: "fixture-token", operatorId: "op-a", gameCode: "ab-cd 2345" });
  assert.equal(headers["X-Game-Code"], "ABCD2345");
  assert.equal(headers["X-App-Token"], undefined);
  assert.equal(headers["X-Operator-Id"], undefined);
  const error = normalizeApiError({ ok: false, code: "lease_owned", message: "game is leased" }, 409);
  assert.equal(error.status, "conflict");
  assert.equal(error.reason, "lease_owned");
});

test("game codes normalize and stay under exact game storage keys", () => {
  const data = new Map();
  const storage = { setItem: (k, v) => data.set(k, v), getItem: (k) => data.get(k) || null, removeItem: (k) => data.delete(k) };
  storeGameCode(storage, "g-1", " ab-cd 2345 ");
  assert.equal(normalizeGameCode("ab-cd 2345"), "ABCD2345");
  assert.equal(gameCodeKey("g-1"), "aahl_game_code_g-1");
  assert.equal(getGameCode(storage, "g-1"), "ABCD2345");
  assert.equal(getGameCode(storage, "g-2"), null);
  removeGameCode(storage, "g-1");
  assert.equal(getGameCode(storage, "g-1"), null);
});

test("authorization responses are actionable and local events remain unchanged", () => {
  const s = ready(); s.scoreSummary.push({ id: "local" }); s.penaltySummary.push({ id: "local-pen" });
  const before = structuredClone({ goals: s.scoreSummary, penalties: s.penaltySummary });
  for (const [reason, phrase] of [["code_expired", "expired"], ["code_revoked", "revoked"], ["wrong_game", "another game"], ["code_locked", "Too many"]]) {
    const error = normalizeApiError({ reason }, reason === "code_locked" ? 429 : 403);
    assert.equal(isAuthorizationError(error), true);
    assert.match(error.message, new RegExp(phrase, "i"));
    assert.deepEqual({ goals: s.scoreSummary, penalties: s.penaltySummary }, before);
  }
});

test("two-phase queue records complete verified publication", async () => {
  const s = ready();
  const q = createSyncQueue({ send: async () => ({ ok: true, status: "published", phase: "published", verified: true }) });
  captureEvent(s, "goal", { id: "g" }); q.enqueue(s); await tick();
  assert.equal(s.syncStatus, "published");
  assert.equal(s.syncPhase, "published");
  assert.equal(s.dirty, false);
});

test("phase failures remain visible and retry can resume", async () => {
  const s = ready(); let attempt = 0;
  const q = createSyncQueue({ send: async () => {
    attempt += 1;
    if (attempt === 1) return { ok: false, status: "goal-published/partial", phase: "penalties", message: "penalty failed", retryable: true };
    return { ok: true, status: "published", phase: "published", verified: true };
  }});
  captureEvent(s, "goal", { id: "g" }); q.enqueue(s); await tick();
  assert.equal(s.syncStatus, "goal-published/partial"); assert.equal(s.dirty, true);
  q.enqueue(s); await tick();
  assert.equal(s.syncStatus, "published"); assert.equal(s.dirty, false);
});

test("partial publication adopts the recovered remote comparison token for retry", async () => {
  const s = ready();
  const q = createSyncQueue({ send: async () => {
    const error = new Error("penalty failed");
    Object.assign(error, { status: "goal-published/partial", phase: "penalties", comparisonToken: "token-after-goal" });
    throw error;
  }});
  captureEvent(s, "goal", { id: "g" }); q.enqueue(s); await tick();
  assert.equal(s.remoteBaseline.comparisonToken, "token-after-goal");
  assert.equal(syncPayload(s).comparisonToken, "token-after-goal");
});

test("reread mismatch is represented as conflict instead of success", async () => {
  const s = ready();
  const q = createSyncQueue({ send: async () => ({ ok: false, conflict: true, status: "conflict", phase: "verification", message: "mismatch" }) });
  captureEvent(s, "penalty", { id: "p" }); q.enqueue(s); await tick();
  assert.equal(s.syncStatus, "conflict"); assert.equal(s.syncPhase, "verification");
  assert.equal(s.dirty, true); assert.match(s.syncError, /mismatch/);
});

test("stale client completion cannot replace a newer phase or clear its revision", async () => {
  const first = ready(); let release;
  const q = createSyncQueue({ send: async () => new Promise(resolve => { release = resolve; }) });
  captureEvent(first, "goal", { id: "one" }); q.enqueue(first); await tick();
  const newer = structuredClone(first); captureEvent(newer, "penalty", { id: "two" }); q.enqueue(newer);
  release({ ok: false, status: "goal-published/partial", phase: "penalties", message: "old completion" }); await tick();
  assert.equal(newer.dirty, true); assert.equal(newer.syncStatus, "pending");
  assert.equal(newer.revision, 2);
});

const setup = {
  home: { div: "H", players: [{ id: "h1" }, { id: "h2" }] },
  away: { div: "A", players: [{ id: "a1" }, { id: "a2" }] },
  infractions: [{ code: "hook", severity: "minor" }],
};
const goodGoal = { period: "1", scoreTime: "12:34", scoreTeam: "H", scorer: "h1", assists1: "h2", assists2: "", strength: "ES" };
const goodPenalty = { period: "2", penaltyTime: "08:00", penaltyTeam: "A", penaltyPlayer: "a1", servedPlayer: "a2", infraction: "hook", severity: "minor", penaltyLength: 2 };

test("T5 blocker-5 strict validation rejects malformed clocks, foreign players, duplicate assists, and bad periods", () => {
  assert.equal(validateGoal(goodGoal, setup).valid, true);
  assert.match(validateGoal({ ...goodGoal, scoreTime: "20:01" }, setup).errors.join(" "), /bounds/);
  assert.match(validateGoal({ ...goodGoal, period: "4", scorer: "a1" }, setup).errors.join(" "), /period|roster/);
  assert.match(validateGoal({ ...goodGoal, assists1: "h2", assists2: "h2" }, setup).errors.join(" "), /unique/);
  assert.equal(validatePenalty({ ...goodPenalty, penaltyLength: 3 }, setup).valid, true);
  assert.match(validatePenalty({ ...goodPenalty, penaltyLength: 5 }, setup).errors.join(" "), /duration/);
  assert.match(validatePenalty({ ...goodPenalty, servedPlayer: "h1" }, setup).errors.join(" "), /served-by/);
  assert.equal(validateEvents({ ...ready(), setup, scoreSummary: [goodGoal, goodGoal], penaltySummary: [goodPenalty] }).valid, false);
});

test("T5 edit creates a revision and deletion has an explicit short undo window", () => {
  const s = { ...ready(), setup, scoreSummary: [goodGoal], penaltySummary: [] };
  editEvent(s, "goal", 0, { ...goodGoal, scoreTime: "11:00" });
  assert.equal(s.revision, 1); assert.equal(s.scoreSummary[0].scoreTime, "11:00");
  deleteEvent(s, "goal", 0, 1000, 8000); assert.equal(s.scoreSummary.length, 0); assert.equal(s.revision, 2);
  undoDeletion(s, 8999); assert.equal(s.scoreSummary.length, 1); assert.equal(s.revision, 3);
  deleteEvent(s, "goal", 0, 1000, 8000); assert.throws(() => undoDeletion(s, 9001), /expired/);
});

test("T5 exact-game gate requires every displayed identity field", () => {
  const identity = { gameId: "g-1", date: "Aug 20", time: "7:00 PM", rink: "Amherst", away: "Away", home: "Home" };
  assert.equal(confirmGameIdentity(identity, { ...identity, confirmed: true }), true);
  assert.equal(confirmGameIdentity(identity, { ...identity, rink: "Other", confirmed: true }), false);
});

test("T5 versioned recovery round trips and refuses wrong game or newer replacement", () => {
  const s = { ...ready(), setup, gameIdentity: { gameId: "g-1", date: "Aug 20", time: "7:00 PM", rink: "Amherst", away: "Away", home: "Home" }, scoreSummary: [goodGoal], penaltySummary: [], revision: 1 };
  const restored = importRecovery({ ...createGameState({ gameId: "g-1" }), setup, gameIdentity: s.gameIdentity }, exportRecovery(s), s.gameIdentity);
  assert.deepEqual(restored.scoreSummary, [goodGoal]);
  assert.throws(() => importRecovery({ ...restored, revision: 2 }, exportRecovery(s), s.gameIdentity), /newer or equal/);
  assert.throws(() => importRecovery({ ...createGameState({ gameId: "g-2" }), setup, gameIdentity: s.gameIdentity }, exportRecovery(s), s.gameIdentity), /different/);
  assert.throws(() => importRecovery({ ...createGameState({ gameId: "g-1" }), setup, gameIdentity: s.gameIdentity }, { format: "aahl-scoresheet-recovery", version: 1, gameId: "g-1", identity: s.gameIdentity, revision: 3 }, s.gameIdentity), /arrays/);
});
