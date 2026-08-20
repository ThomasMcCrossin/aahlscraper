# AAHL Live Scoresheet (prototype)

Replace the paper scoresheet: the timekeeper enters goals/penalties on a tablet
during the game, and they push straight into HomeTeamsOnline — so the public
site, the scraper, and the Yodeck display all update automatically. No lost
sheets, no missing pen, no after-the-fact data entry.

**Status:** working prototype (thin slice). Every piece of the data path has been
validated against the live HomeTeamsOnline system; the proxy just wires them
together. See `../docs/SCORESHEET_APP_FEASIBILITY.md` for the full reverse-engineering writeup.

## How it works

```
 tablet PWA  ──HTTPS──►  Cloudflare Worker (proxy)  ──session cookie──►  HomeTeamsOnline
 (web/)                  (worker/)                                       (admin/ajax/*)
 - offline-first         - holds league login                           - scoresedit.asp
 - localStorage buffer   - lists games / rosters                          (replace semantics)
 - full-array sync       - forwards score+penalty arrays
```

- The PWA writes every event to `localStorage` immediately, so scoring keeps
  working with no signal. A debounced sync re-POSTs the **entire** score/penalty
  arrays. Because HomeTeamsOnline's endpoint replaces the whole summary, retries
  after flaky rink wifi can never double-count — idempotent by design.
- The league password lives **only** in the Worker's secrets, never on the tablet.
- Connect uses a short human-typeable per-game code. The PWA sends it as
  `X-Game-Code`; the Worker redeems it to the exact game and uses its returned
  subject for lease ownership. Codes are stored under `aahl_game_code_<gameId>`
  only after successful redemption. Authorization failures never clear the
  `aahl_game_<gameId>` event or recovery data.

## Deploy

### 1. Worker (backend)
```bash
cd worker
npm install
npx wrangler kv namespace create SESSION      # paste the id into wrangler.toml
npx wrangler secret put HTO_USERNAME
npx wrangler secret put HTO_PASSWORD
npx wrangler secret put APP_TOKEN              # administrator code-management secret
npx wrangler secret put GAME_CODE_PEPPER       # keyed digest pepper; do not expose its value
npx wrangler deploy
```
The Worker also requires the `GameCodeRegistry` Durable Object binding and its
migration in `worker/wrangler.toml`, plus the existing `SESSION` KV binding.
Use the admin code-management routes to mint, revoke, or reissue a code for an
exact `gameId`; plaintext is returned only by mint/reissue and is never stored.
Set `ALLOWED_ORIGIN` in `wrangler.toml` to the PWA URL (below) once you have it,
then `npx wrangler deploy` again.

### 2. PWA (front-end)
Any static host works. With Cloudflare Pages:
```bash
cd web
npx wrangler pages deploy . --project-name aahl-scoresheet
```
Open the page, tap **Connect**, enter the Worker URL + the per-game code. On a phone/
tablet, "Add to Home Screen" installs it as an app (offline-capable).

### Local dev
```bash
cd worker && npx wrangler dev          # proxy at http://localhost:8787
cd web && python3 -m http.server 5173  # PWA at http://localhost:5173
```

## API (Worker)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | minimal liveness boundary (no auth; no protected work) |
| GET | `/api/games` | redeem `X-Game-Code` and list only its authorized game `{gameId,gameId2,homeDiv,awayDiv,home,away,location,startMs}` |
| GET | `/api/games/:id/setup?div=&g2=` | rosters (with HTO player ids), infractions, current finals |
| POST | `/api/games/:id/lease` | `{action:"acquire"|"renew"|"release",leaseId?,ttlMs?}` |
| POST | `/api/games/:id/sync` | `{username,leaseId,comparisonToken,scoreSummary[],penaltySummary[]}` → compare then replace |

Captain routes require the configured `GAME_CODE_PEPPER`, `GameCodeRegistry`
binding, exact configured `Origin`, and `X-Game-Code`. `APP_TOKEN` remains only
for administrator code-management routes. The redeemed code subject supplies
lease identity; the captain does not send an operator label. Missing or
mismatched configuration/origin fails before protected routing and never emits
wildcard CORS. Stable authorization reasons are `code_required`, `code_invalid`,
`code_expired`, `code_revoked`, `wrong_game`, and `code_locked` (HTTP 429 for
lockout).

Schedule and setup carry a `seasonMapId`; sync refuses a schedule/setup/roster
mismatch. The map is configured in `worker/wrangler.toml` and must be changed
deliberately when the league season mapping changes.

Sync validates ownership and freshly reads the authoritative event arrays before
either upstream replacement. Wrong owner, expired or missing lease, missing
baseline, and remote drift return structured conflicts with zero upstream writes.
Production arbitration uses one `GameLease` Durable Object per exact game; it does
not pretend eventually consistent KV is atomic.

## Known prototype limitations / next steps
- **Resume mid-game:** `setup` imports the authoritative goal and penalty arrays and
  exposes a comparison token before any replacement is allowed.
- **Auth:** `APP_TOKEN` is administrator-only. Captains use exact-game codes;
  expired, revoked, wrong-game, and locked codes leave offline events pending
  and require a replacement code or retry after lockout.
- **Game status (in-progress / final):** intentionally out of scope. On the site this
  isn't an AJAX action — it toggles `#inProgress` and submits the full score form
  (and `pre` *clears* the game). Wire it in v2 via the full-form POST, computing the
  per-period line score from the sync response's `scoreInfo`. For now, mark a game
  Final in HomeTeamsOnline directly if needed (scores/penalties still sync fine).
- **Icons:** add `web/icons/icon-192.png` and `icon-512.png` for a polished install.
- Team→division map in `worker/src/index.js` (`TEAMS`) is league/season-specific —
  update it each season.

## Corrections and recovery (T5)

Events are checked before capture and again on recovery import: period and clock
bounds, selected-team roster membership, scorer/assist uniqueness, duplicate
events, penalty served-by membership, and infraction severity/duration must all
match the loaded setup. Existing events have an explicit Edit action; deletion
creates a new local revision and exposes an eight-second Undo window. Every game
open confirms the displayed date, time, rink, away/home order, and game ID before
authoritative import or editing.

The scoring screen can export a versioned `aahl-scoresheet-recovery` JSON file.
Import requires the exact same game identity, validates both arrays, and rejects
an equal or older revision, so it cannot cross games or silently replace newer
local work. Imported and corrected events use the same per-game sync queue.
