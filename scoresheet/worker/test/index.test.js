import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import worker, { comparisonToken, constantTimeEqual, createInMemoryLeaseCoordinator, GameCodeRegistry, gameSetup, parseAuthoritativeEvents, syncGame } from "../src/index.js";

if (!globalThis.crypto) Object.defineProperty(globalThis, "crypto", { value: webcrypto });

const fixture = await readFile(new URL("./fixtures/game-editor.html", import.meta.url), "utf8");

function registryFixture() {
  const data = new Map();
  const storage = {
    get: async (key) => data.get(key),
    put: async (key, value) => data.set(key, value),
    delete: async (key) => data.delete(key),
    list: async ({ prefix } = {}) => new Map([...data].filter(([key]) => !prefix || key.startsWith(prefix))),
  };
  return { registry: new GameCodeRegistry({ storage }), data };
}
async function registryAction(registry, action, input) {
  const response = await registry.fetch(new Request(`https://registry.invalid/${action}`, { method: "POST", body: JSON.stringify(input) }));
  return response.json();
}

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
    assert.deepEqual(setup.current.goals, [{ period: "1", clock: "12:34", team: "HOME-DIV", scorer: "p-home-1", assists: [], scoreTotalText: "(1-0)" }]);
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

test("per-game registry mints plaintext once and stores only a keyed digest", async () => {
  const { registry, data } = registryFixture();
  const minted = await registryAction(registry, "mint", { gameId: "101", pepper: "fixture-pepper", ttlMs: 3600000 });
  assert.equal(minted.ok, true); assert.match(minted.code, /^[A-Z2-9]{8}$/);
  const stored = data.get("game:101");
  assert.equal(stored.code, undefined); assert.equal(stored.digest.length, 64);
  assert.equal((await registryAction(registry, "redeem", { code: minted.code, gameId: "101", pepper: "fixture-pepper" })).gameId, "101");
});

test("per-game registry enforces wrong game, expiry, revoke, reissue, and lockout", async () => {
  const { registry, data } = registryFixture();
  const first = await registryAction(registry, "mint", { gameId: "201", pepper: "p" });
  await registryAction(registry, "mint", { gameId: "202", pepper: "p" });
  assert.equal((await registryAction(registry, "redeem", { code: first.code, gameId: "202", requestSubject: "wrong-game", pepper: "p" })).reason, "wrong_game");
  await registryAction(registry, "revoke", { gameId: "201", pepper: "p" });
  assert.equal((await registryAction(registry, "redeem", { code: first.code, gameId: "201", requestSubject: "revoked", pepper: "p" })).reason, "code_revoked");
  const second = await registryAction(registry, "reissue", { gameId: "201", pepper: "p" });
  assert.equal((await registryAction(registry, "redeem", { code: first.code, gameId: "201", requestSubject: "reissued", pepper: "p" })).reason, "code_invalid");
  data.get("game:201").expiresAt = Date.now() - 1;
  assert.equal((await registryAction(registry, "redeem", { code: second.code, gameId: "201", requestSubject: "expired", pepper: "p" })).reason, "code_expired");
  const third = await registryAction(registry, "reissue", { gameId: "201", pepper: "p" });
  for (let i = 0; i < 4; i++) assert.equal((await registryAction(registry, "redeem", { code: "BADCODE1", gameId: "201", requestSubject: "brute", pepper: "p" })).reason, "code_invalid");
  assert.equal((await registryAction(registry, "redeem", { code: "BADCODE1", gameId: "201", requestSubject: "brute", pepper: "p" })).reason, "code_locked");
  assert.equal((await registryAction(registry, "redeem", { code: third.code, gameId: "201", requestSubject: "brute", pepper: "p" })).reason, "code_locked");
});

test("unknown list-entry guesses lock the peppered subject without storing client data or code", async () => {
  const { registry, data } = registryFixture();
  await registryAction(registry, "mint", { gameId: "250", pepper: "p" });
  for (let i = 0; i < 4; i++) assert.equal((await registryAction(registry, "redeem", { code: "UNKNOWN1", requestSubject: "peppered-subject", pepper: "p" })).reason, "code_invalid");
  assert.equal((await registryAction(registry, "redeem", { code: "UNKNOWN1", requestSubject: "peppered-subject", pepper: "p" })).reason, "code_locked");
  assert.equal((await registryAction(registry, "redeem", { code: (await registryAction(registry, "mint", { gameId: "251", pepper: "p" })).code, gameId: "251", requestSubject: "peppered-subject", pepper: "p" })).reason, "code_locked");
  const stored = [...data.values()];
  assert.equal(stored.some((value) => JSON.stringify(value).includes("UNKNOWN1")), false);
  assert.equal(stored.some((value) => JSON.stringify(value).includes("peppered-subject")), false);
  assert.equal([...data.keys()].some((key) => key.startsWith("subject:")), true);
});

test("rate-limit expiry and successful redemption clear the same subject state", async () => {
  const { registry, data } = registryFixture();
  const minted = await registryAction(registry, "mint", { gameId: "252", pepper: "p" });
  const input = { gameId: "252", requestSubject: "reset-subject", pepper: "p" };
  for (let i = 0; i < 5; i++) await registryAction(registry, "redeem", { ...input, code: "UNKNOWN1" });
  const subjectKey = "subject:reset-subject";
  assert.ok(data.get(subjectKey).lockedUntil > Date.now());
  data.get(subjectKey).lockedUntil = Date.now() - 1;
  assert.equal((await registryAction(registry, "redeem", { ...input, code: minted.code })).ok, true);
  assert.equal(data.has(subjectKey), false);
  assert.equal((await registryAction(registry, "redeem", { ...input, code: "UNKNOWN1" })).reason, "code_invalid");
  assert.equal(data.get(subjectKey).failures, 1);
  assert.equal((await registryAction(registry, "redeem", { ...input, code: minted.code })).ok, true);
  assert.equal(data.has(subjectKey), false);
});

test("constant-time digest helper compares fixed and mismatched lengths without coercion", () => {
  assert.equal(constantTimeEqual("abcd", "abcd"), true);
  assert.equal(constantTimeEqual("abcd", "abce"), false);
  assert.equal(constantTimeEqual("abcd", "abc"), false);
});

test("captain routes reject APP_TOKEN fallback and missing code before protected fetch", async () => {
  const restore = installNetworkTripwire();
  try {
    const response = await worker.fetch(new Request("https://worker.invalid/api/games", { headers: { Origin: "https://scores.invalid", "X-App-Token": "secret" } }), {
      APP_TOKEN: "secret", ALLOWED_ORIGIN: "https://scores.invalid", GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: { fetch: async () => { throw new Error("registry should not be called"); } },
    });
    assert.equal(response.status, 401); assert.equal((await response.json()).reason, "code_required");
  } finally { restore(); }
});

test("route lease uses redeemed subject, ignores X-Operator-Id, and reissue conflicts", async () => {
  const { registry, data } = registryFixture();
  const first = await registryAction(registry, "mint", { gameId: "401", pepper: "p" });
  const firstSubject = data.get("game:401").subject;
  const coordinator = createInMemoryLeaseCoordinator();
  const existing = await coordinator.acquire({ gameId: "401", operatorId: firstSubject });
  const env = { APP_TOKEN: "admin", ALLOWED_ORIGIN: "https://scores.invalid", GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: registry, LEASE_COORDINATOR: coordinator };
  const request = (code) => new Request("https://worker.invalid/api/games/401/lease", {
    method: "POST", headers: { Origin: "https://scores.invalid", "X-Game-Code": code, "X-Operator-Id": "caller-controlled" },
    body: JSON.stringify({ action: "renew", leaseId: existing.leaseId, ttlMs: 30000 }),
  });
  const owned = await worker.fetch(request(first.code), env);
  assert.equal(owned.status, 200, await owned.text());
  const second = await registryAction(registry, "reissue", { gameId: "401", pepper: "p" });
  const conflicted = await worker.fetch(request(second.code), env);
  assert.equal(conflicted.status, 409);
  assert.equal((await conflicted.json()).code, "lease_conflict");
});

test("unknown code guesses on /api/games reach a stable 429 lock without upstream", async () => {
  const restore = installNetworkTripwire();
  const { registry } = registryFixture();
  try {
    const env = { APP_TOKEN: "admin", ALLOWED_ORIGIN: "https://scores.invalid", GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: registry };
    const makeRequest = () => new Request("https://worker.invalid/api/games", { headers: { Origin: "https://scores.invalid", "X-Game-Code": "UNKNOWN1", "CF-Connecting-IP": "198.51.100.7" } });
    for (let i = 0; i < 4; i++) assert.equal((await worker.fetch(makeRequest(), env)).status, 401);
    const locked = await worker.fetch(makeRequest(), env);
    assert.equal(locked.status, 429);
    assert.equal((await locked.json()).reason, "code_locked");
  } finally { restore(); }
});

test("admin code actions are POST-only and preserve non-success status", async () => {
  const { registry } = registryFixture();
  const env = { APP_TOKEN: "admin", ALLOWED_ORIGIN: "https://scores.invalid", GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: registry };
  const get = await worker.fetch(new Request("https://worker.invalid/api/admin/game-codes/mint", { headers: { Origin: "https://scores.invalid", "X-App-Token": "admin" } }), env);
  assert.equal(get.status, 405);
  const invalid = await worker.fetch(new Request("https://worker.invalid/api/admin/game-codes/mint", { method: "POST", headers: { Origin: "https://scores.invalid", "X-App-Token": "admin", "Content-Type": "application/json" }, body: "{}" }), env);
  assert.equal(invalid.status, 400);
});

test("route configuration failures stop before registry, session, and protected work", async () => {
  const restore = installNetworkTripwire();
  let sessionCalls = 0;
  const request = new Request("https://worker.invalid/api/games/601/setup?div=TYLERARSENEAU-1&g2=2", {
    headers: { Origin: "https://scores.invalid", "X-Game-Code": "SYNTHETIC1" },
  });
  const base = { APP_TOKEN: "admin", ALLOWED_ORIGIN: "https://scores.invalid", SESSION: { get: async () => { sessionCalls++; return "fixture"; } } };
  try {
    for (const env of [
      { ...base },
      { ...base, GAME_CODE_PEPPER: "p" },
      { ...base, GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: {} },
    ]) {
      const response = await worker.fetch(request, env);
      assert.equal(response.status, 503);
      assert.equal((await response.json()).error, "configuration_error");
    }
    assert.equal(sessionCalls, 0);
  } finally { restore(); }
});

test("admin routes mint, revoke, and reissue through the HTTP contract", async () => {
  const { registry, data } = registryFixture();
  const env = { APP_TOKEN: "admin", ALLOWED_ORIGIN: "https://scores.invalid", GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: registry };
  const admin = (action, body) => worker.fetch(new Request(`https://worker.invalid/api/admin/game-codes/${action}`, {
    method: "POST", headers: { Origin: "https://scores.invalid", "X-App-Token": "admin", "Content-Type": "application/json" }, body: JSON.stringify(body),
  }), env);
  const captain = (code) => new Request("https://worker.invalid/api/games/602/setup?div=TYLERARSENEAU-1&g2=2", {
    headers: { Origin: "https://scores.invalid", "X-Game-Code": code },
  });
  const mintedResponse = await admin("mint", { gameId: "602" });
  assert.equal(mintedResponse.status, 200);
  const minted = await mintedResponse.json();
  assert.equal(minted.ok, true); assert.match(minted.code, /^[A-Z2-9]{8}$/);
  assert.equal(data.get("game:602").code, undefined);
  const revokedResponse = await admin("revoke", { gameId: "602" });
  assert.equal(revokedResponse.status, 200);
  const revoked = await worker.fetch(captain(minted.code), env);
  assert.equal(revoked.status, 401); assert.equal((await revoked.json()).reason, "code_revoked");
  const reissuedResponse = await admin("reissue", { gameId: "602" });
  assert.equal(reissuedResponse.status, 200);
  const reissued = await reissuedResponse.json();
  assert.equal(reissued.ok, true); assert.match(reissued.code, /^[A-Z2-9]{8}$/);
  assert.notEqual(reissued.code, minted.code);
  const oldCode = await worker.fetch(captain(minted.code), env);
  assert.equal(oldCode.status, 401); assert.equal((await oldCode.json()).reason, "code_invalid");
  assert.equal(data.get("game:602").code, undefined);
});

test("game-A code is rejected on game-B setup and sync before upstream work", async () => {
  const restore = installNetworkTripwire();
  const { registry } = registryFixture();
  const minted = await registryAction(registry, "mint", { gameId: "603", pepper: "p" });
  const env = { APP_TOKEN: "admin", ALLOWED_ORIGIN: "https://scores.invalid", GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: registry };
  try {
    const setup = await worker.fetch(new Request("https://worker.invalid/api/games/604/setup?div=TYLERARSENEAU-1&g2=2", {
      headers: { Origin: "https://scores.invalid", "X-Game-Code": minted.code },
    }), env);
    assert.equal(setup.status, 403); assert.equal((await setup.json()).reason, "wrong_game");
    const sync = await worker.fetch(new Request("https://worker.invalid/api/games/604/sync", {
      method: "POST", headers: { Origin: "https://scores.invalid", "X-Game-Code": minted.code, "Content-Type": "application/json" }, body: "{}",
    }), env);
    assert.equal(sync.status, 403); assert.equal((await sync.json()).reason, "wrong_game");
  } finally { restore(); }
});

test("invalid, expired, revoked, and locked route codes stop before protected work", async () => {
  const restore = installNetworkTripwire();
  const request = (gameId, code, method = "GET") => new Request(`https://worker.invalid/api/games/${gameId}/${method === "GET" ? "setup?div=TYLERARSENEAU-1&g2=2" : "sync"}`, {
    method, headers: { Origin: "https://scores.invalid", "X-Game-Code": code, "Content-Type": "application/json" }, body: method === "GET" ? undefined : "{}",
  });
  const envFor = (registry) => ({ APP_TOKEN: "admin", ALLOWED_ORIGIN: "https://scores.invalid", GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: registry });
  try {
    const invalidRegistry = registryFixture().registry;
    const invalid = await worker.fetch(request("605", "INVALID1"), envFor(invalidRegistry));
    assert.equal(invalid.status, 401); assert.equal((await invalid.json()).reason, "code_invalid");

    const expiredFixture = registryFixture();
    const expired = await registryAction(expiredFixture.registry, "mint", { gameId: "606", pepper: "p" });
    expiredFixture.data.get("game:606").expiresAt = Date.now() - 1;
    const expiredResponse = await worker.fetch(request("606", expired.code), envFor(expiredFixture.registry));
    assert.equal(expiredResponse.status, 401); assert.equal((await expiredResponse.json()).reason, "code_expired");

    const revokedFixture = registryFixture();
    const revoked = await registryAction(revokedFixture.registry, "mint", { gameId: "607", pepper: "p" });
    await registryAction(revokedFixture.registry, "revoke", { gameId: "607", pepper: "p" });
    const revokedResponse = await worker.fetch(request("607", revoked.code, "POST"), envFor(revokedFixture.registry));
    assert.equal(revokedResponse.status, 401); assert.equal((await revokedResponse.json()).reason, "code_revoked");

    const lockedFixture = registryFixture();
    const lockedEnv = envFor(lockedFixture.registry);
    for (let i = 0; i < 4; i++) assert.equal((await worker.fetch(request("608", "LOCKED1", "POST"), lockedEnv)).status, 401);
    const locked = await worker.fetch(request("608", "LOCKED1", "POST"), lockedEnv);
    assert.equal(locked.status, 429); assert.equal((await locked.json()).reason, "code_locked");
  } finally { restore(); }
});

test("redeemed code filters the games list to its exact game", async () => {
  const { registry } = registryFixture();
  const minted = await registryAction(registry, "mint", { gameId: "301", pepper: "p" });
  const html = "<tr><td>Amherst</td><td>ScoreClick('default.asp?p=ScoresEdit&a=1&sportsHQ=TYLERARSENEAU-1&gameID=301&gameID2=1', 10)</td></tr>" +
    "<tr><td>Springhill</td><td>ScoreClick('default.asp?p=ScoresEdit&a=1&sportsHQ=TYLERARSENEAU-2&gameID=302&gameID2=2', 20)</td></tr>";
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(html, { status: 200 });
  try {
    const response = await worker.fetch(new Request("https://worker.invalid/api/games", { headers: { Origin: "https://scores.invalid", "X-Game-Code": minted.code } }), {
      APP_TOKEN: "admin", ALLOWED_ORIGIN: "https://scores.invalid", GAME_CODE_PEPPER: "p", GAME_CODE_REGISTRY: registry, SESSION: { get: async () => "fixture" },
    });
    const listed = await response.json();
    assert.equal(response.status, 200, JSON.stringify(listed));
    assert.deepEqual(listed.map((game) => game.gameId), ["301"]);
  } finally { globalThis.fetch = originalFetch; }
});

test("Blocker 6 regression: missing token/origin and forbidden Origin fail before protected work", async () => {
  const protectedRequest = new Request("https://worker.invalid/api/unknown", { headers: { Origin: "https://scores.invalid", "X-App-Token": "secret" } });
  let response = await worker.fetch(protectedRequest, {});
  assert.equal(response.status, 503);
  response = await worker.fetch(protectedRequest, { APP_TOKEN: "secret", ALLOWED_ORIGIN: "https://scores.invalid" });
  assert.equal(response.status, 404); // route is reached only after both gates
  response = await worker.fetch(new Request(protectedRequest, { headers: { Origin: "https://scores.invalid", "X-App-Token": "wrong" } }), { APP_TOKEN: "secret", ALLOWED_ORIGIN: "https://scores.invalid" });
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error, "unauthorized");
  response = await worker.fetch(new Request(protectedRequest, { headers: { Origin: "https://other.invalid", "X-App-Token": "secret" } }), { APP_TOKEN: "secret", ALLOWED_ORIGIN: "https://scores.invalid" });
  assert.equal(response.status, 403);
  assert.equal((await response.json()).error, "origin_not_allowed");
});

test("health is minimal and never uses wildcard CORS", async () => {
  const response = await worker.fetch(new Request("https://worker.invalid/api/health"), {});
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { ok: true });
  assert.equal(response.headers.get("Access-Control-Allow-Origin"), null);
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

test("Blocker 7/8 regression: season drift blocks sync and fixture preserves HTO running-score orientation", async () => {
  assert.equal(parseAuthoritativeEvents(fixture).goals[0].scoreTotalText, "(1-0)");
  const coordinator = createInMemoryLeaseCoordinator();
  const baseline = authoritative(); const lease = await coordinator.acquire({ gameId: "g-drift", operatorId: "op-a" });
  let writes = 0;
  const result = await syncGame({ SEASON_MAP_ID: "season-current" }, "g-drift", {
    username: "H", seasonMapId: "season-old", scoreSummary: [], penaltySummary: [], ...lease, comparisonToken: baseline.comparisonToken,
  }, { operatorId: "op-a", coordinator, authoritativeReader: async () => ({ ...baseline, seasonMapId: "season-current" }), writer: async () => { writes += 1; } });
  assert.equal(result.code, "season_map_drift");
  assert.equal(writes, 0);
});
