"""User-editable configuration.

Add more app ids here as the set of tracked games grows.
"""
from __future__ import annotations

# Steam app ids to track. 2399830 = ARK: Survival Ascended.
TRACKED_APP_IDS: list[int] = [
    2399830,
]

# Where the JSON price store lives, relative to the repo root.
STORE_PATH = "data/prices.json"
