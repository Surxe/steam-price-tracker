#!/usr/bin/env bash
#
# Refresh Steam prices, then commit the resulting data/ changes locally.
#
# This is the entrypoint the login/resume systemd unit runs (see the README,
# "Auto-refresh prices on login"). It does three things in order:
#
#   1. wait for the network (the machine may not be online yet at login),
#   2. run the tracker, which rewrites data/*.json under today's date,
#   3. commit those data/ changes locally if anything changed.
#
# Why the commit: data/prices.json (and apps.json / alert_state.json) are
# tracked. A refresh mutates them but nothing committed the result, so every run
# left the working tree dirty. That accumulated diff is a hazard — a later
# checkout/stash/rebase, or a hand edit made against an already-dirty tree, can
# silently drop a captured price. Committing right after each refresh keeps the
# tree clean so a "faulty git status" can't corrupt a change. Mirrors the
# local-commit-if-changed pattern the `todo` repo uses for its store.
#
# Local only: it never pushes and never needs auth. The commit runs as whoever
# triggered the refresh; the repo is group-writable by `developers` (setgid), so
# both dev and ethan can write data/ and commit here.
set -euo pipefail

REPO="${STEAM_TRACKER_REPO:-/srv/dev/repos/steam-price-tracker}"
PING_HOST="${STEAM_TRACKER_PING_HOST:-store.steampowered.com}"
PYTHON="${STEAM_TRACKER_PYTHON:-$REPO/.venv/bin/python}"

cd "$REPO"

# Wait for the network before hitting the Steam API. Bounded so a permanently
# offline boot doesn't hang the unit forever.
tries=0
until ping -c1 -W1 "$PING_HOST" >/dev/null 2>&1; do
    tries=$((tries + 1))
    [ "$tries" -ge 60 ] && { echo "network still down after ${tries}s; giving up" >&2; exit 1; }
    sleep 2
done

# Refresh every id in TRACKED_APP_IDS (any extra args pass through to the CLI).
"$PYTHON" -m steam_price_tracker "$@"

# Commit the data/ changes locally if anything actually changed. Best-effort:
# never let a git hiccup fail the refresh that already succeeded above.
commit_data() {
    git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || return 0
    git -C "$REPO" add data 2>/dev/null || return 0
    git -C "$REPO" diff --cached --quiet -- data 2>/dev/null && return 0
    git -C "$REPO" commit -q -m "refresh prices $(date -Iseconds)" -- data 2>/dev/null || true
}
commit_data
