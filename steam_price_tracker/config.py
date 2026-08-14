"""Configuration access.

Two kinds of configuration meet here:

* **Flat settings** (store paths, SMTP/email) come from an OptionsConfig schema
  (:mod:`steam_price_tracker.options_schema`), resolved from CLI args, then the
  environment / ``.env``, then schema defaults. Get them via :func:`get_options`
  (or seed the cache from parsed CLI args with :func:`load_options`).
* **Tracked apps + thresholds** are variable-length per-app data, so they live in
  a JSON file (the "apps file") whose path is the ``APPS_PATH`` option. The
  registry CLI edits it; readers use :func:`tracked_app_ids` /
  :func:`alert_thresholds` / :func:`load_tracked_apps`.

An apps-file entry is ``{"name": <str?>, "threshold": <float?>}`` keyed by app id
(``name`` is a human label; the authoritative name is fetched into the app-info
store). A missing/``null`` ``threshold`` means "tracked, but never alert".
"""
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Dict, List, Optional

from optionsconfig import Options, init_options, logger

# OptionsConfig logs option resolution via loguru; that is noise for this CLI,
# which speaks through print(). Drop loguru's default handler at import.
logger.remove()

_OPTIONS: Optional[Options] = None


def load_options(args: Namespace | None = None) -> Options:
    """Resolve and cache settings (args > env/.env > defaults).

    Call once from the CLI with parsed ``args`` to fold in command-line
    overrides; later ``get_options()`` calls return the same cached object.
    Passing ``args`` re-resolves (last call wins).
    """
    global _OPTIONS
    if _OPTIONS is None or args is not None:
        _OPTIONS = init_options(args=args, setup_logger=False)
    return _OPTIONS


def get_options() -> Options:
    """Return the resolved settings, loading from env/defaults on first use."""
    return load_options()


# --------------------------------------------------------------------------- #
# Tracked-apps file (ids + thresholds)
# --------------------------------------------------------------------------- #
def apps_path(path: str | Path | None = None) -> Path:
    """Resolve the apps-file path (explicit override, else the APPS_PATH option)."""
    return Path(path) if path is not None else Path(get_options().apps_path)


def load_tracked_apps(path: str | Path | None = None) -> Dict[int, dict]:
    """Return the apps file as ``{app_id: entry}`` in file order (``{}`` if absent)."""
    file = apps_path(path)
    if not file.exists():
        return {}
    raw = json.loads(file.read_text(encoding="utf-8"))
    return {int(app_id): entry for app_id, entry in raw.items()}


def save_tracked_apps(apps: Dict[int, dict], path: str | Path | None = None) -> None:
    """Write ``apps`` back to the apps file (atomic replace, insertion order kept)."""
    file = apps_path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(app_id): entry for app_id, entry in apps.items()}
    tmp = file.with_suffix(file.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(file)


def tracked_app_ids(path: str | Path | None = None) -> List[int]:
    """Return the tracked app ids, in file order."""
    return list(load_tracked_apps(path).keys())


def alert_thresholds(path: str | Path | None = None) -> Dict[int, float]:
    """Return ``{app_id: threshold}`` for apps that declare a USD threshold."""
    thresholds: Dict[int, float] = {}
    for app_id, entry in load_tracked_apps(path).items():
        threshold = entry.get("threshold")
        if threshold is not None:
            thresholds[app_id] = float(threshold)
    return thresholds
