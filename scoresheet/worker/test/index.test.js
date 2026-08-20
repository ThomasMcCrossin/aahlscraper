import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { comparisonToken, gameSetup, parseAuthoritativeEvents } from "../src/index.js";

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
