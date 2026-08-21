import assert from "node:assert/strict";
import test from "node:test";
import { backoffDelay, displayModel, nextPollDelay } from "../scoreboard-state.js";
test("display state handles live/final and empty fields", () => { const live = displayModel({ gameId:"1", teams:{ home:{name:"Home"}, away:{name:"Away"} }, boxScore:{HOME:{goals:2},AWAY:{goals:1}}, status:"live", penalties:[{}] }); assert.deepEqual(live, { gameId:"1", home:"Home", away:"Away", homeScore:2, awayScore:1, status:"live", scores:[], penalties:[{}] }); assert.equal(displayModel({status:"verified"}).status, "live"); assert.equal(displayModel({status:"final"}).status, "final"); });
test("poll delay is stable normally and jittered exponential on errors", () => { assert.equal(nextPollDelay(0), 25000); assert.equal(backoffDelay(0, () => 0), 750); assert.equal(backoffDelay(3, () => 1), 10000); });
