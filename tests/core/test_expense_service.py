from decimal import Decimal

import pytest

from invoice_system.errors import NotFound, ValidationFailed


@pytest.fixture
def account(application, organisation_id):
    return application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
    )


def test_create_expense_requires_existing_account(application, organisation_id):
    with pytest.raises(NotFound):
        application.expenses.create_expense(organisation_id=organisation_id, account_id="does-not-exist")


def test_create_expense_requires_account_in_same_organisation(application, organisation_id, account):
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.expenses.create_expense(organisation_id=other_organisation_id, account_id=account.id)


def test_create_expense_assigns_a_number_immediately_unlike_a_quote(application, organisation_id, account):
    # Unlike Quote/Invoice, there's no draft state to move through - an
    # expense is a record of money already spent, so it gets its EXP-0001
    # number at creation, not deferred to a later send()/convert() step.
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    assert expense.number == "EXP-0001"
    assert expense.account_id == account.id
    assert expense.line_items == []
    assert expense.total == Decimal("0")


def test_expense_numbers_are_sequential_per_organisation(application, organisation_id, account):
    first = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    second = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    assert first.number == "EXP-0001"
    assert second.number == "EXP-0002"

    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    other_account = application.accounts.create_account(
        organisation_id=other_organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )
    other_expense = application.expenses.create_expense(
        organisation_id=other_organisation_id, account_id=other_account.id
    )
    assert other_expense.number == "EXP-0001"  # each organisation's own sequence, not a shared one


def test_add_line_item_computes_totals_including_vat(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    expense = application.expenses.add_line_item(
        organisation_id,
        expense.id,
        description="Domain renewal",
        quantity=Decimal("1"),
        unit_price=Decimal("12.00"),
        tax_rate=Decimal("0.20"),
    )
    assert [item.description for item in expense.line_items] == ["Domain renewal"]
    assert expense.subtotal == Decimal("12.00")
    assert expense.tax_total == Decimal("2.40")
    assert expense.total == Decimal("14.40")


def test_add_line_item_requires_a_description(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.expenses.add_line_item(
            organisation_id, expense.id, description="   ", quantity=Decimal("1"), unit_price=Decimal("1")
        )


def test_add_line_item_rejects_an_out_of_range_tax_rate(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.expenses.add_line_item(
            organisation_id,
            expense.id,
            description="Domain renewal",
            quantity=Decimal("1"),
            unit_price=Decimal("12.00"),
            tax_rate=Decimal("1.5"),
        )


def test_line_items_can_be_added_at_any_time_no_status_gate(application, organisation_id, account):
    # No draft/sent lifecycle (see models.Expense) - unlike a quote, there's
    # no status that would ever block adding another line item later (e.g.
    # a follow-up charge for the same renewal).
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    application.expenses.add_line_item(
        organisation_id, expense.id, description="First", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    expense = application.expenses.add_line_item(
        organisation_id, expense.id, description="Second", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    assert [item.description for item in expense.line_items] == ["First", "Second"]


def test_get_missing_expense_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.expenses.get_expense(organisation_id, "does-not-exist")


def test_expense_from_another_organisation_raises_not_found(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.expenses.get_expense(other_organisation_id, expense.id)


def test_list_expenses_filters_by_account(application, organisation_id, account):
    other_account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )
    application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    application.expenses.create_expense(organisation_id=organisation_id, account_id=other_account.id)

    assert len(application.expenses.list_expenses(organisation_id)) == 2
    assert len(application.expenses.list_expenses(organisation_id, account_id=account.id)) == 1
