#!/usr/bin/env bash
#
# Re-run the price refresh each time the system RESUMES from sleep (suspend or
# hibernate). The login systemd unit only fires on a fresh login, so a machine
# that just sleeps/wakes never re-checks prices — this closes that gap.
#
# How it works: logind broadcasts a `PrepareForSleep` signal on the system bus.
# The argument is `true` when going to sleep and `false` when resuming. We watch
# for the `false` edge and trigger the existing oneshot refresh unit, reusing its
# network guard and SMTP EnvironmentFile — no refresh logic is duplicated here.
#
# Meant to be run as a long-lived `systemd --user` service (see the README,
# "Also refresh on resume from sleep"). It blocks forever monitoring the bus.
set -euo pipefail

REFRESH_UNIT="${STEAM_REFRESH_UNIT:-steam-price-refresh.service}"

# `gdbus monitor` emits one line per signal, e.g.:
#   /org/freedesktop/login1: org.freedesktop.login1.Manager.PrepareForSleep (false,)
# `(false,)` = resuming. Kick the oneshot; it handles waiting for the network.
gdbus monitor --system \
  --dest org.freedesktop.login1 \
  --object-path /org/freedesktop/login1 \
| while read -r line; do
    case "$line" in
      *PrepareForSleep*'(false,)'*)
        systemctl --user start "$REFRESH_UNIT"
        ;;
    esac
  done
