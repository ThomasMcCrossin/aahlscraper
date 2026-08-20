// Browser-independent local state and synchronization primitives.

export function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
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
