"""Programmatic read/write access to the tracked-apps file.

The set of tracked apps and their per-app USD alert thresholds live in a JSON
file (the ``APPS_PATH`` option; see :mod:`steam_price_tracker.config`), keyed by
app id::

    {"2399830": {"name": "ARK: Survival Ascended", "threshold": 20.0}}

``name`` is an optional human label and ``threshold`` an optional USD alert
target (``null``/absent = tracked but never alerted). This module reads and
edits that file; the CLI (``python -m steam_price_tracker.registry``) wraps it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .client import PriceSource, SteamStoreClient
from .exceptions import PriceUnavailableError, SteamAPIError
from .models import PriceOverview


class RegistryError(Exception):
    """Raised when the tracked-apps file cannot be read or edited."""


def verify_priceable(
    app_id: int, source: Optional[PriceSource] = None
) -> Optional[PriceOverview]:
    """Probe Steam for a current US price for ``app_id``.

    Returns the :class:`PriceOverview` when Steam lists a static US price, or
    ``None`` when it does not — i.e. the app is free, unreleased, region-locked,
    or a dynamic "complete the set" bundle whose price is computed per-account
    (Steam returns ``"data": []`` for these). Such an app can be tracked but
    will never yield a price or fire an alert, so callers use this to refuse or
    warn before registering it. Transport/protocol failures propagate as
    :class:`SteamAPIError`, since those are "unknown", not "no price".
    """
    source = source or SteamStoreClient()
    try:
        return source.fetch_price(app_id)
    except PriceUnavailableError:
        return None


def read_tracked_ids(apps_path: str | Path | None = None) -> List[int]:
    """Return the app ids currently registered, in file order."""
    return config.tracked_app_ids(apps_path)


def read_alert_thresholds(apps_path: str | Path | None = None) -> Dict[int, float]:
    """Return the configured per-app USD thresholds."""
    return config.alert_thresholds(apps_path)


def add_tracked_id(
    app_id: int,
    name: Optional[str] = None,
    apps_path: str | Path | None = None,
) -> bool:
    """Register ``app_id`` (with optional ``name``) in the tracked-apps file.

    Returns ``True`` if it was added, ``False`` if it was already present.
    Idempotent and safe to re-run.
    """
    apps = config.load_tracked_apps(apps_path)
    if app_id in apps:
        return False
    entry: dict = {}
    if name:
        entry["name"] = name
    apps[app_id] = entry
    config.save_tracked_apps(apps, apps_path)
    return True


def set_alert_threshold(
    app_id: int,
    threshold: float,
    name: Optional[str] = None,
    apps_path: str | Path | None = None,
) -> Optional[float]:
    """Set (upsert) ``app_id``'s alert threshold in USD.

    Registers the app if it is not already tracked. Returns the previous
    threshold, or ``None`` if it had none. An existing ``name`` is preserved
    when ``name`` is not supplied.
    """
    apps = config.load_tracked_apps(apps_path)
    entry = apps.get(app_id, {})
    previous = entry.get("threshold")
    entry["threshold"] = threshold
    if name:
        entry["name"] = name
    apps[app_id] = entry
    config.save_tracked_apps(apps, apps_path)
    return float(previous) if previous is not None else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="steam_price_tracker.registry",
        description="Read or edit the tracked apps and their alert thresholds.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="register an app id")
    p_add.add_argument("app_id", type=int)
    p_add.add_argument("--name", help="product name, stored alongside the id")
    p_add.add_argument(
        "--threshold",
        type=float,
        help="optional USD price-alert threshold (alerts at or below it)",
    )
    p_add.add_argument(
        "--force",
        action="store_true",
        help="register even if Steam lists no US price for the app (skips the "
        "priceability check; the app is tracked but will never alert)",
    )

    p_thr = sub.add_parser("set-threshold", help="set an app's alert threshold")
    p_thr.add_argument("app_id", type=int)
    p_thr.add_argument("threshold", type=float, help="USD; alerts at or below it")
    p_thr.add_argument("--name", help="product name, stored alongside the id")

    sub.add_parser("list", help="print registered app ids")

    args = parser.parse_args(argv)

    if args.command == "list":
        for app_id in read_tracked_ids():
            print(app_id)
        return 0

    if args.command == "add":
        if not args.force:
            try:
                price = verify_priceable(args.app_id)
            except SteamAPIError as exc:
                # Could not reach/parse Steam — don't block on a transient
                # failure; register but make the unverified state explicit.
                print(
                    f"Warning: could not verify a price for {args.app_id} "
                    f"({exc}); registering anyway.",
                    file=sys.stderr,
                )
            else:
                if price is None:
                    print(
                        f"Refusing to register {args.app_id}: Steam lists no "
                        f"US price for it (free, unreleased, region-locked, or "
                        f"a dynamic 'complete the set' bundle), so the tracker "
                        f"can never price it or alert on it. Re-run with "
                        f"--force to track it anyway.",
                        file=sys.stderr,
                    )
                    return 3
                print(f"Steam price for {args.app_id}: {price.final_formatted}.")
        added = add_tracked_id(args.app_id, args.name)
        if added:
            label = f" ({args.name})" if args.name else ""
            print(f"Registered {args.app_id}{label}.")
        else:
            print(f"{args.app_id} is already registered; no change.")
        if args.threshold is not None:
            set_alert_threshold(args.app_id, args.threshold, args.name)
            print(f"Alert threshold for {args.app_id} set to ${args.threshold:.2f}.")
        return 0

    if args.command == "set-threshold":
        previous = set_alert_threshold(args.app_id, args.threshold, args.name)
        if previous is None:
            print(f"Alert threshold for {args.app_id} set to ${args.threshold:.2f}.")
        else:
            print(
                f"Alert threshold for {args.app_id} changed "
                f"${previous:.2f} -> ${args.threshold:.2f}."
            )
        return 0

    return 1  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
