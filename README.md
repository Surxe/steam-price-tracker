# Steam Price Tracker

Fetches **US** pricing for Steam apps from Steam's storefront JSON endpoint and
stores each result in a JSON file keyed by app id.

## Design

The package is split into single-responsibility, injectable collaborators:

| Module         | Responsibility                                             |
| -------------- | ---------------------------------------------------------- |
| `models.py`    | `PriceOverview`, `PriceRecord` — immutable domain data     |
| `client.py`    | `PriceSource` (ABC) → `SteamStoreClient` — fetch + parse   |
| `storage.py`   | `PriceStore` (ABC) → `JsonPriceStore` — persistence        |
| `tracker.py`   | `PriceTracker` — orchestrates source + store               |
| `config.py`    | `TRACKED_APP_IDS`, `STORE_PATH` — user-editable settings   |
| `__main__.py`  | CLI                                                        |

Both `PriceSource` and `PriceStore` are abstract, so you can drop in a fake for
tests, another region, or a database-backed store without touching the tracker.

## Usage

```bash
# Update every id in config.TRACKED_APP_IDS
python -m steam_price_tracker

# Update specific ids
python -m steam_price_tracker 2399830 730
```

```python
from steam_price_tracker import PriceTracker

record = PriceTracker().update(2399830)
print(record.price.final_amount)   # 44.99
```

## Adding more apps

Append ids to `TRACKED_APP_IDS` in `steam_price_tracker/config.py`.

## Notes

- Uses only the Python standard library (`urllib`) — no dependencies.
- The Steam endpoint is undocumented and rate-limited (~200 req / 5 min / IP).
- Apps with no US price (free / unreleased / region-locked) raise
  `PriceUnavailableError` and are skipped in batch updates.
