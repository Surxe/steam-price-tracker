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
| `tracker.py`   | `PriceTracker` — orchestrates source + stores                          |
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

## Tests

```bash
.venv/bin/python -m pytest
```

The tests use in-memory fakes and temp files, so they hit neither the network
nor the real `data/` stores.

## Notes

- Uses only the Python standard library (`urllib`) — no runtime dependencies.
- The Steam endpoint is undocumented and rate-limited (~200 req / 5 min / IP).
- Apps with no US price (free / unreleased / region-locked) raise
  `PriceUnavailableError` and are skipped in batch updates.
