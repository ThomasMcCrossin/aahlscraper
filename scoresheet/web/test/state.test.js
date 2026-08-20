import assert from "node:assert/strict";
import test from "node:test";
import { captureEvent, createGameState, createSyncQueue, resumeGame, syncPayload } from "../state.js";

const game = { gameId: "g-1", homeDiv: "H", awayDiv: "A" };
const remote = { goals: [{ id: "old" }], penalties: [{ id: "pen" }], comparisonToken: "token-1" };
function ready() { return resumeGame(createGameState(game), remote, { gameId: "g-1", confirmed: true }); }
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

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
