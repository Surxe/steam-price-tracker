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
| `registry.py`  | programmatic read/edit of the tracked-apps file (CLI)                  |
| `options_schema.py` | the OptionsConfig schema — one typed entry per setting            |
| `config.py`    | resolves settings (args/env/defaults) + reads the tracked-apps file   |
| `__main__.py`  | price-update CLI                                                       |

Settings are managed with [OptionsConfig](https://github.com/Surxe/OptionsConfig):
the schema in `options_schema.py` is the single source of truth for every
setting, its CLI flag, its `STEAM_TRACKER_*` environment variable, and the
generated `.env.example` / [Configuration](#configuration) docs.

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

**`data/tracked_apps.json`** — the set of tracked apps and their optional USD
alert thresholds, keyed by app id. `name` is a human label (the authoritative
name lives in `apps.json`); a missing/`null` `threshold` means "tracked, but
never alert". Edited by the [registry CLI](#adding-more-apps).

```json
{ "2399830": { "name": "ARK: Survival Ascended", "threshold": 20.0 } }
```

The whole `data/` directory is **gitignored** — it is per-machine runtime state
(your prices, your tracked list), not source. A fresh clone starts with no
tracked apps; add them with the registry (below).

## Setup

The runtime dependency is [OptionsConfig](https://github.com/Surxe/OptionsConfig)
(settings management); tests also use `pytest`. Create a project virtualenv and
install the dev dependencies (which include the runtime ones) into it:

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
# Update every id in the tracked-apps file (data/tracked_apps.json)
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

## Configuration

Settings are managed with [OptionsConfig](https://github.com/Surxe/OptionsConfig).
Each setting can be supplied three ways, highest priority first:

1. a **CLI flag** — e.g. `--store-path data/prices.json`;
2. an **environment variable** (or a line in an untracked `.env` at the repo
   root) — e.g. `STEAM_TRACKER_STORE_PATH=data/prices.json`;
3. otherwise the **default** below.

Copy `.env.example` to `.env` and edit it to set values via the environment.
The reference below — and `.env.example` — are generated from the schema in
`steam_price_tracker/options_schema.py`; after editing that schema, regenerate
them with:

```bash
.venv/bin/python build.py
```

> **On this deployment**, the non-secret settings and the tracked-apps file are
> owned by [my-system](https://github.com/Surxe/my-system) and deployed to
> `~/.config/steam-price-tracker/` (`options.conf` + `tracked_apps.json`); the
> refresh service loads them via its unit's `EnvironmentFile`. Secrets stay in
> the gitignored `smtp.env`. Edit the tracked list through the `/add-app` skill
> (it targets the my-system source), then commit there and re-run `install.sh`.
> `data/` in this repo holds only generated price/metadata output.

<!-- BEGIN_GENERATED_OPTIONS -->
#### Storage

* **STEAM_TRACKER_STORE_PATH** - JSON file for the per-day price history, keyed by app id then date.
  - Default: `"data/prices.json"`
  - Command line: `--store-path`

* **STEAM_TRACKER_APP_INFO_PATH** - JSON file for app metadata (product name), keyed by app id.
  - Default: `"data/apps.json"`
  - Command line: `--app-info-path`

* **STEAM_TRACKER_ALERT_STATE_PATH** - JSON file recording the last date each app was emailed (email dedup).
  - Default: `"data/alert_state.json"`
  - Command line: `--alert-state-path`

* **STEAM_TRACKER_APPS_PATH** - JSON file of tracked apps and their optional USD alert thresholds, keyed by app id. Edited by the registry CLI.
  - Example: `"data/tracked_apps.json"`
  - Default: `"data/tracked_apps.json"`
  - Command line: `--apps-path`


#### Email alerts

* **STEAM_TRACKER_EMAIL_TO** - Recipient address for price-alert digest emails. Treated as a secret (a personal address): supply it via the environment / the gitignored smtp.env alongside the SMTP credentials, never a committed file. Required for email — without it (or the SMTP credentials) email stays off and only console alerts are used.
  - Default: None
  - Command line: `--email-to`

* **STEAM_TRACKER_SMTP_HOST** - SMTP server host used to send alert emails.
  - Default: `"smtp.gmail.com"`
  - Command line: `--smtp-host`

* **STEAM_TRACKER_SMTP_PORT** - SMTP server port (587 = STARTTLS).
  - Default: `"587"`
  - Command line: `--smtp-port`

* **STEAM_TRACKER_SMTP_USER** - SMTP account to authenticate as, also the From address. Email is enabled only when SMTP_USER, SMTP_PASSWORD, and EMAIL_TO are all set.
  - Default: None
  - Command line: `--smtp-user`
  - For Gmail this is the sending account; pair it with a 16-character App Password in SMTP_PASSWORD (see the Email alerts section).

* **STEAM_TRACKER_SMTP_PASSWORD** - SMTP password (a Gmail App Password). Keep this out of the repo; supply it via the environment or an untracked .env file.
  - Default: None
  - Command line: `--smtp-password`


<!-- END_GENERATED_OPTIONS -->

## Adding more apps

Three ways, easiest first:

**1. The `/add-app` skill (recommended).** From a Claude Code session in this
repo, run `/add-app <game name>`. It searches Steam, shows you the matches, and
registers the id you pick. See `.claude/skills/add-app/SKILL.md`.

**2. Search + register CLIs** (what the skill drives):

```bash
# find candidate app ids by name (Markdown table; --format json for machine use)
.venv/bin/python -m steam_price_tracker.search "ark survival"

# register a chosen id (idempotent); --name is stored alongside the id
.venv/bin/python -m steam_price_tracker.registry add 346110 --name "ARK: Survival Evolved"

# list currently-registered ids
.venv/bin/python -m steam_price_tracker.registry list
```

**3. By hand.** Add a key to `data/tracked_apps.json` (created on first
registry write): `"346110": {"name": "ARK: Survival Evolved", "threshold": 15.0}`.
`threshold` is optional.

In all cases the product name is fetched automatically the first time each new
app is priced.

## Price alerts

Each app can have an optional **USD price-alert threshold**. On every refresh, if
an app's current price is **at or below** its threshold, an alert fires. This
per-app threshold is the reason to use this over a Steam wishlist, which has no
per-item target price.

Thresholds live in the tracked-apps file (`data/tracked_apps.json`) and are
managed via the registry (or supplied when adding an app):

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

`SMTP_USER`, `SMTP_PASSWORD`, and `EMAIL_TO` are all treated as secrets (the
recipient is a personal address), so they have no committed defaults and are
supplied via the environment — not a tracked file. Email turns on only when
**all three** are set; otherwise the tracker just fetches prices and uses console
alerts.

```
STEAM_TRACKER_SMTP_USER=your.sender@gmail.com        # also the From address
STEAM_TRACKER_SMTP_PASSWORD=xxxxxxxxxxxxxxxx          # the 16-char App Password
STEAM_TRACKER_EMAIL_TO=your.recipient@example.com     # alert recipient
```

Non-secret SMTP settings (`SMTP_HOST`/`SMTP_PORT`, default `smtp.gmail.com:587`
STARTTLS) have defaults in the schema and rarely need changing. Keep the secret
vars out of the repo — `*.env` is gitignored, and the real file lives in the
running user's `~/.config/steam-price-tracker/smtp.env` (deployed by my-system;
see [Auto-refresh prices on login](#auto-refresh-prices-on-login)).

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

This repo is just the tracker. The auto-refresh wiring — a `systemd --user`
oneshot that runs on login, plus a resume-from-sleep watcher — is owned and
deployed by [my-system](https://github.com/Surxe/my-system) through its
`install.sh`, not by this repo. The deployed units live at
`~/.config/systemd/user/steam-price-refresh{,-resume-watch}.service` and call the
review-gated wrappers in `~/.local/bin/` (sources:
`users/ethan/localbin/steam-price-refresh` and `steam-price-resume-watch` in
my-system). Those wrappers wait for connectivity, then run the CLI below — so
there is nothing tracker-side to install for auto-refresh.

To run a refresh yourself (exactly what the units ultimately call):

```bash
.venv/bin/python -m steam_price_tracker
```

Credentials come from the unit's `EnvironmentFile` (`~/.config/steam-price-tracker/smtp.env`);
see [Email alerts](#email-alerts).

## Notes

- Steam access uses only the Python standard library (`urllib`); the sole runtime
  dependency is `optionsconfig` (settings management).
- The Steam endpoint is undocumented and rate-limited (~200 req / 5 min / IP).
- Apps with no US price (free / unreleased / region-locked) raise
  `PriceUnavailableError` and are skipped in batch updates.
