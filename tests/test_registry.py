"""Registry tests: the tracked-apps file edits and the add-time price guard."""
from __future__ import annotations

import pytest

from steam_price_tracker import PriceOverview, PriceUnavailableError
from steam_price_tracker import config, registry
from steam_price_tracker.client import StoreFront
from steam_price_tracker.exceptions import SteamAPIError

PRICED = PriceOverview(
    currency="USD", initial=3999, final=3999,
    discount_percent=0, final_formatted="$39.99",
)


class _FakeSource(StoreFront):
    """Serves a canned price, or raises to simulate no-price / transport error."""

    def __init__(self, result):
        self._result = result

    def fetch_price(self, app_id: int) -> PriceOverview:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result

    def fetch_app_info(self, app_id):  # pragma: no cover - unused here
        raise NotImplementedError

    def search_apps(self, term, limit=10):  # pragma: no cover - unused here
        return []


def test_verify_priceable_returns_overview_when_priced():
    assert registry.verify_priceable(1, _FakeSource(PRICED)) is PRICED


def test_verify_priceable_returns_none_when_unpriced():
    src = _FakeSource(PriceUnavailableError(1))
    assert registry.verify_priceable(1, src) is None


def test_verify_priceable_propagates_transport_error():
    with pytest.raises(SteamAPIError):
        registry.verify_priceable(1, _FakeSource(SteamAPIError("boom")))


def _run_add(monkeypatch, tmp_path, verify_returns, *extra_args):
    """Run ``registry add`` against a temp apps file with a stubbed price probe."""
    apps = tmp_path / "tracked_apps.json"
    monkeypatch.setenv("STEAM_TRACKER_APPS_PATH", str(apps))
    # The CLI caches resolved options in a process global; a fresh CLI run is a
    # fresh process, but in-test we must drop the cache so the env takes effect.
    monkeypatch.setattr(config, "_OPTIONS", None)
    if isinstance(verify_returns, Exception):
        monkeypatch.setattr(
            registry, "verify_priceable",
            lambda app_id, source=None: (_ for _ in ()).throw(verify_returns),
        )
    else:
        monkeypatch.setattr(
            registry, "verify_priceable", lambda app_id, source=None: verify_returns
        )
    code = registry.main(["add", "424242", "--name", "Test App", *extra_args])
    return code, apps


def test_add_refuses_unpriced_app(monkeypatch, tmp_path, capsys):
    code, apps = _run_add(monkeypatch, tmp_path, None)
    assert code == 3
    assert "Refusing to register" in capsys.readouterr().err
    assert not apps.exists()  # nothing written


def test_add_force_registers_unpriced_app(monkeypatch, tmp_path):
    code, apps = _run_add(monkeypatch, tmp_path, None, "--force")
    assert code == 0
    assert "424242" in apps.read_text()


def test_add_registers_priced_app(monkeypatch, tmp_path, capsys):
    code, apps = _run_add(monkeypatch, tmp_path, PRICED)
    assert code == 0
    assert "424242" in apps.read_text()
    assert "$39.99" in capsys.readouterr().out


def test_add_proceeds_on_transport_error(monkeypatch, tmp_path, capsys):
    code, apps = _run_add(monkeypatch, tmp_path, SteamAPIError("network down"))
    assert code == 0
    assert "424242" in apps.read_text()
    assert "could not verify" in capsys.readouterr().err
