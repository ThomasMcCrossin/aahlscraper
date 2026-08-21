# Scoresheet game-night fallback

If the scoresheet says sync failed, stop retrying if it is unclear what was
published. Nothing should be lost: keep the phone and its event list, and use
native HTO entry for the game. The canonical record is captured before HTO
publication whenever storage is healthy. Tell the operator the game number and
the error shown.

The operator can revoke a leaked or unusable game code, then issue a new one.
Keep codes private; never paste a token, password, or secret into a ticket or
chat. If a phone is lost, revoke its code before reissuing.

Before game night, an operator may run the read-only checks from a shell:

    curl --fail --header "Origin: https://YOUR-ORIGIN" --header "X-App-Token: $APP_TOKEN" https://YOUR-WORKER/api/admin/markup-canary
    curl --fail --header "Origin: https://YOUR-ORIGIN" --header "X-App-Token: $APP_TOKEN" https://YOUR-WORKER/api/admin/diagnostics

The markup canary is manual and read-only. Diagnostics reports names and
presence booleans, not secret values. Take a backup manually with:

    scoresheet/scripts/export-canonical.sh https://YOUR-WORKER https://YOUR-ORIGIN ./backups

The helper reads `APP_TOKEN` from the environment and writes a dated
`canonical-export-YYYY-MM-DD.json` file. Do not put the token in the command
line.

If the message is `season_map_drift`, do not force a sync. The season map must
be rebuilt/configured by the operator before using the scoresheet again.
