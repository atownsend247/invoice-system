import pytest

from invoice_system.errors import NotFound, ValidationFailed


def test_create_and_get_registrar(application, organisation_id):
    registrar = application.registrars.create_registrar(
        organisation_id, name="123-Reg", notes="https://123-reg.co.uk"
    )
    assert registrar.id is not None
    assert registrar.organisation_id == organisation_id
    assert registrar.name == "123-Reg"
    assert registrar.notes == "https://123-reg.co.uk"

    fetched = application.registrars.get_registrar(organisation_id, registrar.id)
    assert fetched.name == "123-Reg"


def test_create_registrar_notes_are_optional(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    assert registrar.notes is None


def test_create_registrar_blank_notes_are_stored_as_none(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg", notes="   ")
    assert registrar.notes is None


def test_create_registrar_requires_non_blank_name(application, organisation_id):
    with pytest.raises(ValidationFailed):
        application.registrars.create_registrar(organisation_id, name="   ")


def test_list_registrars_orders_alphabetically(application, organisation_id):
    application.registrars.create_registrar(organisation_id, name="GoDaddy")
    application.registrars.create_registrar(organisation_id, name="123-Reg")
    application.registrars.create_registrar(organisation_id, name="namecheap")
    registrars = application.registrars.list_registrars(organisation_id)
    assert [r.name for r in registrars] == ["123-Reg", "GoDaddy", "namecheap"]


def test_registrars_are_isolated_per_organisation(application, organisation_id):
    application.registrars.create_registrar(organisation_id, name="123-Reg")
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    assert application.registrars.list_registrars(other_organisation_id) == []


def test_get_missing_registrar_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.registrars.get_registrar(organisation_id, "does-not-exist")


def test_registrar_from_another_organisation_raises_not_found(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.registrars.get_registrar(other_organisation_id, registrar.id)


def test_update_registrar_replaces_all_fields(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    updated = application.registrars.update_registrar(
        organisation_id, registrar.id, name="GoDaddy", notes="Transferred here"
    )
    assert updated.id == registrar.id
    assert updated.name == "GoDaddy"
    assert updated.notes == "Transferred here"

    fetched = application.registrars.get_registrar(organisation_id, registrar.id)
    assert fetched.name == "GoDaddy"


def test_update_registrar_requires_non_blank_name(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    with pytest.raises(ValidationFailed):
        application.registrars.update_registrar(organisation_id, registrar.id, name="   ")


def test_update_missing_registrar_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.registrars.update_registrar(organisation_id, "does-not-exist", name="GoDaddy")


def test_delete_registrar(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    application.registrars.delete_registrar(organisation_id, registrar.id)
    with pytest.raises(NotFound):
        application.registrars.get_registrar(organisation_id, registrar.id)


def test_delete_missing_registrar_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.registrars.delete_registrar(organisation_id, "does-not-exist")
