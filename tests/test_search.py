"""Tests for search rendering and the tracked-apps registry editor."""
from __future__ import annotations

import json
from pathlib import Path

from steam_price_tracker import SearchResult
from steam_price_tracker import registry
from steam_price_tracker.search import to_json, to_markdown

RESULTS = [
    SearchResult(app_id=2399830, name="ARK: Survival Ascended", type="app"),
    SearchResult(app_id=346110, name="ARK: Survival Evolved", type="app"),
]


# --------------------------- search rendering ---------------------------- #
def test_markdown_has_row_per_result():
    md = to_markdown(RESULTS)
    assert "| # | App ID | Type | Name |" in md
    assert "`2399830`" in md and "ARK: Survival Ascended" in md
    assert md.count("\n") == 3  # header + separator + 2 rows -> 3 newlines


def test_markdown_escapes_pipes():
    md = to_markdown([SearchResult(app_id=1, name="A | B", type="app")])
    assert "A \\| B" in md


def test_markdown_empty():
    assert to_markdown([]) == "_No matching apps found._"


def test_json_roundtrips_fields():
    data = json.loads(to_json(RESULTS))
    assert data[0] == {"app_id": 2399830, "name": "ARK: Survival Ascended", "type": "app"}


# ------------------------------- registry -------------------------------- #
def _apps_file(tmp_path: Path, apps: dict) -> Path:
    """Write a tracked-apps file with string keys, as on disk."""
    dst = tmp_path / "tracked_apps.json"
    dst.write_text(json.dumps({str(k): v for k, v in apps.items()}), encoding="utf-8")
    return dst


def test_add_tracked_id_appends_with_name(tmp_path: Path):
    apps = _apps_file(tmp_path, {2399830: {"name": "ARK: Survival Ascended"}})
    assert registry.add_tracked_id(346110, "ARK: Survival Evolved", apps) is True
    assert registry.read_tracked_ids(apps) == [2399830, 346110]
    stored = json.loads(apps.read_text())
    assert stored["346110"] == {"name": "ARK: Survival Evolved"}


def test_add_tracked_id_is_idempotent(tmp_path: Path):
    apps = _apps_file(tmp_path, {2399830: {"name": "ARK: Survival Ascended"}})
    assert registry.add_tracked_id(2399830, "dup", apps) is False
    assert registry.read_tracked_ids(apps) == [2399830]


def test_add_to_missing_file_creates_it(tmp_path: Path):
    apps = tmp_path / "tracked_apps.json"  # does not exist yet
    assert registry.add_tracked_id(2399830, "ARK: Survival Ascended", apps) is True
    assert registry.read_tracked_ids(apps) == [2399830]


# ------------------------------ thresholds ------------------------------- #
def test_read_thresholds_skips_apps_without_one(tmp_path: Path):
    apps = _apps_file(
        tmp_path,
        {
            2399830: {"name": "ARK: Survival Ascended", "threshold": 20.0},
            346110: {"name": "ARK: Survival Evolved"},  # tracked, no threshold
        },
    )
    assert registry.read_alert_thresholds(apps) == {2399830: 20.0}
    assert registry.read_tracked_ids(apps) == [2399830, 346110]


def test_set_threshold_from_none(tmp_path: Path):
    apps = _apps_file(tmp_path, {2399830: {"name": "ARK: Survival Ascended"}})
    prev = registry.set_alert_threshold(2399830, 30.0, apps_path=apps)
    assert prev is None
    assert registry.read_alert_thresholds(apps) == {2399830: 30.0}
    # Existing name is preserved.
    assert json.loads(apps.read_text())["2399830"]["name"] == "ARK: Survival Ascended"


def test_set_threshold_updates_existing(tmp_path: Path):
    apps = _apps_file(tmp_path, {2399830: {"threshold": 30.0}})
    prev = registry.set_alert_threshold(2399830, 25.0, apps_path=apps)
    assert prev == 30.0
    assert registry.read_alert_thresholds(apps) == {2399830: 25.0}


def test_set_threshold_registers_unknown_app(tmp_path: Path):
    apps = _apps_file(tmp_path, {})
    prev = registry.set_alert_threshold(346110, 12.5, "ARK: Survival Evolved", apps)
    assert prev is None
    assert registry.read_tracked_ids(apps) == [346110]
    assert registry.read_alert_thresholds(apps) == {346110: 12.5}
