"""CLI: ``python -m steam_price_tracker [app_id ...]``.

With no app ids it updates every id in the tracked-apps file. Storage paths and
SMTP/email settings are OptionsConfig options: pass them as ``--store-path`` etc.,
or via ``STEAM_TRACKER_*`` environment variables / a ``.env`` file (run
``python build.py`` to regenerate ``.env.example`` and the docs from the schema).
"""
from __future__ import annotations

import argparse
import sys

from optionsconfig import ArgumentWriter

from . import __version__, config
from .alerts import (
    Alerter,
    CompositeAlerter,
    ConsoleAlerter,
    EmailAlerter,
    EmailConfig,
    EphemeralAlertState,
)
from .models import PriceAlert, PriceOverview
from .storage import JsonAlertStateStore, JsonAppInfoStore
from .tracker import PriceTracker


def _build_alerter(options) -> Alerter:
    """Console alerts always; add email when SMTP credentials are present."""
    console = ConsoleAlerter()

    email_config = EmailConfig.from_options(options)
    if email_config is None:
        # Warn if email is partially configured so misconfiguration is not silent.
        if options.smtp_user or options.smtp_password or options.email_to:
            print(
                "Email disabled: set STEAM_TRACKER_SMTP_USER, "
                "STEAM_TRACKER_SMTP_PASSWORD, and STEAM_TRACKER_EMAIL_TO. "
                "Using console alerts only."
            )
        return console

    email = EmailAlerter(email_config, JsonAlertStateStore(options.alert_state_path))
    return CompositeAlerter([console, email])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steam_price_tracker",
        description="Fetch US Steam prices and email alerts for price drops.",
    )
    parser.add_argument(
        "app_ids",
        nargs="*",
        type=int,
        help="Steam app ids to update (default: the tracked-apps file).",
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="send a canned test alert to validate SMTP credentials, then exit",
    )
    parser.add_argument("--version", action="version", version=__version__)
    # Storage / email settings (--store-path, --smtp-*, ...) from the schema.
    ArgumentWriter().add_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    options = config.load_options(args)

    if args.test_email:
        return _send_test_email(options)

    app_ids = args.app_ids or config.tracked_app_ids()
    tracker = PriceTracker(
        info_store=JsonAppInfoStore(options.app_info_path),
        alerter=_build_alerter(options),
    )

    results = tracker.update_many(app_ids)
    for app_id, price in sorted(results.items()):
        info = tracker.info_store.get(app_id)
        name = info.name if info else str(app_id)
        if price.is_discounted:
            deal = (
                f"{price.final_formatted} "
                f"({price.discount_percent}% off {price.base_formatted})"
            )
        else:
            deal = price.final_formatted
        print(f"{app_id} {name}: {deal} ({price.currency})")

    # Non-zero exit if nothing succeeded.
    return 0 if results else 1


def _send_test_email(options) -> int:
    """Send a canned alert via SMTP to validate credentials (bypasses dedup)."""
    email_config = EmailConfig.from_options(options)
    if email_config is None:
        print(
            "Email is not configured: set STEAM_TRACKER_SMTP_USER, "
            "STEAM_TRACKER_SMTP_PASSWORD, and STEAM_TRACKER_EMAIL_TO."
        )
        return 1
    canned = PriceAlert(
        app_id=2399830,
        price=PriceOverview(
            currency="USD", initial=4499, final=4499,
            discount_percent=0, final_formatted="$44.99",
        ),
        threshold=50.0,
        name="ARK: Survival Ascended (test alert)",
    )
    ok = EmailAlerter(email_config, EphemeralAlertState()).try_send([canned])
    if ok:
        print(f"Test alert sent to {email_config.to_addr} (check inbox/spam).")
        return 0
    print("Test alert NOT sent — see the error above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
