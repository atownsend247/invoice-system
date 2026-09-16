from datetime import UTC, datetime
from decimal import Decimal

import pytest

from invoice_system.core import MAX_ATTACHMENT_SIZE
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


def test_add_attachment_round_trips_through_the_returned_expense(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    attachment = application.expenses.add_attachment(
        organisation_id,
        expense.id,
        filename="receipt.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.4 fake receipt",
    )
    assert attachment.filename == "receipt.pdf"
    assert attachment.size == len(b"%PDF-1.4 fake receipt")

    fetched = application.expenses.get_expense(organisation_id, expense.id)
    assert [a.id for a in fetched.attachments] == [attachment.id]


def test_add_attachment_requires_an_existing_expense(application, organisation_id):
    with pytest.raises(NotFound):
        application.expenses.add_attachment(
            organisation_id,
            "does-not-exist",
            filename="receipt.pdf",
            content_type="application/pdf",
            data=b"data",
        )


def test_add_attachment_rejects_a_non_pdf(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.expenses.add_attachment(
            organisation_id,
            expense.id,
            filename="receipt.png",
            content_type="image/png",
            data=b"not a pdf",
        )


def test_add_attachment_accepts_a_pdf_extension_even_with_a_generic_content_type(
    application, organisation_id, account
):
    # A browser upload's Content-Type isn't always trustworthy (some OSes/
    # browsers send application/octet-stream for an unfamiliar extension) -
    # the .pdf extension alone is enough, matching ExpenseService.add_attachment.
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    attachment = application.expenses.add_attachment(
        organisation_id,
        expense.id,
        filename="receipt.PDF",
        content_type="application/octet-stream",
        data=b"data",
    )
    assert attachment.filename == "receipt.PDF"


def test_add_attachment_rejects_an_empty_file(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.expenses.add_attachment(
            organisation_id, expense.id, filename="receipt.pdf", content_type="application/pdf", data=b""
        )


def test_add_attachment_rejects_a_blank_filename(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.expenses.add_attachment(
            organisation_id, expense.id, filename="   ", content_type="application/pdf", data=b"data"
        )


def test_add_attachment_rejects_a_file_over_the_size_limit(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.expenses.add_attachment(
            organisation_id,
            expense.id,
            filename="receipt.pdf",
            content_type="application/pdf",
            data=b"0" * (MAX_ATTACHMENT_SIZE + 1),
        )


def test_get_attachment_bytes_returns_the_uploaded_data(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    uploaded = application.expenses.add_attachment(
        organisation_id, expense.id, filename="receipt.pdf", content_type="application/pdf", data=b"hello"
    )

    attachment, data = application.expenses.get_attachment_bytes(organisation_id, expense.id, uploaded.id)
    assert attachment.id == uploaded.id
    assert data == b"hello"


def test_get_attachment_bytes_requires_existing_attachment(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(NotFound):
        application.expenses.get_attachment_bytes(organisation_id, expense.id, "does-not-exist")


def test_get_attachment_bytes_from_another_organisation_raises_not_found(
    application, organisation_id, account
):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    attachment = application.expenses.add_attachment(
        organisation_id, expense.id, filename="receipt.pdf", content_type="application/pdf", data=b"data"
    )

    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.expenses.get_attachment_bytes(other_organisation_id, expense.id, attachment.id)


def test_delete_attachment_removes_it_from_the_expense_and_from_disk(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    attachment = application.expenses.add_attachment(
        organisation_id, expense.id, filename="receipt.pdf", content_type="application/pdf", data=b"data"
    )

    application.expenses.delete_attachment(organisation_id, expense.id, attachment.id)

    fetched = application.expenses.get_expense(organisation_id, expense.id)
    assert fetched.attachments == []
    with pytest.raises(NotFound):
        application.expenses.get_attachment_bytes(organisation_id, expense.id, attachment.id)


def test_delete_missing_attachment_raises_not_found(application, organisation_id, account):
    expense = application.expenses.create_expense(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(NotFound):
        application.expenses.delete_attachment(organisation_id, expense.id, "does-not-exist")


class TestMonthlyTotals:
    def _create_expense(
        self, application, organisation_id, account, *, currency: str = "GBP", price: str = "100.00"
    ):
        expense = application.expenses.create_expense(
            organisation_id=organisation_id, account_id=account.id, currency=currency
        )
        return application.expenses.add_line_item(
            organisation_id,
            expense.id,
            description="Work",
            quantity=Decimal("1"),
            unit_price=Decimal(price),
        )

    def test_returns_twelve_months_ending_with_the_current_one_even_with_no_data(
        self, application, organisation_id, fake_clock
    ):
        fake_clock.set(datetime(2026, 6, 15, tzinfo=UTC))
        totals = application.expenses.monthly_totals(organisation_id, "GBP")
        assert [t.month for t in totals] == [
            "2025-07",
            "2025-08",
            "2025-09",
            "2025-10",
            "2025-11",
            "2025-12",
            "2026-01",
            "2026-02",
            "2026-03",
            "2026-04",
            "2026-05",
            "2026-06",
        ]
        assert all(t.total == Decimal("0") for t in totals)

    def test_buckets_by_issue_date_month_and_sums_gross_total(
        self, application, organisation_id, account, fake_clock
    ):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        self._create_expense(application, organisation_id, account, price="100.00")

        fake_clock.set(datetime(2026, 3, 20, tzinfo=UTC))
        self._create_expense(application, organisation_id, account, price="50.00")

        totals = {t.month: t for t in application.expenses.monthly_totals(organisation_id, "GBP")}
        assert totals["2026-03"].total == Decimal("150.00")

    def test_expenses_outside_the_window_are_excluded(
        self, application, organisation_id, account, fake_clock
    ):
        fake_clock.set(datetime(2025, 1, 10, tzinfo=UTC))
        self._create_expense(application, organisation_id, account, price="100.00")

        fake_clock.set(datetime(2026, 6, 1, tzinfo=UTC))
        totals = application.expenses.monthly_totals(organisation_id, "GBP")
        assert all(t.total == Decimal("0") for t in totals)

    def test_expenses_in_a_different_currency_are_excluded(
        self, application, organisation_id, account, fake_clock
    ):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        self._create_expense(application, organisation_id, account, currency="USD", price="100.00")

        totals = {t.month: t for t in application.expenses.monthly_totals(organisation_id, "GBP")}
        assert totals["2026-03"].total == Decimal("0")

    def test_expenses_from_another_organisation_are_excluded(
        self, application, organisation_id, account, fake_clock
    ):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        self._create_expense(application, organisation_id, account, price="100.00")

        other_organisation_id = application.organisations.get_or_create_for_user("user-2")
        totals = {t.month: t for t in application.expenses.monthly_totals(other_organisation_id, "GBP")}
        assert totals["2026-03"].total == Decimal("0")
