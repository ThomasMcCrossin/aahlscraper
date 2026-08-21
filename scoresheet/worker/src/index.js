/**
 * AAHL Live Scoresheet — auth proxy + API (Cloudflare Worker)
 *
 * Holds the HomeTeamsOnline league login server-side (never on the tablet) and
 * exposes a small JSON API the PWA uses to list games, load rosters, and push
 * the live scoring/penalty summary back into HomeTeamsOnline.
 *
 * All writes use HomeTeamsOnline's own AJAX endpoint with REPLACE semantics:
 * the array we POST IS the full summary for that game. That makes every sync
 * idempotent — the PWA holds the complete event list locally and re-POSTs the
 * whole array, so retries (after flaky rink wifi) can never double-count.
 *
 * Administrator code-management endpoints require `X-App-Token`; captain
 * endpoints require `X-Game-Code` bound to the exact game.
 *   GET  /api/games                         -> [{gameId, gameId2, homeDiv, awayDiv, home, away, location, startMs}]
 *   GET  /api/games/:gameId/setup?div=&g2=  -> {home, away, infractions, current}
 *   POST /api/games/:gameId/lease           -> acquire/renew/release a game lease
 *   POST /api/games/:gameId/sync            -> compare-and-replace summaries
 *   GET  /api/health                        -> {ok}
 *
 * Bindings (wrangler.toml):
 *   KV  SESSION              - stores the HTO session cookie
 *   var ALLOWED_ORIGIN       - the PWA origin for CORS (e.g. https://aahl-scoresheet.pages.dev)
 *   secret HTO_USERNAME      - league login email
 *   secret HTO_PASSWORD      - league login password
 *   secret APP_TOKEN         - administrator shared secret
 *   secret GAME_CODE_PEPPER  - keyed digest pepper for per-game codes
 */

const HTO = "https://www.hometeamsonline.com";
const LOGIN_URL = `${HTO}/sportswebsites/ajax/Login.asp?p=login&username=DSMALL`;
const LOGIN_PAGE = `${HTO}/sportswebsites/default.asp?p=login&username=DSMALL`;
const SCORESEDIT_AJAX = `${HTO}/admin/ajax/scoresedit.asp`;
// The schedule page is client-rendered; games come from this AJAX call.
const SCHEDULE_AJAX = `${HTO}/admin/ajax/Schedule.asp?p=schedule`;
const SESSION_KEY = "hto_session_cookie";

// League division-id -> display name. AAHL Winter 2025/2026 (update each season).
const TEAMS = {
  "TYLERARSENEAU-1": "Maltby Sports",
  "TYLERARSENEAU-2": "Ultramar",
  "TYLERARSENEAU-3": "Colson Overhead Doors",
  "TYLERARSENEAU-4": "J&K Electric",
  "983723": "G.R. Mitchell Welding",
};
const LOCATIONS = ["Amherst", "Springhill"];
const DEFAULT_SEASON_MAP_ID = "AAHL-WINTER-2025-2026";

// ---------------------------------------------------------------------------
// Worker entry
// ---------------------------------------------------------------------------
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin");
    // The public display is deliberately independent of the captain/admin
    // origin gate. It is read-only and returns only projected canonical data.
    if (url.pathname.startsWith("/api/public/")) {
      const publicHeaders = { ...publicCors(), "Cache-Control": "public, max-age=20, s-maxage=20" };
      if (request.method !== "GET") return json({ ok: false, error: "method_not_allowed" }, 405, publicHeaders);
      if (url.pathname === "/api/public/scoreboard" || /^\/api\/public\/games\/[^/]+\/boxscore$/.test(url.pathname)) {
        try {
          const result = await publicRoute(env, url);
          return json(result.body, result.status, publicHeaders);
        } catch {
          return json({ ok: false, error: "public_service_unavailable" }, 503, publicHeaders);
        }
      }
      return json({ ok: false, error: "not_found" }, 404, publicHeaders);
    }
    const configured = configuration(env);
    const cors = configured.ok && origin === configured.origin ? corsHeaders(configured.origin) : {};

    // Health is intentionally minimal and does not open the protected API.
    if (url.pathname === "/api/health" && request.method === "GET") return json({ ok: true }, 200, cors);
    // Preflight is protected too: never emit wildcard CORS or process a
    // request when deployment configuration or the exact origin is absent.
    if (!configured.ok) return json({ ok: false, error: "configuration_error" }, 503);
    if (origin !== configured.origin) return json({ ok: false, error: "origin_not_allowed" }, 403);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });

    try {
      const admin = url.pathname.startsWith("/api/admin/game-codes/") || url.pathname.startsWith("/api/admin/game-records/");
      if (admin && request.headers.get("X-App-Token") !== configured.token)
        return json({ ok: false, error: "unauthorized" }, url.pathname.startsWith("/api/admin/game-records/") ? 403 : 401, cors);
      if (url.pathname.startsWith("/api/admin/game-records/")) {
        const result = await adminGameRecordRoute(env, url, request);
        return json(result.body, result.status, cors);
      }
      if (admin) {
        const result = await adminCodeRoute(env, url, request);
        return json(result.body, result.status, cors);
      }

      const protectedRoute = url.pathname === "/api/games" || /^\/api\/games\/\d+\/(setup|lease|sync)$/.test(url.pathname);
      if (!protectedRoute) {
        if (request.headers.get("X-App-Token") !== configured.token)
          return json({ ok: false, error: "unauthorized" }, 401, cors);
        return json({ ok: false, error: "not found" }, 404, cors);
      }
      const captain = await captainAuthorization(env, request, url);
      if (!captain.ok) return json(captain.body, captain.status, cors);

      if (url.pathname === "/api/games" && request.method === "GET") {
        const games = await listGames(env);
        return json(games.filter((game) => String(game.gameId) === captain.gameId), 200, cors);
      }

      const setup = url.pathname.match(/^\/api\/games\/(\d+)\/setup$/);
      if (setup && request.method === "GET") {
        if (setup[1] !== captain.gameId) return json(codeError("wrong_game"), 403, cors);
        const div = url.searchParams.get("div");
        const g2 = url.searchParams.get("g2") || "";
        return json(await gameSetup(env, setup[1], div, g2), 200, cors);
      }

      const lease = url.pathname.match(/^\/api\/games\/(\d+)\/lease$/);
      if (lease && request.method === "POST") {
        if (lease[1] !== captain.gameId) return json(codeError("wrong_game"), 403, cors);
        const operatorId = captain.operatorId;
        if (!operatorId) return json(conflict("identity_required", "operator identity is required"), 409, cors);
        const body = await request.json();
        const result = await leaseAction(env, lease[1], body, operatorId);
        return json(result, result.ok ? 200 : 409, cors);
      }

      const sync = url.pathname.match(/^\/api\/games\/(\d+)\/sync$/);
      if (sync && request.method === "POST") {
        if (sync[1] !== captain.gameId) return json(codeError("wrong_game"), 403, cors);
        const body = await request.json();
        const operatorId = captain.operatorId;
        if (!operatorId) return json(conflict("identity_required", "operator identity is required"), 409, cors);
        const result = await syncGame(env, sync[1], body, { operatorId });
        return json(result, result.conflict ? 409 : 200, cors);
      }

      return json({ ok: false, error: "not found" }, 404, cors);
    } catch (err) {
      return json({ ok: false, error: String((err && err.message) || err) }, 500, cors);
    }
  },
};

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------
const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const CODE_LENGTH = 8;
const CODE_MIN_TTL = 5 * 60 * 1000;
const CODE_MAX_TTL = 24 * 60 * 60 * 1000;
const CODE_DEFAULT_TTL = 6 * 60 * 60 * 1000;
const MAX_FAILED_ATTEMPTS = 5;
const LOCKOUT_MS = 10 * 60 * 1000;

function codeError(reason) {
  const messages = { code_required: "game code is required", code_invalid: "game code is invalid", code_expired: "game code has expired", code_revoked: "game code has been revoked", wrong_game: "game code is bound to another game", code_locked: "game code attempts are locked" };
  return { ok: false, error: reason, reason, message: messages[reason] || "game code is not authorized" };
}
function normalizeCode(value) { return String(value || "").toUpperCase().replace(/[-\s]/g, ""); }
function boundedTtl(value) { return Math.min(Math.max(Number(value) || CODE_DEFAULT_TTL, CODE_MIN_TTL), CODE_MAX_TTL); }
function randomCode() {
  const bytes = new Uint8Array(CODE_LENGTH); crypto.getRandomValues(bytes);
  return [...bytes].map((b) => CODE_ALPHABET[b % CODE_ALPHABET.length]).join("");
}
async function keyedDigest(code, pepper) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(String(pepper)), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const digest = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(normalizeCode(code)));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}
export function constantTimeEqual(left, right) {
  const a = String(left || ""), b = String(right || ""); let different = a.length ^ b.length;
  const length = Math.max(a.length, b.length);
  for (let i = 0; i < length; i++) different |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return different === 0;
}
function codeRegistry(env) {
  if (env.GAME_CODE_REGISTRY && typeof env.GAME_CODE_REGISTRY.fetch === "function") return env.GAME_CODE_REGISTRY;
  if (env.GAME_CODE_REGISTRY && typeof env.GAME_CODE_REGISTRY.idFromName === "function") return env.GAME_CODE_REGISTRY.get(env.GAME_CODE_REGISTRY.idFromName("registry"));
  return { fetch: async () => new Response(JSON.stringify(codeError("code_invalid")), { status: 503 }) };
}
async function registryCall(env, path, body) {
  const response = await codeRegistry(env).fetch(new Request(`https://game-code${path}`, { method: "POST", body: JSON.stringify(body) }));
  return response.json();
}
async function adminCodeRoute(env, url, request) {
  if (!env.GAME_CODE_PEPPER || !env.GAME_CODE_REGISTRY) return { body: codeError("configuration_error"), status: 503 };
  if (request.method !== "POST") return { body: { ok: false, error: "method_not_allowed" }, status: 405 };
  const body = await request.json();
  const gameId = String(body.gameId || "");
  if (!gameId) return { body: { ok: false, error: "invalid_request", message: "gameId is required" }, status: 400 };
  const action = url.pathname.split("/").pop();
  if (action !== "mint" && action !== "reissue" && action !== "revoke") return { body: { ok: false, error: "not_found" }, status: 404 };
  const result = action === "revoke"
    ? await registryCall(env, "/revoke", { gameId, pepper: env.GAME_CODE_PEPPER })
    : await registryCall(env, `/${action}`, { gameId, ttlMs: boundedTtl(body.ttlMs), pepper: env.GAME_CODE_PEPPER });
  return { body: result, status: result.ok ? 200 : 400 };
}

function gameRecords(env) {
  if (env.GAME_RECORDS && typeof env.GAME_RECORDS.fetch === "function") return env.GAME_RECORDS;
  if (env.GAME_RECORDS && typeof env.GAME_RECORDS.idFromName === "function") {
    return { fetch: (request) => env.GAME_RECORDS.get(env.GAME_RECORDS.idFromName(new URL(request.url).pathname.split("/").pop())).fetch(request) };
  }
  return null;
}

async function adminGameRecordRoute(env, url, request) {
  if (request.method !== "GET") return { body: { ok: false, error: "method_not_allowed" }, status: 405 };
  const match = url.pathname.match(/^\/api\/admin\/game-records\/([^/]+)$/);
  if (!match) return { body: { ok: false, error: "not_found" }, status: 404 };
  const namespace = gameRecords(env);
  if (!namespace) return { body: { ok: false, error: "configuration_error" }, status: 503 };
  const gameId = decodeURIComponent(match[1]);
  const response = await namespace.fetch(new Request(`https://game-record/${encodeURIComponent(gameId)}`, { method: "GET" }));
  return { body: await response.json(), status: response.status };
}
async function rateLimitSubject(request, pepper) {
  const forwarded = request.headers.get("CF-Connecting-IP") || "anonymous";
  return keyedDigest(`request-subject:${forwarded.split(",")[0].trim()}`, pepper);
}
async function captainAuthorization(env, request, url) {
  if (!env.GAME_CODE_PEPPER || !env.GAME_CODE_REGISTRY || (typeof env.GAME_CODE_REGISTRY.fetch !== "function" && typeof env.GAME_CODE_REGISTRY.idFromName !== "function")) return { ok: false, status: 503, body: codeError("configuration_error") };
  const supplied = request.headers.get("X-Game-Code");
  if (!supplied) return { ok: false, status: 401, body: codeError("code_required") };
  const expectedGame = url.pathname.match(/^\/api\/games\/(\d+)\//)?.[1] || null;
  const result = await registryCall(env, "/redeem", { code: supplied, gameId: expectedGame, requestSubject: await rateLimitSubject(request, env.GAME_CODE_PEPPER), pepper: env.GAME_CODE_PEPPER });
  if (!result.ok) return { ok: false, status: result.reason === "code_locked" ? 429 : result.reason === "wrong_game" ? 403 : 401, body: codeError(result.reason || "code_invalid") };
  return { ok: true, gameId: String(result.gameId), operatorId: await operatorFromSubject(result.subject, env) };
}
function operatorFromSubject(subject, env) {
  if (typeof env.IDENTITY_ADAPTER === "function") return env.IDENTITY_ADAPTER(new Request("https://identity.invalid", { headers: { "X-Operator-Id": subject } }), env);
  return subject;
}

/** Serialized registry: plaintext is returned only by mint/reissue and never stored. */
export class GameCodeRegistry {
  constructor(state) { this.state = state; }
  async fetch(request) {
    const action = new URL(request.url).pathname.slice(1); const input = await request.json();
    const now = Date.now(); const key = `game:${String(input.gameId || "")}`;
    let record = await this.state.storage.get(key);
    if (action === "mint" || action === "reissue") {
      const code = randomCode(); const next = { gameId: String(input.gameId), digest: await keyedDigest(code, input.pepper), subject: crypto.randomUUID(), expiresAt: now + boundedTtl(input.ttlMs), revoked: false, failures: 0, lockedUntil: 0 };
      await this.state.storage.put(key, next); return this.response({ ok: true, gameId: next.gameId, code, expiresAt: next.expiresAt });
    }
    if (action === "revoke") {
      if (record) await this.state.storage.put(key, { ...record, revoked: true });
      return this.response({ ok: true, revoked: true, gameId: String(input.gameId) });
    }
    if (action === "redeem") {
      const subjectKey = `subject:${String(input.requestSubject || "fixture-subject")}`;
      let attempt = await this.state.storage.get(subjectKey);
      if (attempt?.lockedUntil > now) return this.response(codeError("code_locked"), 429);
      if (attempt?.lockedUntil && attempt.lockedUntil <= now) attempt = null;
      const digest = await keyedDigest(input.code, input.pepper);
      if (!record && typeof this.state.storage.list === "function") {
        const all = await this.state.storage.list({ prefix: "game:" });
        for (const candidate of all.values()) if (constantTimeEqual(digest, candidate.digest)) { record = candidate; break; }
      } else if (record && !constantTimeEqual(digest, record.digest) && typeof this.state.storage.list === "function") {
        const all = await this.state.storage.list({ prefix: "game:" });
        for (const candidate of all.values()) if (constantTimeEqual(digest, candidate.digest)) { record = candidate; break; }
      }
      const fail = async (reason) => {
        const failures = (attempt?.failures || 0) + 1;
        const lockedUntil = failures >= MAX_FAILED_ATTEMPTS ? now + LOCKOUT_MS : 0;
        await this.state.storage.put(subjectKey, { failures, lockedUntil, expiresAt: now + LOCKOUT_MS });
        return this.response(codeError(lockedUntil ? "code_locked" : reason), lockedUntil ? 429 : 401);
      };
      if (!record) return fail("code_invalid");
      if (record.revoked) return fail("code_revoked");
      if (record.expiresAt <= now) return fail("code_expired");
      if (!constantTimeEqual(digest, record.digest)) {
        return fail("code_invalid");
      }
      if (input.gameId && String(input.gameId) !== record.gameId) return fail("wrong_game");
      await this.state.storage.delete(subjectKey);
      return this.response({ ok: true, gameId: record.gameId, subject: record.subject });
    }
    return this.response({ ok: false, error: "not found" });
  }
  response(value, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }); }
}

/** One strongly-consistent, append-only canonical revision log per game. */
export class GameRecord {
  constructor(state) { this.state = state; }
  async fetch(request) {
    const url = new URL(request.url);
    const input = request.method === "GET" ? {} : await request.json();
    if ((request.method === "GET" && url.pathname !== "/index") || url.pathname === "/read") {
      const revisions = await this.revisions();
      return this.response({ ok: true, gameId: input.gameId || url.pathname.slice(1), latest: revisions.at(-1) || null, revisions });
    }
    if (url.pathname === "/append") {
      const append = async (storage) => {
        const next = Number(await storage.get("nextRevision") || 0) + 1;
        const revision = {
          gameId: String(input.gameId || ""),
          scoreSummary: input.scoreSummary,
          penaltySummary: input.penaltySummary,
          boxScore: input.boxScore,
          displayTeams: sanitizeDisplayTeams(input.displayTeams),
          periodSummary: input.periodSummary,
          seasonMapId: input.seasonMapId,
          subject: input.subject,
          submittedAt: input.submittedAt,
          status: "submitted",
          revision: next,
        };
        await storage.put(`revision:${next}`, revision);
        await storage.put("nextRevision", next);
        return revision;
      };
      const revision = typeof this.state.storage.transaction === "function"
        ? await this.state.storage.transaction(append)
        : await append(this.state.storage);
      return this.response({ ok: true, revision });
    }
    if (url.pathname === "/index-update") {
      const gameId = String(input.gameId || "");
      const next = {
        gameId,
        seasonMapId: input.seasonMapId,
        displayTeams: input.displayTeams,
        updatedAt: input.updatedAt || new Date().toISOString(),
        revision: Number(input.revision),
      };
      const update = async (storage) => {
        const index = (await storage.get("publicIndex")) || { entries: [] };
        const entries = Array.isArray(index.entries) ? index.entries.slice() : [];
        const position = entries.findIndex((entry) => String(entry.gameId) === gameId);
        const current = position >= 0 ? entries[position] : null;
        // Append/update only: never remove an entry or move it backwards.
        if (current && next.revision < Number(current.revision || 0)) return { ok: true, entry: current };
        if (!current && entries.length >= MAX_PUBLIC_INDEX_ENTRIES) return { ok: false, error: "index_capacity", limit: MAX_PUBLIC_INDEX_ENTRIES };
        if (position >= 0) entries[position] = next;
        else entries.push(next);
        await storage.put("publicIndex", { entries });
        return { ok: true, entry: next };
      };
      const result = typeof this.state.storage.transaction === "function"
        ? await this.state.storage.transaction(update)
        : await update(this.state.storage);
      return this.response(result, result.ok ? 200 : 409);
    }
    if (url.pathname === "/index") {
      const index = (await this.state.storage.get("publicIndex")) || { entries: [] };
      return this.response({ ok: true, entries: Array.isArray(index.entries) ? index.entries : [] });
    }
    if (url.pathname === "/promote") {
      const number = Number(input.revision);
      const current = await this.state.storage.get(`revision:${number}`);
      if (!current) return this.response({ ok: false, error: "revision_not_found" }, 404);
      if (current.status === "verified") return this.response({ ok: true, revision: current });
      if (current.status !== "submitted") return this.response({ ok: false, error: "invalid_status" }, 409);
      const revision = { ...current, status: "verified", verifiedAt: input.verifiedAt || new Date().toISOString() };
      await this.state.storage.put(`revision:${number}`, revision);
      return this.response({ ok: true, revision });
    }
    return this.response({ ok: false, error: "not found" }, 404);
  }
  async revisions() {
    const count = Number(await this.state.storage.get("nextRevision") || 0);
    const values = [];
    for (let n = 1; n <= count; n++) {
      const value = await this.state.storage.get(`revision:${n}`);
      if (value) values.push(value);
    }
    return values;
  }
  response(value, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }); }
}

function configuration(env) {
  const token = typeof env.APP_TOKEN === "string" ? env.APP_TOKEN.trim() : "";
  const rawOrigin = typeof env.ALLOWED_ORIGIN === "string" ? env.ALLOWED_ORIGIN.trim() : "";
  if (!token || !rawOrigin) return { ok: false };
  let parsed;
  try { parsed = new URL(rawOrigin); } catch { return { ok: false }; }
  if (!/^https?:$/.test(parsed.protocol) || parsed.origin !== rawOrigin || parsed.pathname !== "/" || parsed.search || parsed.hash || parsed.username || parsed.password) return { ok: false };
  return { ok: true, token, origin: parsed.origin };
}
function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Vary": "Origin",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-App-Token,X-Game-Code",
  };
}
function publicCors() {
  return { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET", "Access-Control-Allow-Headers": "Content-Type" };
}
function json(obj, statusCode, cors) {
  return new Response(JSON.stringify(obj), {
    status: statusCode || 200,
    headers: { "Content-Type": "application/json", ...(cors || {}) },
  });
}

// ---------------------------------------------------------------------------
// HomeTeamsOnline session handling
// ---------------------------------------------------------------------------

/** Merge Set-Cookie headers into a "name=value; name=value" jar string. */
function mergeCookies(existing, resp) {
  const jar = {};
  for (const part of (existing || "").split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k) jar[k] = v.join("=");
  }
  const setCookies = typeof resp.headers.getSetCookie === "function"
    ? resp.headers.getSetCookie()
    : [resp.headers.get("set-cookie")].filter(Boolean);
  for (const sc of setCookies) {
    const first = sc.split(";")[0];
    const [k, ...v] = first.split("=");
    if (k) jar[k.trim()] = v.join("=");
  }
  return Object.entries(jar).map(([k, v]) => `${k}=${v}`).join("; ");
}

/** Log in fresh and persist the session cookie to KV. Returns the cookie string. */
async function login(env) {
  // 1) Seed an ASP session cookie by hitting the login page.
  const seed = await fetch(LOGIN_PAGE, { redirect: "manual" });
  let cookie = mergeCookies("", seed);

  // 2) Authenticate that session.
  const body = new URLSearchParams({ username: env.HTO_USERNAME, password: env.HTO_PASSWORD });
  const resp = await fetch(LOGIN_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      "Cookie": cookie,
    },
    body: body.toString(),
    redirect: "manual",
  });
  cookie = mergeCookies(cookie, resp);
  const text = await resp.text();
  if (resp.status >= 400 || /loginForm|error=/i.test(text)) {
    throw new Error(`HTO login failed (status ${resp.status})`);
  }
  await env.SESSION.put(SESSION_KEY, cookie);
  return cookie;
}

/** True when a response indicates the session is no longer authenticated. */
function looksUnauthed(resp, text) {
  if (resp.status === 301 || resp.status === 302) {
    if (/p=login/i.test(resp.headers.get("location") || "")) return true;
  }
  if (text && /SessionExpired|p=login&error|id="loginForm"/i.test(text)) return true;
  return false;
}

/**
 * Fetch an HTO URL using the stored session, re-logging-in once on expiry.
 * Returns { resp, text }.
 */
async function htoFetch(env, target, init = {}, allowRetry = true) {
  let cookie = await env.SESSION.get(SESSION_KEY);
  if (!cookie) cookie = await login(env);

  const doFetch = (ck) =>
    fetch(target, {
      ...init,
      redirect: "manual",
      headers: { ...(init.headers || {}), "Cookie": ck },
    });

  let resp = await doFetch(cookie);
  let text = await resp.text();

  if (allowRetry && looksUnauthed(resp, text)) {
    cookie = await login(env);
    resp = await doFetch(cookie);
    text = await resp.text();
  }
  return { resp, text };
}

// ---------------------------------------------------------------------------
// API handlers
// ---------------------------------------------------------------------------
async function listGames(env) {
  const { text: html } = await htoFetch(env, SCHEDULE_AJAX, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: "action=getDetailsHTML",
  });
  return parseGamesFromSchedule(html, seasonMapId(env));
}

const PUBLIC_DEFAULT_LIMIT = 20;
const PUBLIC_MAX_LIMIT = 100;
// The public index is a finite directory of distinct games, not an unbounded
// event log. Existing games may continue to advance at the ceiling.
export const MAX_PUBLIC_INDEX_ENTRIES = 400;
function publicLimit(url) {
  const raw = url.searchParams.get("limit");
  if (raw == null || raw === "") return PUBLIC_DEFAULT_LIMIT;
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? Math.min(value, PUBLIC_MAX_LIMIT) : PUBLIC_DEFAULT_LIMIT;
}
function publicProjection(record) {
  if (!record) return null;
  const status = record.status === "verified" ? "final" : "live";
  return {
    gameId: String(record.gameId || ""),
    teams: publicTeams(record.displayTeams || record.teams),
    boxScore: publicBoxScore(record.boxScore),
    scores: publicEvents(record.scoreSummary, ["period", "clock", "scoreTeam", "team", "scorer", "assists", "scoreTotalText"]),
    penalties: publicEvents(record.penaltySummary, ["period", "clock", "penaltyTeam", "team", "penaltyPlayer", "servedPlayer", "infraction", "penaltyLength", "minutes"]),
    periodSummary: publicEvents(record.periodSummary, ["period", "home", "away", "homeScore", "awayScore"]),
    seasonMapId: record.seasonMapId || null,
    revision: Number(record.revision || 0),
    status,
    submittedAt: record.submittedAt || null,
    verifiedAt: record.verifiedAt || null,
  };
}
function publicTeams(value) {
  if (!value || typeof value !== "object") return null;
  const side = (item) => item && typeof item === "object" ? { name: item.name || null, key: item.key || null } : null;
  return { home: side(value.home), away: side(value.away) };
}
function sanitizeDisplayTeams(value) {
  if (!value || typeof value !== "object") return null;
  const side = (item) => item && typeof item === "object" ? {
    name: typeof item.name === "string" ? item.name : null,
    key: typeof item.key === "string" ? item.key : null,
  } : null;
  return { home: side(value.home), away: side(value.away) };
}
function publicBoxScore(value) {
  if (!value || typeof value !== "object") return null;
  return Object.fromEntries(Object.entries(value).map(([team, row]) => [String(team), {
    goals: Number(row?.goals || 0), penaltyCount: Number(row?.penaltyCount || 0), penaltyMinutes: Number(row?.penaltyMinutes || 0),
  }]));
}
function publicEvents(value, fields) {
  return Array.isArray(value) ? value.map((event) => Object.fromEntries(fields.filter((field) => event && event[field] !== undefined).map((field) => [field, event[field]]))) : [];
}
function publicIndex(env) {
  const namespace = env.GAME_RECORDS;
  if (!namespace || typeof namespace.idFromName !== "function") throw new Error("index unavailable");
  return namespace.get(namespace.idFromName("__public-index__"));
}
async function publicRoute(env, url) {
  const namespace = env.GAME_RECORDS;
  if (!namespace || typeof namespace.idFromName !== "function") return { body: { ok: false, error: "configuration_error" }, status: 503 };
  const box = url.pathname.match(/^\/api\/public\/games\/([^/]+)\/boxscore$/);
  if (box) {
    const gameId = decodeURIComponent(box[1]);
    const response = await namespace.get(namespace.idFromName(gameId)).fetch(new Request(`https://record/${encodeURIComponent(gameId)}`, { method: "GET" }));
    if (!response.ok) return { body: { ok: false, error: "not_found" }, status: 404 };
    const data = await response.json();
    return data.latest ? { body: publicProjection(data.latest), status: 200 } : { body: { ok: false, error: "not_found" }, status: 404 };
  }
  const indexResponse = await publicIndex(env).fetch(new Request("https://record/index", { method: "GET" }));
  const index = await indexResponse.json();
  const timestamp = (value) => {
    const parsed = Date.parse(String(value || ""));
    return Number.isFinite(parsed) ? parsed : null;
  };
  const entries = (index.entries || []).slice().sort((a, b) => {
    const left = timestamp(a.updatedAt), right = timestamp(b.updatedAt);
    if (left === null && right === null) return String(a.gameId || "").localeCompare(String(b.gameId || ""));
    if (left === null) return 1;
    if (right === null) return -1;
    return right - left || String(a.gameId || "").localeCompare(String(b.gameId || ""));
  }).slice(0, publicLimit(url));
  const games = [];
  for (const entry of entries) {
    const response = await namespace.get(namespace.idFromName(String(entry.gameId))).fetch(new Request(`https://record/${encodeURIComponent(entry.gameId)}`, { method: "GET" }));
    if (response.ok) { const data = await response.json(); if (data.latest) games.push(publicProjection(data.latest)); }
  }
  return { body: { games, limit: publicLimit(url) }, status: 200 };
}

async function gameSetup(env, gameId, div, gameId2) {
  if (!div) throw new Error("missing ?div (home division id)");
  const target = `${HTO}/admin/default.asp?p=ScoresEdit&a=1&sportsHQ=${encodeURIComponent(div)}&gameID=${gameId}&gameID2=${encodeURIComponent(gameId2)}`;
  const { text: html } = await htoFetch(env, target);

  const rosters = parsePlayersByUsername(html);
  const infractions = parseInfractionList(html);
  const finals = parseFinals(html); // current line-score finals from the static form
  const authoritative = parseAuthoritativeEvents(html);

  const homeDiv = div;
  const awayDiv = Object.keys(rosters).find((d) => d !== homeDiv) || null;

  return {
    ok: true,
    gameId,
    gameId2,
    seasonMapId: seasonMapId(env),
    home: { div: homeDiv, name: TEAMS[homeDiv] || homeDiv, players: rosters[homeDiv] || [] },
    away: awayDiv ? { div: awayDiv, name: TEAMS[awayDiv] || awayDiv, players: rosters[awayDiv] || [] } : null,
    infractions,
    current: {
      finals,
      goals: authoritative.goals,
      penalties: authoritative.penalties,
      comparisonToken: comparisonToken({ finals, goals: authoritative.goals, penalties: authoritative.penalties }),
      seasonMapId: seasonMapId(env),
    },
  };
}

async function syncGame(env, gameId, body, options = {}) {
  const username = body.username; // home division id, not operator identity
  const operatorId = options.operatorId;
  if (!username) return conflict("invalid_request", "missing username (home division id)");
  if (!operatorId) return conflict("identity_required", "operator identity is required");
  if (!body.leaseId) return conflict("lease_required", "an active game lease is required");
  if (!body.comparisonToken) return conflict("baseline_required", "authoritative comparison token is required");
  const expectedSeason = body.seasonMapId || env.SEASON_MAP_ID;
  if (env.SEASON_MAP_ID && expectedSeason !== env.SEASON_MAP_ID) return conflict("season_map_drift", "schedule season map does not match the configured season map");

  const coordinator = options.coordinator || leaseCoordinator(env);
  const ownership = await coordinator.check({ gameId, operatorId, leaseId: body.leaseId });
  if (!ownership.ok) return conflict(ownership.reason || "lease_conflict", ownership.message || "game lease is not owned");

  // This read is deliberately immediately before the first write. The caller's
  // token is compared to a fresh authoritative snapshot, never to cached KV.
  let remote;
  try {
    remote = options.authoritativeReader
      ? await options.authoritativeReader({ gameId, username, gameId2: body.gameId2 })
      : (await gameSetup(env, gameId, username, body.gameId2 || "")).current;
  } catch (error) {
    return conflict("remote_read_failed", error.message);
  }
  if (!remote || !remote.comparisonToken) return conflict("baseline_required", "authoritative baseline is required");
  if (expectedSeason && remote.seasonMapId && remote.seasonMapId !== expectedSeason) return conflict("season_map_drift", "authoritative setup/roster season map changed");
  const actualToken = comparisonToken({ finals: remote.finals, goals: remote.goals, penalties: remote.penalties });
  if (actualToken !== body.comparisonToken || actualToken !== remote.comparisonToken) {
    return conflict("remote_drift", "authoritative remote snapshot changed");
  }
  const stillOwned = await coordinator.check({ gameId, operatorId, leaseId: body.leaseId });
  if (!stillOwned.ok) return conflict(stillOwned.reason || "lease_conflict", stillOwned.message || "game lease expired before publish");
  if (!Array.isArray(body.scoreSummary) && !Array.isArray(body.penaltySummary)) {
    return conflict("invalid_request", "at least one summary array is required");
  }

  const writer = options.writer || postSummary;
  const results = {};

  // These are deliberately separate phases. A retry repeats the complete
  // arrays, so a partial upstream write is safe to resume without pretending
  // that the second request (or verification) happened.
  if (!Array.isArray(body.scoreSummary) || !Array.isArray(body.penaltySummary)) {
    return conflict("invalid_request", "both goal and penalty summary arrays are required");
  }
  // Canonical capture is the first operation after all validation and lease
  // checks, so a publication failure cannot discard a valid captain revision.
  const recordBoundary = options.gameRecord || canonicalRecord(env);
  if (!recordBoundary) return conflict("canonical_persistence_failed", "GAME_RECORDS binding is required");
  let captured;
  try {
    captured = await recordBoundary.append({
        gameId: String(gameId),
        scoreSummary: body.scoreSummary,
        penaltySummary: body.penaltySummary,
        boxScore: deriveBoxScore(body.scoreSummary, body.penaltySummary),
        displayTeams: body.displayTeams || body.teams || null,
        periodSummary: Array.isArray(body.periodSummary) ? body.periodSummary : derivePeriodSummary(body.scoreSummary, body.displayTeams || body.teams),
        seasonMapId: expectedSeason || seasonMapId(env),
        subject: options.operatorId || operatorId,
        status: "submitted",
        submittedAt: new Date().toISOString(),
    });
  } catch (error) {
    return conflict("canonical_persistence_failed", String((error && error.message) || error));
  }
  try {
    results.goals = await writer(env, "updateScoreSummary", "scoreSummaryData", gameId, username, body.scoreSummary);
  } catch (error) {
    return publicationFailure("goals", "goal-failed", error, results, body);
  }

  try {
    results.penalties = await writer(env, "updatePenaltySummary", "penaltySummaryData", gameId, username, body.penaltySummary);
  } catch (error) {
    // The goal write changed the authoritative comparison token. Recover the
    // exact partial state so a retry can compare against reality instead of
    // being rejected with the now-stale pre-publication token.
    try {
      const partial = options.authoritativeReader
        ? await options.authoritativeReader({ gameId, username, gameId2: body.gameId2, phase: "partial-recovery" })
        : (await gameSetup(env, gameId, username, body.gameId2 || "")).current;
      if (!partial || !sameEvents(partial.goals, body.scoreSummary)) {
        return publicationFailure("verification", "conflict", new Error("partial goal publication could not be verified"), results, body, "partial_verification_mismatch");
      }
      return publicationFailure("penalties", "goal-published/partial", error, results, body, "publication_failed", {
        comparisonToken: comparisonToken({ finals: partial.finals, goals: partial.goals, penalties: partial.penalties }),
      });
    } catch (recoveryError) {
      return publicationFailure("verification", "conflict", recoveryError, results, body, "partial_verification_failed");
    }
  }

  // The write acknowledgements are not authoritative. Read the editor again
  // through the injected boundary and only then report full publication.
  let verified;
  try {
    verified = options.authoritativeReader
      ? await options.authoritativeReader({ gameId, username, gameId2: body.gameId2, phase: "verifying" })
      : (await gameSetup(env, gameId, username, body.gameId2 || "")).current;
  } catch (error) {
    return publicationFailure("verification", "penalty-published", error, results, body, "verification_failed");
  }
  if (!verified || !sameEvents(verified.goals, body.scoreSummary) || !sameEvents(verified.penalties, body.penaltySummary)) {
    return publicationFailure("verification", "conflict", new Error("authoritative reread does not match requested revision"), results, body, "verification_mismatch");
  }
  if (captured?.revision) {
    try { await recordBoundary.promote(captured); }
    catch (error) { return publicationFailure("verification", "penalty-published", error, results, body, "canonical_promotion_failed"); }
  }
  return {
    ok: true, status: "published", phase: "published", verified: true, results,
    canonical: captured ? { revision: captured.revision, indexUpdated: captured.indexUpdated !== false } : null,
    leaseId: body.leaseId, comparisonToken: comparisonToken({
      finals: verified.finals, goals: verified.goals, penalties: verified.penalties,
    }),
  };
}

export function canonicalRecord(env) {
  const namespace = env.GAME_RECORDS;
  if (!namespace || typeof namespace.idFromName !== "function") return null;
  const stub = (gameId) => namespace.get(namespace.idFromName(String(gameId)));
  const index = namespace.get(namespace.idFromName("__public-index__"));
  return {
    append: async (value) => {
      const result = await gameRecordCall(stub(value.gameId), "/append", value);
      try {
        await gameRecordCall(index, "/index-update", { gameId: value.gameId, seasonMapId: value.seasonMapId, displayTeams: value.displayTeams, revision: result.revision.revision, updatedAt: value.submittedAt });
        return { ...result.revision, indexUpdated: true };
      } catch {
        // Canonical append is durable; index refresh is best-effort and can be retried.
        return { ...result.revision, indexUpdated: false, indexFailure: true };
      }
    },
    promote: async (revision) => gameRecordCall(stub(revision.gameId), "/promote", { revision: revision.revision }),
  };
}
async function gameRecordCall(stub, path, value) {
  const response = await stub.fetch(new Request(`https://game-record${path}`, { method: "POST", body: JSON.stringify(value) }));
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || "canonical record operation failed");
  return result;
}
function deriveBoxScore(goals, penalties) {
  const teams = new Map();
  const row = (team) => {
    const key = String(team || "");
    if (!teams.has(key)) teams.set(key, { goals: 0, penaltyCount: 0, penaltyMinutes: 0 });
    return teams.get(key);
  };
  for (const event of goals) row(event?.scoreTeam ?? event?.team).goals++;
  for (const event of penalties) {
    const value = row(event?.penaltyTeam ?? event?.team); value.penaltyCount++; value.penaltyMinutes += Number(event?.penaltyLength ?? event?.minutes) || 0;
  }
  return Object.fromEntries([...teams.entries()].sort(([a], [b]) => a.localeCompare(b)));
}

function derivePeriodSummary(goals, displayTeams) {
  if (!Array.isArray(goals) || !goals.length) return [];
  const homeKey = displayTeams?.home?.key || "HOME";
  const rows = new Map();
  for (const goal of goals) {
    const period = String(goal?.period || "");
    if (!period) continue;
    if (!rows.has(period)) rows.set(period, { period, homeScore: 0, awayScore: 0 });
    const row = rows.get(period);
    if (String(goal?.scoreTeam ?? goal?.team ?? "") === String(homeKey)) row.homeScore += 1;
    else row.awayScore += 1;
  }
  return [...rows.values()];
}

function conflict(code, message) { return { ok: false, conflict: true, code, message, writes: 0 }; }

function sameEvents(actual, requested) {
  return stableStringify(actual) === stableStringify(requested);
}

function publicationFailure(phase, status, error, results, body, code = "publication_failed", extra = {}) {
  return {
    ok: false, conflict: phase === "verification", retryable: true, code,
    phase, status, message: String((error && error.message) || error), results,
    revision: body.revision, writes: Object.keys(results).length, ...extra,
  };
}

function operatorIdentity(request, env) {
  // D2 is intentionally unresolved: this is only an injected/default adapter,
  // and never a claim that X-Operator-Id is an identity provider.
  return (env.IDENTITY_ADAPTER || defaultIdentityAdapter)(request, env);
}
function seasonMapId(env) { return env.SEASON_MAP_ID || DEFAULT_SEASON_MAP_ID; }
function defaultIdentityAdapter(request) { return request.headers.get("X-Operator-Id") || null; }

async function leaseAction(env, gameId, body, operatorId) {
  const coordinator = leaseCoordinator(env);
  const input = { gameId, operatorId, leaseId: body.leaseId, ttlMs: body.ttlMs };
  if (body.action === "acquire") return coordinator.acquire(input);
  if (body.action === "renew") return coordinator.renew(input);
  if (body.action === "release") return coordinator.release(input);
  return conflict("invalid_request", "lease action must be acquire, renew, or release");
}

function leaseCoordinator(env) {
  if (env.GAME_LEASES && typeof env.GAME_LEASES.idFromName === "function") {
    return durableLeaseCoordinator(env.GAME_LEASES);
  }
  return env.LEASE_COORDINATOR || rejectingLeaseCoordinator();
}

function durableLeaseCoordinator(namespace) {
  const stub = (gameId) => namespace.get(namespace.idFromName(String(gameId)));
  return { acquire: (x) => stub(x.gameId).fetch("https://lease/acquire", { method: "POST", body: JSON.stringify(x) }).then(r => r.json()),
    renew: (x) => stub(x.gameId).fetch("https://lease/renew", { method: "POST", body: JSON.stringify(x) }).then(r => r.json()),
    release: (x) => stub(x.gameId).fetch("https://lease/release", { method: "POST", body: JSON.stringify(x) }).then(r => r.json()),
    check: (x) => stub(x.gameId).fetch("https://lease/check", { method: "POST", body: JSON.stringify(x) }).then(r => r.json()) };
}

function rejectingLeaseCoordinator() {
  const rejected = async () => ({ ok: false, reason: "lease_unconfigured", message: "distributed game lease is not configured" });
  return { acquire: rejected, renew: rejected, release: rejected, check: rejected };
}

/** Durable Object: one object per exact game gives serialized lease mutations. */
export class GameLease {
  constructor(state) { this.state = state; }
  async fetch(request) {
    const action = new URL(request.url).pathname.slice(1);
    const input = await request.json();
    const now = Date.now();
    const current = await this.state.storage.get("lease");
    if (current && current.expiresAt <= now) await this.state.storage.delete("lease");
    const lease = current && current.expiresAt > now ? current : null;
    let result;
    if (action === "acquire") {
      if (lease && lease.operatorId !== input.operatorId) result = conflict("lease_owned", "game is leased by another operator");
      else {
        const next = { operatorId: input.operatorId, leaseId: lease?.leaseId || crypto.randomUUID(), expiresAt: now + leaseTtl(input.ttlMs) };
        await this.state.storage.put("lease", next); result = { ok: true, ...next };
      }
    } else if (action === "renew" || action === "release" || action === "check") {
      const owns = lease && lease.operatorId === input.operatorId && lease.leaseId === input.leaseId;
      if (!owns) result = conflict("lease_conflict", "lease owner or lease token is invalid");
      else if (action === "release") { await this.state.storage.delete("lease"); result = { ok: true, released: true }; }
      else if (action === "renew") { const next = { ...lease, expiresAt: now + leaseTtl(input.ttlMs) }; await this.state.storage.put("lease", next); result = { ok: true, ...next }; }
      else result = { ok: true, expiresAt: lease.expiresAt };
    } else result = conflict("invalid_request", "unknown lease action");
    return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
  }
}

function leaseTtl(value) { return Math.min(Math.max(Number(value) || 30000, 1000), 120000); }

/** Fixture/test coordinator. Production uses the Durable Object above. */
function createInMemoryLeaseCoordinator(clock = () => Date.now()) {
  const leases = new Map(); let sequence = 0;
  function active(gameId) {
    const lease = leases.get(String(gameId));
    if (lease && lease.expiresAt <= clock()) { leases.delete(String(gameId)); return null; }
    return lease || null;
  }
  function own(input) {
    const lease = active(input.gameId);
    return lease && lease.operatorId === input.operatorId && lease.leaseId === input.leaseId;
  }
  return {
    async acquire(input) {
      const existing = active(input.gameId);
      if (existing && existing.operatorId !== input.operatorId) return conflict("lease_owned", "game is leased by another operator");
      const lease = { operatorId: input.operatorId, leaseId: existing?.leaseId || `lease-${++sequence}`, expiresAt: clock() + leaseTtl(input.ttlMs) };
      leases.set(String(input.gameId), lease); return { ok: true, ...lease };
    },
    async renew(input) {
      if (!own(input)) return conflict("lease_conflict", "lease owner or lease token is invalid");
      const lease = { ...active(input.gameId), expiresAt: clock() + leaseTtl(input.ttlMs) };
      leases.set(String(input.gameId), lease); return { ok: true, ...lease };
    },
    async release(input) {
      if (!own(input)) return conflict("lease_conflict", "lease owner or lease token is invalid");
      leases.delete(String(input.gameId)); return { ok: true, released: true };
    },
    async check(input) { return own(input) ? { ok: true } : conflict("lease_conflict", "lease owner or lease token is invalid"); },
  };
}

async function postSummary(env, action, key, gameId, username, arr) {
  const body = new URLSearchParams();
  body.set("action", action);
  body.set(key, JSON.stringify(arr));
  body.set("gameID", String(gameId));
  body.set("username", username);
  const { resp, text } = await htoFetch(env, SCORESEDIT_AJAX, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: body.toString(),
  });
  let parsed;
  try { parsed = JSON.parse(text); } catch { parsed = { raw: text.slice(0, 200) }; }
  if (!resp.ok || parsed.success !== 1) {
    throw new Error(`${action} failed (status ${resp.status})`);
  }
  return parsed;
}

// NOTE: game status (pre / in-progress / final) is NOT an ajax action — on the
// site it toggles the #inProgress checkbox and submits the full score form
// (and 'pre' clears scores). Left out of the prototype on purpose; see README.

// ---------------------------------------------------------------------------
// Parsers (regex over server HTML — no DOM in Workers)
// ---------------------------------------------------------------------------

/** Pull games out of the admin schedule page via the per-row ScoreClick handlers. */
function parseGamesFromSchedule(html, mapId = DEFAULT_SEASON_MAP_ID) {
  const games = [];
  const re = /ScoreClick\('default\.asp\?p=ScoresEdit&a=1&sportsHQ=([^&]+)&gameID=(\d+)&gameID2=(\d+)',\s*(\d+)\)/g;
  for (const m of html.matchAll(re)) {
    const homeDiv = m[1], gameId = m[2], gameId2 = m[3], ts = m[4];
    // Grab the enclosing <tr> so we can read team names + location as rendered text.
    const idx = m.index;
    const trStart = html.lastIndexOf("<tr", idx);
    const trEnd = html.indexOf("</tr>", idx);
    const rowText = stripTags(html.slice(trStart, trEnd === -1 ? idx : trEnd));

    // Match known team names in order of appearance: away listed first, home second.
    const found = [];
    for (const [div, name] of Object.entries(TEAMS)) {
      const at = rowText.indexOf(name);
      if (at >= 0) found.push({ div, name, at });
    }
    found.sort((a, b) => a.at - b.at);
    const awayEntry = found.find((f) => f.div !== homeDiv);
    const location = LOCATIONS.find((l) => rowText.includes(l)) || "";

    games.push({
      gameId,
      gameId2,
      homeDiv,
      awayDiv: awayEntry ? awayEntry.div : null,
      home: TEAMS[homeDiv] || homeDiv,
      away: awayEntry ? awayEntry.name : null,
      location,
      startMs: Number(ts),
      seasonMapId: mapId,
    });
  }
  const seen = new Set();
  return games
    .filter((g) => (seen.has(g.gameId) ? false : seen.add(g.gameId)))
    .sort((a, b) => a.startMs - b.startMs);
}

/** Extract globalVars.playersByUsername = {div:[{playerID,playernumber,firstName,lastName}]}. */
function parsePlayersByUsername(html) {
  const obj = extractJsonAssignment(html, "globalVars.playersByUsername");
  if (!obj) return {};
  const out = {};
  for (const [div, players] of Object.entries(obj)) {
    out[div] = players.map((p) => ({
      id: String(p.playerID),
      number: p.playernumber,
      name: `${(p.firstName || "").trim()} ${(p.lastName || "").trim()}`.trim(),
    }));
  }
  return out;
}

/** Extract globalVars.infractionList = {code:{label,severity}}. */
function parseInfractionList(html) {
  const obj = extractJsonAssignment(html, "globalVars.infractionList");
  if (!obj) return [];
  return Object.entries(obj).map(([code, v]) => ({
    code,
    label: v.label || code,
    severity: v.severity || "minor",
  }));
}

/** Read the static line-score final inputs (cheap "does this game already have a score?" signal). */
function parseFinals(html) {
  const grab = (name) => {
    const m = html.match(new RegExp(`name=["']${name}["'][^>]*value=["']([^"']*)["']`, "i"));
    return m ? Number(m[1] || 0) : 0;
  };
  return { h: grab("finalh"), a: grab("finala") };
}

/**
 * Read the event arrays embedded in the Game Score editor. These are the
 * authoritative remote baseline: callers must never substitute [] when the
 * editor shape is unknown or malformed.
 *
 * The editor has used both the globalVars names and the submitted form names
 * over time; the fixture and these aliases keep that variation explicit.
 */
function parseAuthoritativeEvents(html) {
  const goals = firstArrayAssignment(html, [
    "globalVars.scoreSummary", "globalVars.scoringSummary", "scoreSummaryData",
  ]);
  const penalties = firstArrayAssignment(html, [
    "globalVars.penaltySummary", "globalVars.penaltiesSummary", "penaltySummaryData",
  ]);
  if (!goals || !penalties || !goals.every(isEvent) || !penalties.every(isEvent)) {
    throw new Error("authoritative event arrays missing or malformed");
  }
  return { goals, penalties };
}

function firstArrayAssignment(html, names) {
  for (const name of names) {
    const value = extractJsonAssignment(html, name);
    if (Array.isArray(value)) return value;
  }
  return null;
}

function isEvent(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Stable, local comparison token for the complete authoritative setup. */
function comparisonToken(value) {
  const canonical = stableStringify(value);
  let hash = 0xcbf29ce484222325n;
  for (let i = 0; i < canonical.length; i++) {
    hash ^= BigInt(canonical.charCodeAt(i));
    hash = BigInt.asUintN(64, hash * 0x100000001b3n);
  }
  return hash.toString(16).padStart(16, "0");
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

/** Find `name = { ... }` / `name = [ ... ]` and JSON.parse the balanced literal. */
function extractJsonAssignment(html, name) {
  const at = html.indexOf(name);
  if (at < 0) return null;
  const eq = html.indexOf("=", at);
  if (eq < 0) return null;
  let i = eq + 1;
  while (i < html.length && /\s/.test(html[i])) i++;
  const open = html[i];
  const close = open === "{" ? "}" : open === "[" ? "]" : null;
  if (!close) return null;
  let depth = 0, inStr = false, esc = false, end = -1;
  for (let j = i; j < html.length; j++) {
    const c = html[j];
    if (inStr) {
      if (esc) esc = false;
      else if (c === "\\") esc = true;
      else if (c === '"') inStr = false;
    } else {
      if (c === '"') inStr = true;
      else if (c === open) depth++;
      else if (c === close) { depth--; if (depth === 0) { end = j; break; } }
    }
  }
  if (end < 0) return null;
  try { return JSON.parse(html.slice(i, end + 1)); } catch { return null; }
}

function stripTags(s) {
  return s.replace(/<[^>]*>/g, " ").replace(/&amp;/g, "&").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();
}

export { comparisonToken, createInMemoryLeaseCoordinator, gameSetup, parseAuthoritativeEvents, syncGame, configuration, seasonMapId };
