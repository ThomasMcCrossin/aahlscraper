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
 * Endpoints (all require header `X-App-Token: <APP_TOKEN>`):
 *   GET  /api/games                         -> [{gameId, gameId2, homeDiv, awayDiv, home, away, location, startMs}]
 *   GET  /api/games/:gameId/setup?div=&g2=  -> {home, away, infractions, current:{finals}}
 *   POST /api/games/:gameId/sync            -> {ok, results}   body: {username, scoreSummary[], penaltySummary[]}
 *   GET  /api/health                        -> {ok}
 *
 * Bindings (wrangler.toml):
 *   KV  SESSION              - stores the HTO session cookie
 *   var ALLOWED_ORIGIN       - the PWA origin for CORS (e.g. https://aahl-scoresheet.pages.dev)
 *   secret HTO_USERNAME      - league login email
 *   secret HTO_PASSWORD      - league login password
 *   secret APP_TOKEN         - shared secret the PWA must send
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

// ---------------------------------------------------------------------------
// Worker entry
// ---------------------------------------------------------------------------
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(env);

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    try {
      if (url.pathname === "/api/health") return json({ ok: true }, 200, cors);

      // Simple shared-secret gate so the proxy isn't open to the world.
      if (env.APP_TOKEN && request.headers.get("X-App-Token") !== env.APP_TOKEN) {
        return json({ ok: false, error: "unauthorized" }, 401, cors);
      }

      if (url.pathname === "/api/games" && request.method === "GET") {
        return json(await listGames(env), 200, cors);
      }

      const setup = url.pathname.match(/^\/api\/games\/(\d+)\/setup$/);
      if (setup && request.method === "GET") {
        const div = url.searchParams.get("div");
        const g2 = url.searchParams.get("g2") || "";
        return json(await gameSetup(env, setup[1], div, g2), 200, cors);
      }

      const sync = url.pathname.match(/^\/api\/games\/(\d+)\/sync$/);
      if (sync && request.method === "POST") {
        const body = await request.json();
        return json(await syncGame(env, sync[1], body), 200, cors);
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
function corsHeaders(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-App-Token",
  };
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
  return parseGamesFromSchedule(html);
}

async function gameSetup(env, gameId, div, gameId2) {
  if (!div) throw new Error("missing ?div (home division id)");
  const target = `${HTO}/admin/default.asp?p=ScoresEdit&a=1&sportsHQ=${encodeURIComponent(div)}&gameID=${gameId}&gameID2=${encodeURIComponent(gameId2)}`;
  const { text: html } = await htoFetch(env, target);

  const rosters = parsePlayersByUsername(html);
  const infractions = parseInfractionList(html);
  const finals = parseFinals(html); // current line-score finals from the static form

  const homeDiv = div;
  const awayDiv = Object.keys(rosters).find((d) => d !== homeDiv) || null;

  return {
    ok: true,
    gameId,
    gameId2,
    home: { div: homeDiv, name: TEAMS[homeDiv] || homeDiv, players: rosters[homeDiv] || [] },
    away: awayDiv ? { div: awayDiv, name: TEAMS[awayDiv] || awayDiv, players: rosters[awayDiv] || [] } : null,
    infractions,
    current: { finals }, // full event resume is a v2 item — see README
  };
}

async function syncGame(env, gameId, body) {
  const username = body.username; // home division id
  if (!username) throw new Error("missing username (home division id)");

  const results = {};
  if (Array.isArray(body.scoreSummary)) {
    results.score = await postSummary(env, "updateScoreSummary", "scoreSummaryData", gameId, username, body.scoreSummary);
  }
  if (Array.isArray(body.penaltySummary)) {
    results.penalty = await postSummary(env, "updatePenaltySummary", "penaltySummaryData", gameId, username, body.penaltySummary);
  }
  return { ok: true, results };
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
function parseGamesFromSchedule(html) {
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
