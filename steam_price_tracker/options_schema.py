"""OptionsConfig schema for the Steam price tracker.

Every user-tunable setting lives here as a single typed option. OptionsConfig
resolves each one from (in priority order) a CLI argument, then an environment
variable / ``.env`` entry, then the ``default`` below, and also drives the
generated ``.env.example`` and the README's Configuration section (run
``python build.py`` after editing this file).

The *set* of tracked apps and their per-app alert thresholds is deliberately
NOT here: that is variable-length, per-app data edited by the ``registry`` CLI,
so it lives in a separate JSON file whose path is the ``APPS_PATH`` option.
"""
from __future__ import annotations

OPTIONS_SCHEMA = {
    # ---------------------------- Storage ------------------------------- #
    "STORE_PATH": {
        "env": "STEAM_TRACKER_STORE_PATH",
        "arg": "--store-path",
        "type": str,
        "default": "data/prices.json",
        "section": "Storage",
        "help": "JSON file for the per-day price history, keyed by app id then date.",
    },
    "APP_INFO_PATH": {
        "env": "STEAM_TRACKER_APP_INFO_PATH",
        "arg": "--app-info-path",
        "type": str,
        "default": "data/apps.json",
        "section": "Storage",
        "help": "JSON file for app metadata (product name), keyed by app id.",
    },
    "ALERT_STATE_PATH": {
        "env": "STEAM_TRACKER_ALERT_STATE_PATH",
        "arg": "--alert-state-path",
        "type": str,
        "default": "data/alert_state.json",
        "section": "Storage",
        "help": "JSON file recording the last date each app was emailed (email dedup).",
    },
    "APPS_PATH": {
        "env": "STEAM_TRACKER_APPS_PATH",
        "arg": "--apps-path",
        "type": str,
        "default": "data/tracked_apps.json",
        "section": "Storage",
        "help": (
            "JSON file of tracked apps and their optional USD alert thresholds, "
            "keyed by app id. Edited by the registry CLI."
        ),
        "example": "data/tracked_apps.json",
    },
    # -------------------------- Email alerts ---------------------------- #
    "EMAIL_TO": {
        "env": "STEAM_TRACKER_EMAIL_TO",
        "arg": "--email-to",
        "type": str,
        "default": None,
        "section": "Email alerts",
        "sensitive": True,
        "help": (
            "Recipient address for price-alert digest emails. Treated as a "
            "secret (a personal address): supply it via the environment / the "
            "gitignored smtp.env alongside the SMTP credentials, never a "
            "committed file. Required for email — without it (or the SMTP "
            "credentials) email stays off and only console alerts are used."
        ),
    },
    "SMTP_HOST": {
        "env": "STEAM_TRACKER_SMTP_HOST",
        "arg": "--smtp-host",
        "type": str,
        "default": "smtp.gmail.com",
        "section": "Email alerts",
        "help": "SMTP server host used to send alert emails.",
    },
    "SMTP_PORT": {
        "env": "STEAM_TRACKER_SMTP_PORT",
        "arg": "--smtp-port",
        "type": int,
        "default": 587,
        "section": "Email alerts",
        "help": "SMTP server port (587 = STARTTLS).",
    },
    "SMTP_USER": {
        "env": "STEAM_TRACKER_SMTP_USER",
        "arg": "--smtp-user",
        "type": str,
        "default": None,
        "section": "Email alerts",
        "sensitive": True,
        "help": (
            "SMTP account to authenticate as, also the From address. Email is "
            "enabled only when SMTP_USER, SMTP_PASSWORD, and EMAIL_TO are all set."
        ),
        "help_extended": (
            "For Gmail this is the sending account; pair it with a 16-character "
            "App Password in SMTP_PASSWORD (see the Email alerts section)."
        ),
    },
    "SMTP_PASSWORD": {
        "env": "STEAM_TRACKER_SMTP_PASSWORD",
        "arg": "--smtp-password",
        "type": str,
        "default": None,
        "section": "Email alerts",
        "sensitive": True,
        "help": (
            "SMTP password (a Gmail App Password). Keep this out of the repo; "
            "supply it via the environment or an untracked .env file."
        ),
    },
}
