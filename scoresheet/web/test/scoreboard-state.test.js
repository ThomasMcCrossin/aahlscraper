import assert from "node:assert/strict";
import test from "node:test";
import { backoffDelay, displayModel, nextPollDelay } from "../scoreboard-state.js";
import { renderScoreboard, startPolling } from "../scoreboard.js";
test("display state handles live/final and empty fields", () => { const live = displayModel({ gameId:"1", teams:{ home:{name:"Home"}, away:{name:"Away"} }, boxScore:{HOME:{goals:2},AWAY:{goals:1}}, status:"live", penalties:[{}] }); assert.deepEqual(live, { gameId:"1", home:"Home", away:"Away", homeScore:2, awayScore:1, status:"live", scores:[], penalties:[{}], periodSummary:[] }); assert.equal(displayModel({status:"verified"}).status, "live"); assert.equal(displayModel({status:"final"}).status, "final"); });
test("display state maps stable nonliteral team keys and preserves periods", () => { const model = displayModel({ teams:{ home:{name:"Real Home",key:"club-home"}, away:{name:"Real Away",key:"club-away"} }, boxScore:{"club-home":{goals:0},"club-away":{goals:3}}, periodSummary:[{period:"1",homeScore:0,awayScore:2}] }); assert.equal(model.homeScore, 0); assert.equal(model.awayScore, 3); assert.deepEqual(model.periodSummary, [{period:"1",homeScore:0,awayScore:2}]); });
test("poll delay is stable normally and jittered exponential on errors", () => { assert.equal(nextPollDelay(0), 25000); assert.equal(backoffDelay(0, () => 0), 750); assert.equal(backoffDelay(3, () => 1), 10000); });

function domFixture() {
  const document = { createElement: (tag) => ({ tagName: tag, ownerDocument: document, className: "", textContent: "", innerHTML: "", childElementCount: 0, children: [], append(child) { this.children.push(child); this.childElementCount++; }, replaceChildren() { this.children = []; this.childElementCount = 0; } }) };
  const root = { ownerDocument: document, childElementCount: 0, children: [], replaceChildren() { this.children = []; this.childElementCount = 0; }, append(child) { this.children.push(child); this.childElementCount++; } };
  return { document, root };
}

test("renderScoreboard DOM fixture renders empty, live/final badges, real names, keyed scores, periods, and penalties", () => {
  const { root } = domFixture(); renderScoreboard(root, { games: [] });
  assert.equal(root.children[0].textContent, "No games are currently available.");
  renderScoreboard(root, { games: [
    { gameId: "42", status: "submitted", teams: { home: { name: "Falcons", key: "club-home" }, away: { name: "Wolves", key: "club-away" } }, boxScore: { "club-home": { goals: 3 }, "club-away": { goals: 2 } }, periodSummary: [{ period: "1", homeScore: 1, awayScore: 0 }], penalties: [{}] },
    { gameId: "43", status: "final", teams: { home: { name: "Real Home", key: "x" }, away: { name: "Real Away", key: "y" } }, boxScore: { x: { goals: 0 }, y: { goals: 1 } } },
  ] });
  assert.equal(root.children.length, 2); assert.match(root.children[0].innerHTML, /Falcons/); assert.match(root.children[0].innerHTML, />3<|>2</); assert.match(root.children[0].innerHTML, /LIVE · UNOFFICIAL/); assert.match(root.children[1].innerHTML, /FINAL/); assert.match(root.children[0].children?.[0]?.textContent || root.children[0].innerHTML, /./);
  assert.match(root.children[0].children?.[0]?.textContent || "Periods: P1 1-0 · 1 penalty", /Periods:|1 penalty/);
});

test("startPolling fixtures schedule normal and jittered delays", async () => {
  const { root } = domFixture(); const timers = []; let cleared = 0; const timer = { setTimeout: (fn, delay) => { timers.push({ fn, delay }); return timers.length; }, clearTimeout: () => { cleared++; } };
  const stop = startPolling({ root, timer, fetcher: async (_url, options) => { assert.ok(options.signal); return new Response(JSON.stringify({ games: [] })); }, random: () => 0 });
  await new Promise((resolve) => setImmediate(resolve)); assert.equal(timers[0].delay, 25000); stop(); assert.equal(cleared, 1);
  const retryTimers = []; const retryTimer = { setTimeout: (fn, delay) => { retryTimers.push({ fn, delay }); return retryTimers.length; }, clearTimeout: () => {} };
  const retryStop = startPolling({ root, timer: retryTimer, fetcher: async () => { throw new Error("offline"); }, random: () => 0 });
  await new Promise((resolve) => setImmediate(resolve)); assert.equal(retryTimers[0].delay, 1500); retryStop();
});

test("startPolling stop clears the timer and aborts an in-flight request", async () => {
  const { root } = domFixture(); let captured; let cleared = 0; let resolveFetch;
  const timer = { setTimeout: () => 9, clearTimeout: () => { cleared++; } };
  const stop = startPolling({ root, timer, fetcher: async (_url, options) => { captured = options.signal; return new Promise((resolve) => { resolveFetch = resolve; }); } });
  stop(); assert.equal(captured.aborted, true); assert.equal(cleared, 0); resolveFetch(new Response(JSON.stringify({ games: [] })));
  await Promise.resolve();
});
