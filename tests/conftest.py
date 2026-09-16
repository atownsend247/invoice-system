from datetime import UTC, datetime, timedelta

import pytest

from invoice_system.factory import Application, build_application


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **kwargs) -> None:
        self._now += timedelta(**kwargs)

    def set(self, value: datetime) -> None:
        self._now = value


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def application(tmp_path, fake_clock: FakeClock) -> Application:
    app = build_application(tmp_path / "test.db", clock=fake_clock, attachments_dir=tmp_path / "attachments")
    yield app
    app.close()


@pytest.fixture
def organisation_id(application: Application) -> str:
    """A single user's (id "user-1") auto-created Organisation - the tenant
    boundary every Account/Quote/Invoice call now requires (see CLAUDE.md).
    Most tests only care that there's *an* organisation, not which one -
    tests asserting isolation between two organisations build their own
    second id via `application.organisations.get_or_create_for_user("user-2")`.
    A plain string, not a real UUID - user_id is never parsed or validated
    as one (see CLAUDE.md), only ever used as an opaque key."""
    return application.organisations.get_or_create_for_user("user-1")
