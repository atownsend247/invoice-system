import pytest

from invoice_system.errors import ValidationFailed


def test_get_profile_returns_defaults_when_none_saved(application):
    profile = application.business_profiles.get_profile(user_id=1)
    assert profile.id is None
    assert profile.title is None
    assert profile.first_name == ""
    assert profile.last_name == ""
    assert profile.business_name == ""
    assert profile.business_address is None
    assert profile.payment_terms_days == 30
    assert profile.utr is None
    assert profile.vat_number is None


def test_save_and_refetch_profile(application):
    saved = application.business_profiles.save_profile(
        user_id=1,
        title="Dr",
        first_name="Ada",
        last_name="Lovelace",
        business_name="Acme Consulting",
        business_address="1 Main St",
        payment_terms_days=14,
        utr="1234567890",
        vat_number="GB123456789",
    )
    assert saved.id is not None
    assert saved.title == "Dr"
    assert saved.first_name == "Ada"
    assert saved.last_name == "Lovelace"
    assert saved.business_name == "Acme Consulting"
    assert saved.payment_terms_days == 14

    fetched = application.business_profiles.get_profile(user_id=1)
    assert fetched.id == saved.id
    assert fetched.utr == "1234567890"
    assert fetched.vat_number == "GB123456789"


def test_saving_again_updates_the_same_row_not_a_new_one(application):
    first = application.business_profiles.save_profile(
        user_id=1, first_name="Ada", last_name="Lovelace", business_name="A", payment_terms_days=30
    )
    second = application.business_profiles.save_profile(
        user_id=1, first_name="Grace", last_name="Hopper", business_name="B", payment_terms_days=45
    )
    assert second.id == first.id
    assert second.first_name == "Grace"
    assert second.business_name == "B"
    assert second.payment_terms_days == 45


def test_title_business_address_utr_and_vat_number_are_optional(application):
    profile = application.business_profiles.save_profile(
        user_id=1, first_name="Ada", last_name="Lovelace", business_name="Acme", payment_terms_days=30
    )
    assert profile.title is None
    assert profile.business_address is None
    assert profile.utr is None
    assert profile.vat_number is None


def test_blank_optional_fields_are_stored_as_none(application):
    profile = application.business_profiles.save_profile(
        user_id=1,
        first_name="Ada",
        last_name="Lovelace",
        business_name="Acme",
        payment_terms_days=30,
        title="   ",
        business_address="   ",
        utr="   ",
        vat_number="   ",
    )
    assert profile.title is None
    assert profile.business_address is None
    assert profile.utr is None
    assert profile.vat_number is None


@pytest.mark.parametrize(("field", "value"), [("first_name", ""), ("last_name", "  "), ("business_name", "")])
def test_save_profile_requires_non_blank_required_fields(application, field, value):
    kwargs = {"first_name": "Ada", "last_name": "Lovelace", "business_name": "Acme", "payment_terms_days": 30}
    kwargs[field] = value
    with pytest.raises(ValidationFailed):
        application.business_profiles.save_profile(user_id=1, **kwargs)


def test_save_profile_requires_positive_payment_terms(application):
    with pytest.raises(ValidationFailed):
        application.business_profiles.save_profile(
            user_id=1,
            first_name="Ada",
            last_name="Lovelace",
            business_name="Acme",
            payment_terms_days=0,
        )


def test_profiles_are_isolated_per_user(application):
    application.business_profiles.save_profile(
        user_id=1,
        first_name="Ada",
        last_name="Lovelace",
        business_name="User One Co",
        payment_terms_days=30,
    )
    other = application.business_profiles.get_profile(user_id=2)
    assert other.business_name == ""
    assert other.first_name == ""
