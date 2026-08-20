import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { comparisonToken, createInMemoryLeaseCoordinator, gameSetup, parseAuthoritativeEvents, syncGame } from "../src/index.js";

const fixture = await readFile(new URL("./fixtures/game-editor.html", import.meta.url), "utf8");

function installNetworkTripwire(responseText = fixture) {
  const original = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url !== "https://fixture.invalid/editor") {
      throw new Error(`unexpected network request: ${url}`);
    }
    return new Response(responseText, { status: 200 });
  };
  return () => { globalThis.fetch = original; };
}

test("Blocker 1 regression: setup imports authoritative scoring and penalty arrays", async () => {
  const restore = installNetworkTripwire();
  try {
    const env = { SESSION: { get: async () => "fixture=session" } };
    // The setup URL is fixed to HTO in production; inject the fetch boundary
    // while preserving the parser/setup contract in this network-free test.
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => new Response(fixture, { status: 200 });
    const setup = await gameSetup(env, "game-1", "HOME-DIV", "game-2");
    globalThis.fetch = originalFetch;
    assert.deepEqual(setup.current.goals, [{ period: "1", clock: "12:34", team: "HOME-DIV", scorer: "p-home-1", assists: [] }]);
    assert.equal(setup.current.penalties[0].infraction, "hook");
    assert.deepEqual(setup.current.finals, { h: 2, a: 1 });
    assert.equal(setup.current.comparisonToken, comparisonToken({
      finals: setup.current.finals,
      goals: setup.current.goals,
      penalties: setup.current.penalties,
    }));
  } finally { restore(); }
});

test("unknown editor event shape fails closed instead of creating an empty baseline", () => {
  assert.throws(
    () => parseAuthoritativeEvents('<script>globalVars.scoreSummary = {};</script>'),
    /authoritative event arrays missing or malformed/
  );
});

test("network tripwire rejects an unmocked request immediately", async () => {
  const restore = installNetworkTripwire();
  try {
    await assert.rejects(() => globalThis.fetch("https://unexpected.invalid/"), /unexpected network request/);
  } finally { restore(); }
});

test("Blocker 3 regression: leases acquire, renew, release, and expire atomically", async () => {
  let now = 1000;
  const c = createInMemoryLeaseCoordinator(() => now);
  const first = await c.acquire({ gameId: "g-1", operatorId: "op-a", ttlMs: 1000 });
  assert.equal(first.ok, true);
  assert.equal((await c.acquire({ gameId: "g-1", operatorId: "op-b" })).code, "lease_owned");
  const renewed = await c.renew({ gameId: "g-1", operatorId: "op-a", leaseId: first.leaseId, ttlMs: 2000 });
  assert.equal(renewed.expiresAt, 3000);
  assert.equal((await c.release({ gameId: "g-1", operatorId: "op-b", leaseId: first.leaseId })).code, "lease_conflict");
  now = 3000;
  assert.equal((await c.check({ gameId: "g-1", operatorId: "op-a", leaseId: first.leaseId })).code, "lease_conflict");
  const afterExpiry = await c.acquire({ gameId: "g-1", operatorId: "op-b", ttlMs: 1000 });
  assert.equal(afterExpiry.ok, true);
});

function authoritative(goals = [], penalties = [], finals = { h: 0, a: 0 }) {
  return { goals, penalties, finals, comparisonToken: comparisonToken({ finals, goals, penalties }) };
}

test("Blocker 3 regression: wrong owner, missing baseline, and stale remote token do zero writes", async () => {
  const coordinator = createInMemoryLeaseCoordinator();
  const lease = await coordinator.acquire({ gameId: "g-1", operatorId: "op-a" });
  const remote = authoritative([{ id: "remote" }]);
  let writes = 0;
  const writer = async () => { writes += 1; return { success: 1 }; };
  const base = { username: "HOME-DIV", leaseId: lease.leaseId, comparisonToken: remote.comparisonToken, scoreSummary: [], penaltySummary: [] };
  const wrongOwner = await syncGame({}, "g-1", base, { operatorId: "op-b", coordinator, authoritativeReader: async () => remote, writer });
  assert.equal(wrongOwner.code, "lease_conflict");
  assert.equal(writes, 0);
  const missing = await syncGame({}, "g-1", { ...base, leaseId: undefined }, { operatorId: "op-a", coordinator, authoritativeReader: async () => remote, writer });
  assert.equal(missing.code, "lease_required");
  assert.equal(writes, 0);
  const drift = await syncGame({}, "g-1", { ...base, comparisonToken: "stale" }, { operatorId: "op-a", coordinator, authoritativeReader: async () => remote, writer });
  assert.equal(drift.code, "remote_drift");
  assert.equal(drift.writes, 0);
  assert.equal(writes, 0);
});

test("Blocker 3 regression: compare is against a freshly read authoritative snapshot before replacement", async () => {
  const coordinator = createInMemoryLeaseCoordinator();
  const lease = await coordinator.acquire({ gameId: "g-2", operatorId: "op-a" });
  const remote = authoritative([{ id: "old" }], []);
  const calls = [];
  const writes = [];
  const result = await syncGame({}, "g-2", {
    username: "HOME-DIV", leaseId: lease.leaseId, comparisonToken: remote.comparisonToken,
    scoreSummary: [{ id: "new" }], penaltySummary: [],
  }, {
    operatorId: "op-a", coordinator,
    authoritativeReader: async ({ phase }) => { calls.push("read"); return phase === "verifying" ? authoritative([{ id: "new" }], []) : remote; },
    writer: async (_env, action) => { calls.push("write"); writes.push(action); return { success: 1 }; },
  });
  assert.equal(result.ok, true);
  assert.deepEqual(calls, ["read", "write", "write", "read"]);
  assert.deepEqual(writes, ["updateScoreSummary", "updatePenaltySummary"]);
});

test("T4 complete publication has goal, penalty, and verified phases", async () => {
  const coordinator = createInMemoryLeaseCoordinator();
  const baseline = authoritative([{ id: "old" }], [{ id: "old-pen" }]);
  const requested = { scoreSummary: [{ id: "new" }], penaltySummary: [{ id: "new-pen" }] };
  const lease = await coordinator.acquire({ gameId: "g-t4", operatorId: "op-a" });
  const phases = [];
  const result = await syncGame({}, "g-t4", { username: "H", ...requested, ...lease, comparisonToken: baseline.comparisonToken, revision: 4 }, {
    operatorId: "op-a", coordinator,
    authoritativeReader: async ({ phase }) => { phases.push(phase || "baseline"); return phase === "verifying" ? authoritative(requested.scoreSummary, requested.penaltySummary) : baseline; },
    writer: async (_env, action) => { phases.push(action); return { success: 1 }; },
  });
  assert.equal(result.ok, true);
  assert.equal(result.status, "published");
  assert.equal(result.verified, true);
  assert.deepEqual(phases, ["baseline", "updateScoreSummary", "updatePenaltySummary", "verifying"]);
});

test("T4 first-phase failure is explicit and retryable without a penalty write", async () => {
  const coordinator = createInMemoryLeaseCoordinator();
  const baseline = authoritative();
  const lease = await coordinator.acquire({ gameId: "g-fail-goal", operatorId: "op-a" });
  let writes = 0;
  const result = await syncGame({}, "g-fail-goal", { username: "H", scoreSummary: [{ id: "g" }], penaltySummary: [], ...lease, comparisonToken: baseline.comparisonToken }, {
    operatorId: "op-a", coordinator, authoritativeReader: async () => baseline,
    writer: async () => { writes += 1; throw new Error("goal unavailable"); },
  });
  assert.equal(result.ok, false); assert.equal(result.phase, "goals"); assert.equal(result.status, "goal-failed");
  assert.equal(result.retryable, true); assert.equal(writes, 1);
});

test("T4 penalty failure exposes partial goal publication and retry resumes both phases", async () => {
  const coordinator = createInMemoryLeaseCoordinator();
  const baseline = authoritative();
  const goal = [{ id: "g" }], penalty = [{ id: "p" }];
  const lease = await coordinator.acquire({ gameId: "g-fail-pen", operatorId: "op-a" });
  let failPenalty = true; const writes = []; let current = baseline;
  const result = await syncGame({}, "g-fail-pen", { username: "H", scoreSummary: goal, penaltySummary: penalty, ...lease, comparisonToken: baseline.comparisonToken }, {
    operatorId: "op-a", coordinator, authoritativeReader: async () => current,
    writer: async (_env, action) => {
      writes.push(action);
      if (action === "updateScoreSummary") current = authoritative(goal, current.penalties);
      if (action === "updatePenaltySummary" && failPenalty) { failPenalty = false; throw new Error("penalty unavailable"); }
      if (action === "updatePenaltySummary") current = authoritative(goal, penalty);
      return { success: 1 };
    },
  });
  assert.equal(result.ok, false); assert.equal(result.phase, "penalties"); assert.equal(result.status, "goal-published/partial");
  assert.equal(result.comparisonToken, current.comparisonToken);
  const retry = await syncGame({}, "g-fail-pen", { username: "H", scoreSummary: goal, penaltySummary: penalty, ...lease, comparisonToken: result.comparisonToken }, {
    operatorId: "op-a", coordinator, authoritativeReader: async () => current,
    writer: async (_env, action) => {
      writes.push(action);
      if (action === "updatePenaltySummary") current = authoritative(goal, penalty);
      return { success: 1 };
    },
  });
  assert.equal(retry.ok, true); assert.deepEqual(writes, ["updateScoreSummary", "updatePenaltySummary", "updateScoreSummary", "updatePenaltySummary"]);
});

test("T4 reread mismatch is a conflict, never a published result", async () => {
  const coordinator = createInMemoryLeaseCoordinator();
  const baseline = authoritative(); const lease = await coordinator.acquire({ gameId: "g-mismatch", operatorId: "op-a" });
  const result = await syncGame({}, "g-mismatch", { username: "H", scoreSummary: [{ id: "wanted" }], penaltySummary: [], ...lease, comparisonToken: baseline.comparisonToken }, {
    operatorId: "op-a", coordinator,
    authoritativeReader: async ({ phase }) => phase === "verifying" ? authoritative([{ id: "different" }], []) : baseline,
    writer: async () => ({ success: 1 }),
  });
  assert.equal(result.ok, false); assert.equal(result.conflict, true); assert.equal(result.phase, "verification");
  assert.equal(result.status, "conflict"); assert.equal(result.code, "verification_mismatch");
});
