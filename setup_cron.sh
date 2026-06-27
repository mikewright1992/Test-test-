#!/usr/bin/env bash
# Installs the crontab line that runs dca_runner.py on weekdays at 10:30am
# US/Eastern. Run this once on the machine that will actually execute the
# trades (your own computer or server) — NOT inside a Claude Code session,
# since that container does not persist.
#
# Safe to re-run: it replaces any previous line tagged with the same marker
# instead of adding a duplicate.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER="# dca_runner.py (auto-installed by setup_cron.sh)"
PYTHON_BIN="$(command -v python3)"

if [ -z "$PYTHON_BIN" ]; then
  echo "python3 not found on PATH" >&2
  exit 1
fi

TZ_NAME="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
if [ "$TZ_NAME" != "America/New_York" ]; then
  echo "WARNING: system timezone is '${TZ_NAME:-unknown}', not America/New_York."
  echo "The cron line below assumes the server clock is US/Eastern. If it isn't,"
  echo "adjust the hour (30 10) to match 10:30am ET in your local timezone, or"
  echo "set CRON_TZ=America/New_York (supported by some cron implementations,"
  echo "e.g. Vixie cron / cronie) by adding a 'CRON_TZ=America/New_York' line"
  echo "above the job in your crontab."
  echo
fi

CRON_LINE="30 10 * * 1-5 cd $REPO_DIR && $PYTHON_BIN dca_runner.py --live >> data/dca_cron.log 2>&1 $MARKER"

mkdir -p "$REPO_DIR/data"

EXISTING="$(crontab -l 2>/dev/null || true)"
FILTERED="$(printf '%s\n' "$EXISTING" | grep -vF "$MARKER" || true)"
NEW_CRONTAB="$(printf '%s\n%s\n' "$FILTERED" "$CRON_LINE" | sed '/^$/d')"

printf '%s\n' "$NEW_CRONTAB" | crontab -

echo "Installed crontab entry:"
echo "  $CRON_LINE"
echo
echo "Verify with: crontab -l"
echo "First run: do 'python3 dca_runner.py --dry-run' interactively once to clear"
echo "Robinhood's MFA challenge before relying on the scheduled job."
