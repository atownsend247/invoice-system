from datetime import timedelta

import pytest

from invoice_system.errors import NotFound


def test_create_invite_sets_expiry_relative_to_now(application, fake_clock):
    invite = application.registration_invites.create_invite(expires_in_days=7)
    assert invite.created_at == fake_clock()
    assert invite.expires_at == fake_clock() + timedelta(days=7)
    assert invite.used_at is None


def test_check_invite_passes_for_a_fresh_invite(application):
    invite = application.registration_invites.create_invite()
    application.registration_invites.check_invite(invite.token)  # does not raise


def test_check_invite_raises_not_found_for_an_unknown_token(application):
    with pytest.raises(NotFound):
        application.registration_invites.check_invite("does-not-exist")


def test_check_invite_raises_not_found_once_expired(application, fake_clock):
    invite = application.registration_invites.create_invite(expires_in_days=7)
    fake_clock.advance(days=8)
    with pytest.raises(NotFound):
        application.registration_invites.check_invite(invite.token)


def test_consume_invite_marks_it_used_and_cannot_be_reused(application):
    invite = application.registration_invites.create_invite()
    application.registration_invites.consume_invite(invite.token)

    with pytest.raises(NotFound):
        application.registration_invites.consume_invite(invite.token)
    with pytest.raises(NotFound):
        application.registration_invites.check_invite(invite.token)


def test_consume_invite_raises_not_found_for_an_unknown_token(application):
    with pytest.raises(NotFound):
        application.registration_invites.consume_invite("does-not-exist")


def test_consume_invite_raises_not_found_if_a_concurrent_request_wins_the_race(application, monkeypatch):
    # Simulates two near-simultaneous submissions of the same token: this
    # one's check_invite() sees it as still valid, but the repository's
    # atomic claim then reports another caller got there first - the
    # scenario SqliteRepository.consume_registration_invite's WHERE
    # used_at IS NULL guard exists for (see its docstring).
    invite = application.registration_invites.create_invite()
    monkeypatch.setattr(application.repository, "consume_registration_invite", lambda token, used_at: False)
    with pytest.raises(NotFound):
        application.registration_invites.consume_invite(invite.token)
