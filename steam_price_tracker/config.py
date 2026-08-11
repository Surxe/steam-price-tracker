"""User-editable configuration.

Add more app ids here as the set of tracked games grows.
"""
from __future__ import annotations

# Steam app ids to track. 2399830 = ARK: Survival Ascended.
TRACKED_APP_IDS: list[int] = [
    2399830,
    1771300,  # Kingdom Come: Deliverance II
    1903340,  # Clair Obscur: Expedition 33
    1203620,  # Enshrouded
    1295660,  # Sid Meier's Civilization VII
    2246340,  # Monster Hunter Wilds
]

# Where the JSON stores live, relative to the repo root.
STORE_PATH = "data/prices.json"       # price history, keyed by app id -> date
APP_INFO_PATH = "data/apps.json"      # app metadata (name, ...), keyed by app id
ALERT_STATE_PATH = "data/alert_state.json"  # last-emailed date per app (dedup)

# Per-app price-alert thresholds, in USD. An alert fires on refresh when an
# app's current price is at or below its threshold. Apps absent here are not
# alerted. Managed via `python -m steam_price_tracker.registry`.
ALERT_THRESHOLDS: dict[int, float] = {
    2399830: 20.0,  # ARK: Survival Ascended
    1771300: 25.0,  # Kingdom Come: Deliverance II
    1903340: 25.0,  # Clair Obscur: Expedition 33
    1203620: 13.0,  # Enshrouded
    1295660: 25.0,  # Sid Meier's Civilization VII
    2246340: 20.0,  # Monster Hunter Wilds
}

# Email alert delivery (Gmail SMTP + App Password). Non-secret settings only.
# The sender address and 16-char App Password are supplied at runtime via the
# STEAM_TRACKER_SMTP_USER / STEAM_TRACKER_SMTP_PASSWORD environment variables
# (never committed). Email is enabled only when both are present.
EMAIL_TO = "eethansur@gmail.com"      # recipient (override: STEAM_TRACKER_EMAIL_TO)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587                       # STARTTLS
