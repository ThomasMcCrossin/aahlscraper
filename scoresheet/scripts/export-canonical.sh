#!/usr/bin/env bash
set -euo pipefail

# Manual operator helper. Arguments are explicit: worker base URL, exact
# allowed Origin, and output directory. APP_TOKEN is read from the environment.
BASE_URL="${1:?usage: $0 BASE_URL ORIGIN OUTPUT_DIR}"
ORIGIN="${2:?usage: $0 BASE_URL ORIGIN OUTPUT_DIR}"
OUTPUT_DIR="${3:?usage: $0 BASE_URL ORIGIN OUTPUT_DIR}"
: "${APP_TOKEN:?APP_TOKEN must be set in the environment}"
umask 077

case "$BASE_URL" in http://*|https://*) ;; *) echo "BASE_URL must be http(s)" >&2; exit 2 ;; esac
case "$ORIGIN" in http://*|https://*) ;; *) echo "ORIGIN must be http(s)" >&2; exit 2 ;; esac
mkdir -p -- "$OUTPUT_DIR"
date_stamp="$(date -u +%F)"
destination="$OUTPUT_DIR/canonical-export-$date_stamp.json"
temporary="$(mktemp "$OUTPUT_DIR/.canonical-export.XXXXXX")"
trap 'rm -f -- "$temporary"' EXIT

curl --fail --silent --show-error --proto '=https,http' \
  --header "Origin: $ORIGIN" \
  --header "X-App-Token: $APP_TOKEN" \
  --header 'Accept: application/json' \
  "$BASE_URL/api/admin/canonical-export" >"$temporary"
test -s "$temporary"
mv -f -- "$temporary" "$destination"
trap - EXIT
echo "$destination"
