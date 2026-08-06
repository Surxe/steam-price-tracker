# Steam Price Tracker

Fetches **US** pricing for Steam apps from Steam's storefront JSON endpoint and
builds a **per-day price history** keyed by app id, plus a separate store of
app metadata (product name).

## Design

The package is split into single-responsibility, injectable collaborators:

| Module         | Responsibility                                                        |
| -------------- | --------------------------------------------------------------------- |
| `models.py`    | `PriceOverview`, `PriceRecord`, `AppInfo`, `SearchResult` — domain data |
| `client.py`    | `PriceSource` / `AppInfoSource` / `AppSearchSource` / `StoreFront` (ABCs) → `SteamStoreClient` |
| `storage.py`   | `PriceStore` → `JsonPriceStore`, `AppInfoStore` → `JsonAppInfoStore`   |
| `tracker.py`   | `PriceTracker` — orchestrates source + stores, fires alerts            |
| `alerts.py`    | `Alerter` (ABC) → `ConsoleAlerter` — alert delivery strategy           |
| `search.py`    | search-by-name + Markdown/JSON rendering (CLI)                         |
| `registry.py`  | programmatic read/edit of `TRACKED_APP_IDS` (CLI)                      |
| `config.py`    | `TRACKED_APP_IDS`, `STORE_PATH`, `APP_INFO_PATH` — user settings       |
| `__main__.py`  | price-update CLI                                                       |

The sources and stores are all abstract, so you can drop in a fake for tests,
another region, or a database-backed store without touching the tracker.

## Data layout

**`data/prices.json`** — price history, keyed by app id → date (`YYYY-MM-DD`,
UTC). One entry per calendar day; a same-day re-run overwrites that day.

```json
{
  "2399830": {
    "2026-08-04": {
      "fetched_at": "2026-08-04T23:09:07+00:00",
      "price_overview": { "currency": "USD", "final": 4499, "final_formatted": "$44.99", ... }
    }
  }
}
```

**`data/apps.json`** — app metadata, keyed by app id. Fetched once the first
time an app is priced, then never re-queried (staleness is acceptable).

```json
{ "2399830": { "name": "ARK: Survival Ascended", "fetched_at": "..." } }
```

## Setup

The package runs on the standard library alone, but tests use `pytest`. Create a
project virtualenv and install the dev dependencies into it:

```bash
cd /srv/dev/repos/steam-price-tracker
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

`.venv/` is gitignored. Use `.venv/bin/python` for everything below (or
`source .venv/bin/activate` once per shell so `python`/`pytest` resolve there).
The system Python won't have `pytest` — it blocks `pip` under PEP 668 — so always
go through the venv for this repo.

## Usage

```bash
# Update every id in config.TRACKED_APP_IDS
.venv/bin/python -m steam_price_tracker

# Update specific ids
.venv/bin/python -m steam_price_tracker 2399830 730
```

```python
from steam_price_tracker import PriceTracker

tracker = PriceTracker()
record = tracker.update(2399830)          # fetches metadata too, if new
print(record.price.final_amount)          # 44.99
print(tracker.store.get_history(2399830)) # {date: PriceRecord, ...}
print(tracker.info_store.get(2399830).name)  # "ARK: Survival Ascended"
```

## Adding more apps

Three ways, easiest first:

**1. The `/add-app` skill (recommended).** From a Claude Code session in this
repo, run `/add-app <game name>`. It searches Steam, shows you the matches, and
registers the id you pick. See `.claude/skills/add-app/SKILL.md`.

**2. Search + register CLIs** (what the skill drives):

```bash
# find candidate app ids by name (Markdown table; --format json for machine use)
.venv/bin/python -m steam_price_tracker.search "ark survival"

# register a chosen id (idempotent); --name is stored as an inline comment
.venv/bin/python -m steam_price_tracker.registry add 346110 --name "ARK: Survival Evolved"

# list currently-registered ids
.venv/bin/python -m steam_price_tracker.registry list
```

**3. By hand.** Append ids to `TRACKED_APP_IDS` in `steam_price_tracker/config.py`.

In all cases the product name is fetched automatically the first time each new
app is priced.

## Price alerts

Each app can have an optional **USD price-alert threshold**. On every refresh, if
an app's current price is **at or below** its threshold, an alert fires. This
per-app threshold is the reason to use this over a Steam wishlist, which has no
per-item target price.

Thresholds live in `ALERT_THRESHOLDS` in `config.py` and are managed via the
registry (or supplied when adding an app):

```bash
# set / change a threshold (USD)
.venv/bin/python -m steam_price_tracker.registry set-threshold 2399830 30

# or when registering a new app
.venv/bin/python -m steam_price_tracker.registry add 2399830 --name "ARK: Survival Ascended" --threshold 30
```

Delivery is a swappable strategy (`Alerter`). `ConsoleAlerter` prints every
alert (into the journal under the login service); `EmailAlerter` sends email (see
below); `CompositeAlerter` runs several at once. Alerts fire as a **batch** per
refresh, so a whole run's alerts arrive as one message rather than one-per-app.

## Email alerts

When SMTP credentials are present, a refresh sends **one digest email** listing
every app at/below threshold, from a Gmail account via an **App Password**. To
avoid spamming (the refresh runs on every login), email is **deduped to once per
app per UTC day** — the last-emailed date is tracked in
`data/alert_state.json`. Console alerts are not deduped.

### One-time: create a Gmail App Password

1. On the sending account (`surxe.developer@gmail.com`), enable **2-Step
   Verification** (required for App Passwords).
2. Google Account → Security → **App passwords** → generate one (app: "Mail") and
   copy the 16 characters (shown once).

### Provide credentials via environment (never committed)

Email turns on only when **both** of these are set; presence of the creds is the
enable switch. Recipient defaults to `EMAIL_TO` in `config.py`
(`eethansur@gmail.com`).

```
STEAM_TRACKER_SMTP_USER=surxe.developer@gmail.com   # also the From address
STEAM_TRACKER_SMTP_PASSWORD=xxxxxxxxxxxxxxxx         # the 16-char App Password
STEAM_TRACKER_EMAIL_TO=eethansur@gmail.com           # optional override
```

Non-secret SMTP settings (`smtp.gmail.com:587`, STARTTLS) live in `config.py`.
Keep these vars out of the repo — `*.env` is gitignored, and the real file lives
in the running user's `~/.config` (see the login-service section).

### Validate the credentials

```bash
set -a; . ~/.config/steam-price-tracker/smtp.env; set +a
.venv/bin/python -m steam_price_tracker --test-email
```

Sends a canned alert to the recipient (bypassing dedup). On failure the SMTP
error prints — an auth rejection means the App Password or 2-Step Verification
needs attention. Adding email later for a new channel is just another `Alerter`
subclass passed to `PriceTracker(alerter=...)`.

## Tests

```bash
.venv/bin/python -m pytest
```

The tests use in-memory fakes and temp files, so they hit neither the network
nor the real `data/` stores.

## Auto-refresh prices on login

A `systemd` **user** service refreshes prices whenever the user logs in. Because
the service must live under a specific user's home (`~/.config/systemd/user/`),
it is installed per-user by that user — it is not part of the repo.

Create `~/.config/systemd/user/steam-price-refresh.service`:

```ini
[Unit]
Description=Refresh Steam prices on login
After=graphical-session.target

[Service]
Type=oneshot
WorkingDirectory=/srv/dev/repos/steam-price-tracker
# SMTP credentials for email alerts (see "Email alerts"). Optional: omit the
# line if you only want console/journal alerts. `-` = tolerate a missing file.
EnvironmentFile=-%h/.config/steam-price-tracker/smtp.env
# Wait for the network, then update every id in TRACKED_APP_IDS.
ExecStart=/bin/bash -lc 'until ping -c1 -W1 store.steampowered.com >/dev/null 2>&1; do sleep 2; done; exec .venv/bin/python -m steam_price_tracker'

[Install]
WantedBy=default.target
```

For email alerts, create the referenced env file (owned by this user, secret):

```bash
mkdir -p ~/.config/steam-price-tracker
cat > ~/.config/steam-price-tracker/smtp.env <<'EOF'
STEAM_TRACKER_SMTP_USER=surxe.developer@gmail.com
STEAM_TRACKER_SMTP_PASSWORD=xxxxxxxxxxxxxxxx
EOF
chmod 600 ~/.config/steam-price-tracker/smtp.env
```

Enable it (runs on every subsequent login; `--now` also runs it immediately):

```bash
systemctl --user daemon-reload
systemctl --user enable --now steam-price-refresh.service

# check the last run
systemctl --user status steam-price-refresh.service
journalctl --user -u steam-price-refresh.service -n 20
```

Notes:

- The `ping` guard handles the network not being up yet at login. Prices land in
  `data/prices.json` under today's date (a second run the same day just
  overwrites that day's entry).
- The repo is group-writable by `developers` (setgid), so any user in that group
  can run the tracker and write to `data/`. Files that user creates are owned by
  them but stay group `developers`.

### When exactly does it run?

The trigger is subtler than "on login." `WantedBy=default.target` ties the
refresh to your **user session manager** (`systemd --user`) reaching
`default.target`. Without [lingering](#lingering) that manager **starts when you
go from zero sessions to one**, and **stops when your last session ends**. So the
`Type=oneshot` refresh fires exactly once each time your user session manager
(re)starts — not at boot, and not when an existing session merely wakes up.

Concretely:

| Event | Runs? | Why |
| ----- | ----- | --- |
| Cold boot → your first login | ✅ | 0→1 session starts `systemd --user` → `default.target` |
| Reboot → login | ✅ | same as cold boot |
| Full **logout**, then log back in | ✅ | last session ended stopped the manager; new login restarts it |
| **Resume from suspend** (sleep to RAM) | ❌ | your session never ended — the manager kept running |
| **Resume from hibernate** (sleep to disk) | ❌ | session is restored, not recreated |
| **Unlock** screen / screensaver off | ❌ | no new session |
| Log in a **2nd** time while already logged in elsewhere | ❌ | manager already running; `default.target` isn't re-reached |
| SSH / console login (when you had no other session) | ✅ | any session type starts the user manager |

Mental model: **it runs on a fresh login from a logged-out state (boot, reboot,
or after a full logout) — not on resume, unlock, or an additional concurrent
session.** The common surprise is sleep/wake: that keeps your session alive, so
the refresh does **not** re-run.

Check the last run and its time:

```bash
systemctl --user status steam-price-refresh.service   # look for "Deactivated successfully" + timestamp
journalctl --user -u steam-price-refresh.service -n 20
```

<a id="lingering"></a>
**Lingering changes this.** If `loginctl enable-linger $USER` is set, `systemd
--user` starts at **boot** and stays up until shutdown regardless of logins — so
the refresh runs **once at boot** and **not** on subsequent logins. This service
assumes lingering is **off** (the default), giving the per-login behavior above.

**Want it on resume-from-sleep too?** That's a separate trigger — a small
user service that watches logind's `PrepareForSleep` D-Bus signal (a `gdbus
monitor` loop), or a `systemd --user` timer for periodic refreshes independent of
sessions. Ask if you want either wired up.

## Notes

- Uses only the Python standard library (`urllib`) — no runtime dependencies.
- The Steam endpoint is undocumented and rate-limited (~200 req / 5 min / IP).
- Apps with no US price (free / unreleased / region-locked) raise
  `PriceUnavailableError` and are skipped in batch updates.
