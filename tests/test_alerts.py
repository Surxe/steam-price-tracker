"""Tests for email delivery, once-per-day dedup, and composite fan-out.

No network and no real credentials: SMTP is replaced with a fake that records
login() args and sent messages, and ``today`` is injected for determinism.
"""
from __future__ import annotations

import smtplib
from pathlib import Path

from steam_price_tracker import (
    Alerter,
    CompositeAlerter,
    EmailAlerter,
    EmailConfig,
    JsonAlertStateStore,
    PriceAlert,
    PriceOverview,
)

CFG = EmailConfig(
    host="smtp.example.com",
    port=587,
    user="surxe.developer@gmail.com",
    password="app-password-16",
    to_addr="alerts@example.com",
)

ARK_ALERT = PriceAlert(
    app_id=2399830,
    price=PriceOverview("USD", 4499, 4499, 0, "$44.99"),
    threshold=50.0,
    name="ARK: Survival Ascended",
)


class FakeSMTP:
    """Minimal stand-in for smtplib.SMTP usable as a context manager."""

    def __init__(self, host, port, *, fail_login=False):
        self.host = host
        self.port = port
        self._fail_login = fail_login
        self.started_tls = False
        self.login_args = None
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        if self._fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad creds")
        self.login_args = (user, password)

    def send_message(self, message):
        self.sent.append(message)


def _factory(recorder: list, *, fail_login=False):
    def make(host, port):
        smtp = FakeSMTP(host, port, fail_login=fail_login)
        recorder.append(smtp)
        return smtp
    return make


def test_email_composes_and_authenticates(tmp_path: Path):
    smtps: list[FakeSMTP] = []
    state = JsonAlertStateStore(tmp_path / "state.json")
    alerter = EmailAlerter(
        CFG, state, smtp_factory=_factory(smtps), today=lambda: "2026-08-06"
    )

    assert alerter.try_send([ARK_ALERT]) is True

    assert len(smtps) == 1
    smtp = smtps[0]
    assert smtp.started_tls is True
    assert smtp.login_args == ("surxe.developer@gmail.com", "app-password-16")
    assert len(smtp.sent) == 1
    msg = smtp.sent[0]
    assert msg["From"] == "surxe.developer@gmail.com"
    assert msg["To"] == "alerts@example.com"
    assert "1 game" in msg["Subject"]
    body = msg.get_content()
    assert "ARK: Survival Ascended" in body
    assert "store.steampowered.com/app/2399830" in body
    # State recorded so the same day won't re-send.
    assert state.last_emailed(2399830) == "2026-08-06"


def test_email_deduped_same_day(tmp_path: Path):
    smtps: list[FakeSMTP] = []
    state = JsonAlertStateStore(tmp_path / "state.json")
    alerter = EmailAlerter(
        CFG, state, smtp_factory=_factory(smtps), today=lambda: "2026-08-06"
    )

    alerter.send([ARK_ALERT])
    alerter.send([ARK_ALERT])  # same day -> suppressed

    assert len(smtps) == 1  # no second SMTP connection/message


def test_email_sends_again_next_day(tmp_path: Path):
    smtps: list[FakeSMTP] = []
    state = JsonAlertStateStore(tmp_path / "state.json")
    day = {"v": "2026-08-06"}
    alerter = EmailAlerter(
        CFG, state, smtp_factory=_factory(smtps), today=lambda: day["v"]
    )

    alerter.send([ARK_ALERT])
    day["v"] = "2026-08-07"
    alerter.send([ARK_ALERT])

    assert len(smtps) == 2


def test_auth_failure_does_not_crash_or_mark(tmp_path: Path):
    smtps: list[FakeSMTP] = []
    state = JsonAlertStateStore(tmp_path / "state.json")
    alerter = EmailAlerter(
        CFG,
        state,
        smtp_factory=_factory(smtps, fail_login=True),
        today=lambda: "2026-08-06",
    )

    assert alerter.try_send([ARK_ALERT]) is False  # must not raise

    assert smtps[0].sent == []                 # nothing sent
    assert state.last_emailed(2399830) is None  # not marked -> will retry


def test_empty_batch_no_connection(tmp_path: Path):
    smtps: list[FakeSMTP] = []
    alerter = EmailAlerter(
        CFG,
        JsonAlertStateStore(tmp_path / "state.json"),
        smtp_factory=_factory(smtps),
        today=lambda: "2026-08-06",
    )
    alerter.send([])
    assert smtps == []


def _opts(**overrides):
    """A stand-in for resolved OptionsConfig settings (only the fields read)."""
    from types import SimpleNamespace

    base = dict(
        smtp_user=None,
        smtp_password=None,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        email_to=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_email_config_from_options():
    # Off until user, password, AND recipient are all present (all three are
    # secrets supplied via smtp.env; the recipient has no committed default).
    assert EmailConfig.from_options(_opts()) is None
    assert EmailConfig.from_options(
        _opts(smtp_user="x@y.com", smtp_password="pw")
    ) is None  # no recipient
    assert EmailConfig.from_options(
        _opts(smtp_user="x@y.com", email_to="to@z.com")
    ) is None  # no password
    cfg = EmailConfig.from_options(
        _opts(smtp_user="x@y.com", smtp_password="pw", email_to="to@z.com")
    )
    assert cfg is not None
    assert cfg.user == "x@y.com" and cfg.password == "pw"
    assert cfg.host == "smtp.gmail.com" and cfg.port == 587
    assert cfg.to_addr == "to@z.com"


def test_composite_fans_out():
    class Recorder(Alerter):
        def __init__(self):
            self.batches = []

        def send(self, alerts):
            self.batches.append(list(alerts))

    a, b = Recorder(), Recorder()
    CompositeAlerter([a, b]).send([ARK_ALERT])

    assert a.batches == [[ARK_ALERT]]
    assert b.batches == [[ARK_ALERT]]
