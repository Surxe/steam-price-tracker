"""Programmatic read/write access to the ``TRACKED_APP_IDS`` list in config.py.

The list lives in source (per the project's convention) but is edited here by
parsing and re-rendering just the assignment block, so existing ids and their
inline ``# name`` comments are preserved.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.py")

# Captures `TRACKED_APP_IDS: list[int] = [ ... ]` in three groups: head, inner, tail.
_LIST_RE = re.compile(
    r"(TRACKED_APP_IDS\s*:\s*list\[int\]\s*=\s*\[)(.*?)(\])",
    re.DOTALL,
)
# One entry inside the list: an id, then an optional inline comment.
_ENTRY_RE = re.compile(r"(\d+)[ \t]*,?[ \t]*(#[^\n]*)?")

# Captures the ALERT_THRESHOLDS dict block: head, inner, tail.
_DICT_RE = re.compile(
    r"(ALERT_THRESHOLDS\s*:\s*dict\[int,\s*float\]\s*=\s*\{)(.*?)(\})",
    re.DOTALL,
)
# One dict entry: `id: value` then an optional inline comment.
_DICT_ENTRY_RE = re.compile(r"(\d+)\s*:\s*([0-9]*\.?[0-9]+)[ \t]*,?[ \t]*(#[^\n]*)?")


class RegistryError(Exception):
    """Raised when config.py cannot be parsed or edited."""


def _parse(text: str) -> Tuple[re.Match, List[Tuple[int, Optional[str]]]]:
    match = _LIST_RE.search(text)
    if not match:
        raise RegistryError("Could not locate TRACKED_APP_IDS list in config.py")
    entries: List[Tuple[int, Optional[str]]] = []
    for entry in _ENTRY_RE.finditer(match.group(2)):
        comment = (entry.group(2) or "").strip() or None
        entries.append((int(entry.group(1)), comment))
    return match, entries


def _render(entries: List[Tuple[int, Optional[str]]]) -> str:
    lines = ["TRACKED_APP_IDS: list[int] = ["]
    for app_id, comment in entries:
        line = f"    {app_id},"
        if comment:
            line += f"  {comment}"
        lines.append(line)
    lines.append("]")
    return "\n".join(lines)


def read_tracked_ids(config_path: Path = DEFAULT_CONFIG_PATH) -> List[int]:
    """Return the app ids currently registered, in file order."""
    _, entries = _parse(Path(config_path).read_text(encoding="utf-8"))
    return [app_id for app_id, _ in entries]


def add_tracked_id(
    app_id: int,
    name: Optional[str] = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> bool:
    """Append ``app_id`` (with optional ``name`` comment) to TRACKED_APP_IDS.

    Returns ``True`` if it was added, ``False`` if it was already present.
    Idempotent and safe to re-run. The rewritten file is syntax-checked before
    it is saved.
    """
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")
    match, entries = _parse(text)

    if app_id in {existing for existing, _ in entries}:
        return False

    comment = f"# {name}" if name else None
    entries.append((app_id, comment))
    new_text = text[: match.start()] + _render(entries) + text[match.end() :]
    _write_validated(path, new_text)
    return True


def _write_validated(path: Path, new_text: str) -> None:
    """Syntax-check ``new_text`` before overwriting config.py."""
    try:
        ast.parse(new_text)
    except SyntaxError as exc:  # pragma: no cover - defensive
        raise RegistryError(f"Refusing to write invalid config.py: {exc}") from exc
    path.write_text(new_text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# ALERT_THRESHOLDS  (dict[int, float])
# --------------------------------------------------------------------------- #
def _parse_thresholds(
    text: str,
) -> Tuple[re.Match, List[Tuple[int, float, Optional[str]]]]:
    match = _DICT_RE.search(text)
    if not match:
        raise RegistryError("Could not locate ALERT_THRESHOLDS dict in config.py")
    entries: List[Tuple[int, float, Optional[str]]] = []
    for entry in _DICT_ENTRY_RE.finditer(match.group(2)):
        comment = (entry.group(3) or "").strip() or None
        entries.append((int(entry.group(1)), float(entry.group(2)), comment))
    return match, entries


def _render_thresholds(entries: List[Tuple[int, float, Optional[str]]]) -> str:
    if not entries:
        return "ALERT_THRESHOLDS: dict[int, float] = {}"
    lines = ["ALERT_THRESHOLDS: dict[int, float] = {"]
    for app_id, threshold, comment in entries:
        line = f"    {app_id}: {threshold},"
        if comment:
            line += f"  {comment}"
        lines.append(line)
    lines.append("}")
    return "\n".join(lines)


def read_alert_thresholds(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> "dict[int, float]":
    """Return the configured per-app USD thresholds."""
    _, entries = _parse_thresholds(Path(config_path).read_text(encoding="utf-8"))
    return {app_id: threshold for app_id, threshold, _ in entries}


def set_alert_threshold(
    app_id: int,
    threshold: float,
    name: Optional[str] = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> Optional[float]:
    """Set (upsert) ``app_id``'s alert threshold in USD.

    Returns the previous threshold, or ``None`` if it had none. An existing
    inline ``# name`` comment is preserved when ``name`` is not supplied.
    """
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")
    match, entries = _parse_thresholds(text)

    previous: Optional[float] = None
    updated: List[Tuple[int, float, Optional[str]]] = []
    found = False
    for existing_id, existing_threshold, existing_comment in entries:
        if existing_id == app_id:
            previous = existing_threshold
            comment = f"# {name}" if name else existing_comment
            updated.append((app_id, threshold, comment))
            found = True
        else:
            updated.append((existing_id, existing_threshold, existing_comment))
    if not found:
        updated.append((app_id, threshold, f"# {name}" if name else None))

    new_text = text[: match.start()] + _render_thresholds(updated) + text[match.end() :]
    _write_validated(path, new_text)
    return previous


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="steam_price_tracker.registry",
        description="Read or edit TRACKED_APP_IDS and ALERT_THRESHOLDS.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="register an app id")
    p_add.add_argument("app_id", type=int)
    p_add.add_argument("--name", help="product name, stored as an inline comment")
    p_add.add_argument(
        "--threshold",
        type=float,
        help="optional USD price-alert threshold (alerts at or below it)",
    )

    p_thr = sub.add_parser("set-threshold", help="set an app's alert threshold")
    p_thr.add_argument("app_id", type=int)
    p_thr.add_argument("threshold", type=float, help="USD; alerts at or below it")
    p_thr.add_argument("--name", help="product name, stored as an inline comment")

    sub.add_parser("list", help="print registered app ids")

    args = parser.parse_args(argv)

    if args.command == "list":
        for app_id in read_tracked_ids():
            print(app_id)
        return 0

    if args.command == "add":
        added = add_tracked_id(args.app_id, args.name)
        if added:
            label = f" ({args.name})" if args.name else ""
            print(f"Registered {args.app_id}{label} in TRACKED_APP_IDS.")
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
