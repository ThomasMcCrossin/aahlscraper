// Browser-independent local state and synchronization primitives.

export function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

const PERIODS = new Set(["1", "2", "3", "OT", "2OT", "SO"]);
const PERIOD_LIMITS = { "1": 20, "2": 20, "3": 20, OT: 5, "2OT": 5, SO: 0 };

function roster(setup, team) {
  const side = setup && (setup.homeDiv === team || setup.home?.div === team ? setup.home : setup.awayDiv === team || setup.away?.div === team ? setup.away : null);
  return (side && side.players) || [];
}
function playerIds(setup, team) { return new Set(roster(setup, team).map((p) => String(p.id))); }
function clockError(period, value, label) {
  if (!/^\d{1,2}:[0-5]\d$/.test(String(value || ""))) return `${label} must use mm:ss`;
  const [minutes, seconds] = String(value).split(":").map(Number);
  if (minutes > PERIOD_LIMITS[period] || (minutes === PERIOD_LIMITS[period] && seconds > 0)) return `${label} is outside the period bounds`;
  return null;
}
function required(value, label) { return value == null || String(value).trim() === "" ? `${label} is required` : null; }

export function validateGoal(goal, setup) {
  const errors = [];
  if (!PERIODS.has(String(goal.period))) errors.push("period is invalid");
  const clock = clockError(String(goal.period), goal.scoreTime ?? goal.clock, "goal clock"); if (clock) errors.push(clock);
  const strengthError = required(goal.strength, "goal strength"); if (strengthError) errors.push(strengthError);
  const ids = playerIds(setup, goal.scoreTeam ?? goal.team);
  if (!ids.size) errors.push("goal team is not a selected roster");
  for (const [value, label] of [[goal.scorer, "scorer"]]) { const e = required(value, label); if (e) errors.push(e); else if (!ids.has(String(value))) errors.push(`${label} is not on the selected team's roster`); }
  const assists = [goal.assists1, goal.assists2, ...(Array.isArray(goal.assists) ? goal.assists : [])].filter(Boolean).map(String);
  if (new Set(assists).size !== assists.length) errors.push("assists must be unique");
  if (assists.includes(String(goal.scorer))) errors.push("scorer cannot also be an assist");
  if (assists.some((id) => !ids.has(id))) errors.push("assist is not on the selected team's roster");
  return { valid: errors.length === 0, errors };
}

export function validatePenalty(penalty, setup) {
  const errors = [];
  if (!PERIODS.has(String(penalty.period))) errors.push("period is invalid");
  const clock = clockError(String(penalty.period), penalty.penaltyTime ?? penalty.clock, "penalty clock"); if (clock) errors.push(clock);
  const team = penalty.penaltyTeam ?? penalty.team; const ids = playerIds(setup, team);
  if (!ids.size) errors.push("penalty team is not a selected roster");
  for (const [value, label] of [[penalty.penaltyPlayer ?? penalty.player, "penalty player"], [penalty.servedPlayer ?? penalty.servedBy, "served-by player"]]) {
    const e = required(value, label); if (e) errors.push(e); else if (!ids.has(String(value))) errors.push(`${label} is not on the selected team's roster`);
  }
  const inf = (setup && setup.infractions || []).find((x) => x.code === penalty.infraction);
  const severity = penalty.severity || inf?.severity;
  const minutes = Number(penalty.penaltyLength ?? penalty.minutes);
  if (!inf) errors.push("infraction is required and must be known");
  if (!Number.isFinite(minutes) || minutes <= 0) errors.push("penalty duration is required");
  // AAHL fixtures include both standard and shortened-game minor lengths;
  // severity constrains the permitted set without inventing one season rule.
  const allowed = { minor: [2, 3, 4], major: [5], misconduct: [10], match: [10] }[severity];
  if (allowed && !allowed.includes(minutes)) errors.push("penalty duration does not match severity");
  return { valid: errors.length === 0, errors };
}

export function validateEvents(state) {
  const errors = [];
  const goals = state.scoreSummary || [], penalties = state.penaltySummary || [];
  goals.forEach((event, i) => { const r = validateGoal(event, state.setup); if (!r.valid) errors.push(...r.errors.map((e) => `goal ${i + 1}: ${e}`)); });
  penalties.forEach((event, i) => { const r = validatePenalty(event, state.setup); if (!r.valid) errors.push(...r.errors.map((e) => `penalty ${i + 1}: ${e}`)); });
  const seen = new Set();
  for (const [kind, events] of [["goal", goals], ["penalty", penalties]]) for (const event of events) {
    const key = JSON.stringify({ kind, ...event, scoreTotalText: undefined });
    if (seen.has(key)) errors.push(`duplicate ${kind} event`); else seen.add(key);
  }
  return { valid: errors.length === 0, errors };
}

export function confirmGameIdentity(displayed, confirmation) {
  const fields = ["gameId", "date", "time", "rink", "away", "home"];
  return !!confirmation && fields.every((field) => String(displayed?.[field] ?? "") === String(confirmation[field] ?? "")) && confirmation.confirmed === true;
}

export function deleteEvent(state, kind, index, now = Date.now(), undoMs = 8000) {
  const key = kind === "goal" ? "scoreSummary" : kind === "penalty" ? "penaltySummary" : null;
  if (!key || !Number.isInteger(index) || !state[key][index]) throw new Error("event not found");
  const event = state[key].splice(index, 1)[0];
  state.revision += 1; state.dirty = true; state.syncStatus = "pending"; state.syncPhase = "pending";
  state.undo = { kind, index, event: clone(event), expiresAt: now + undoMs };
  return state;
}
export function undoDeletion(state, now = Date.now()) {
  if (!state.undo || now > state.undo.expiresAt) throw new Error("undo window expired");
  const { kind, index, event } = state.undo; const key = kind === "goal" ? "scoreSummary" : "penaltySummary";
  state[key].splice(Math.min(index, state[key].length), 0, clone(event)); state.undo = null;
  state.revision += 1; state.dirty = true; state.syncStatus = "pending"; state.syncPhase = "pending"; return state;
}

export function editEvent(state, kind, index, event) {
  const key = kind === "goal" ? "scoreSummary" : kind === "penalty" ? "penaltySummary" : null;
  if (!key || !state[key][index]) throw new Error("event not found");
  const result = kind === "goal" ? validateGoal(event, state.setup) : validatePenalty(event, state.setup);
  if (!result.valid) throw new Error(result.errors.join("; "));
  state[key][index] = clone(event); state.revision += 1; state.dirty = true; state.syncStatus = "pending"; state.syncPhase = "pending"; return state;
}

const RECOVERY_VERSION = 1;
export function exportRecovery(state) {
  return JSON.stringify({ format: "aahl-scoresheet-recovery", version: RECOVERY_VERSION, identity: clone(state.gameIdentity || state), gameId: state.gameId, revision: state.revision, scoreSummary: clone(state.scoreSummary), penaltySummary: clone(state.penaltySummary) }, null, 2);
}
export function importRecovery(state, serialized, expectedIdentity) {
  let data; try { data = typeof serialized === "string" ? JSON.parse(serialized) : serialized; } catch { throw new Error("recovery JSON is invalid"); }
  if (data?.format !== "aahl-scoresheet-recovery" || data.version !== RECOVERY_VERSION) throw new Error("unsupported recovery format");
  if (!Array.isArray(data.scoreSummary) || !Array.isArray(data.penaltySummary)) throw new Error("recovery event arrays are invalid");
  if (String(data.gameId) !== String(state.gameId) || !confirmGameIdentity(expectedIdentity, { ...data.identity, confirmed: true })) throw new Error("recovery belongs to a different exact game");
  if (Number(data.revision) <= Number(state.revision)) throw new Error("recovery cannot replace newer or equal state");
  const next = { ...state, scoreSummary: clone(data.scoreSummary), penaltySummary: clone(data.penaltySummary), revision: Number(data.revision), dirty: true, syncStatus: "pending", syncPhase: "pending" };
  const result = validateEvents(next); if (!result.valid) throw new Error(result.errors.join("; ")); return next;
}

export function createGameState(game, setup = {}) {
  return {
    ...clone(game),
    gameId: game.gameId,
    scoreSummary: [],
    penaltySummary: [],
    revision: 0,
    syncedRevision: 0,
    dirty: false,
    syncStatus: "offline",
    syncPhase: null,
    syncError: null,
    remoteBaseline: null,
    resume: { required: true, confirmed: false },
    setup: clone(setup),
    gameIdentity: { gameId: game.gameId, date: game.date ?? game.gameDate ?? "", time: game.time ?? game.startTime ?? "", rink: game.location ?? game.rink ?? "", away: game.away ?? "", home: game.home ?? "" },
    undo: null,
  };
}

export function resumeGame(state, remote, confirmation = {}) {
  if (!remote || !Array.isArray(remote.goals) || !Array.isArray(remote.penalties)) {
    throw new Error("authoritative remote event arrays are required");
  }
  if (confirmation.gameId !== state.gameId || confirmation.confirmed !== true) {
    throw new Error("exact-game resume/import confirmation required");
  }
  if (!remote.comparisonToken) throw new Error("authoritative comparison token is required");
  state.scoreSummary = clone(remote.goals);
  state.penaltySummary = clone(remote.penalties);
  state.remoteBaseline = {
    goals: clone(remote.goals), penalties: clone(remote.penalties),
    comparisonToken: remote.comparisonToken,
  };
  state.resume = { required: false, confirmed: true };
  state.revision = 0;
  state.syncedRevision = 0;
  state.dirty = false;
  state.syncStatus = "published";
  state.syncPhase = "published";
  return state;
}

export function captureEvent(state, kind, event) {
  if (!state.resume || state.resume.confirmed !== true || !state.remoteBaseline) {
    throw new Error("resume/import confirmation is required before capture");
  }
  const key = kind === "goal" ? "scoreSummary" : kind === "penalty" ? "penaltySummary" : null;
  if (!key) throw new Error("event kind must be goal or penalty");
  state[key].push(clone(event));
  state.revision += 1;
  state.dirty = true;
  state.syncStatus = "pending";
  state.syncPhase = "pending";
  state.syncError = null;
  return state;
}

export function syncPayload(state) {
  if (!state.remoteBaseline) throw new Error("authoritative baseline is required");
  return {
    gameId: state.gameId, revision: state.revision,
    comparisonToken: state.remoteBaseline.comparisonToken,
    scoreSummary: clone(state.scoreSummary), penaltySummary: clone(state.penaltySummary),
  };
}

// One queue instance belongs to exactly one game. A later enqueue replaces the
// pending payload, while the in-flight payload remains immutable.
export function createSyncQueue({ send, persist = () => {}, isOnline = () => true }) {
  let inFlight = false;
  let pending = null;
  let latestRevision = 0;

  async function drain() {
    if (inFlight || !pending || !isOnline()) return;
    const item = pending;
    pending = null;
    inFlight = true;
    try {
      const result = await send(item.payload);
      if (item.state.revision === item.payload.revision && item.payload.revision >= latestRevision) {
        if (result && result.ok === false) {
          item.state.dirty = true;
          item.state.syncStatus = result.status || (result.conflict ? "conflict" : "error");
          item.state.syncPhase = result.phase || null;
          item.state.syncError = result.message || result.error || "publication failed";
        } else {
          item.state.syncedRevision = item.payload.revision;
          item.state.dirty = false;
          item.state.syncStatus = result && result.status || "published";
          item.state.syncPhase = result && result.phase || "published";
          item.state.syncError = null;
        }
      } else {
        item.state.dirty = true;
        item.state.syncStatus = "pending";
        item.state.syncPhase = "pending";
      }
    } catch (error) {
      item.state.dirty = true;
      item.state.syncStatus = error.status || "error";
      item.state.syncPhase = error.phase || null;
      item.state.syncError = error.message;
      if (error.comparisonToken && item.state.remoteBaseline) {
        item.state.remoteBaseline.comparisonToken = error.comparisonToken;
      }
    } finally {
      inFlight = false;
      // The browser reloads persisted state for each edit, so a queued edit may
      // be a newer object than the in-flight snapshot. Never let the older
      // completion overwrite that durable state, even momentarily.
      const hasNewerPending = pending && pending.payload.revision > item.payload.revision;
      if (!hasNewerPending) persist(item.state);
      if (pending && isOnline()) void drain();
    }
  }
  return {
    enqueue(state) {
      latestRevision = Math.max(latestRevision, state.revision);
      state.dirty = true;
      state.syncStatus = "pending";
      pending = { state, payload: syncPayload(state) };
      persist(state);
      void drain();
    },
    reconnect() { void drain(); },
    get inFlight() { return inFlight; },
    get pendingRevision() { return pending && pending.payload.revision; },
  };
}
