"""User-editable configuration.

Add more app ids here as the set of tracked games grows.
"""
from __future__ import annotations

# Steam app ids to track. 2399830 = ARK: Survival Ascended.
TRACKED_APP_IDS: list[int] = [
    2399830,
]

# Where the JSON stores live, relative to the repo root.
STORE_PATH = "data/prices.json"       # price history, keyed by app id -> date
APP_INFO_PATH = "data/apps.json"      # app metadata (name, ...), keyed by app id

# Per-app price-alert thresholds, in USD. An alert fires on refresh when an
# app's current price is at or below its threshold. Apps absent here are not
# alerted. Managed via `python -m steam_price_tracker.registry`.
ALERT_THRESHOLDS: dict[int, float] = {}
