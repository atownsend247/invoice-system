import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sessionkit import AuthenticationError, AuthError, DuplicateUser
from sessionkit import User as SessionUser
from sessionkit import UserNotFound as AuthUserNotFound
from sessionkit import ValidationError as AuthValidationError

from ..auth import build_auth
from ..errors import AppError, Duplicate, InvalidTransition, NotFound, ValidationFailed
from ..factory import Application, build_application
from ..pdf import render_expense_pdf, render_invoice_pdf, render_quote_pdf
from .auth import (
    get_current_user,
)
from .auth import (
    protected_router as auth_protected_router,
)
from .auth import (
    public_router as auth_public_router,
)
from .schemas import (
    AccountIn,
    AccountOut,
    BusinessProfileIn,
    BusinessProfileOut,
    ExpenseCreateIn,
    ExpenseOut,
    InvoiceOut,
    LineItemIn,
    MonthlyTotalsReportOut,
    QuoteCreateIn,
    QuoteOut,
    StatsOut,
)

_STATUS_BY_ERROR: list[tuple[type[AppError], int]] = [
    (NotFound, 404),
    (Duplicate, 409),
    (InvalidTransition, 409),
    (ValidationFailed, 422),
]

_STATUS_BY_AUTH_ERROR: list[tuple[type[AuthError], int]] = [
    (AuthenticationError, 401),  # covers OtpRequired, OtpLocked too
    (AuthUserNotFound, 404),
    (DuplicateUser, 409),
    (AuthValidationError, 422),
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_path = os.environ.get("INVOICE_SYSTEM_DB", "invoice_system.db")
    auth_db_path = os.environ.get("INVOICE_SYSTEM_AUTH_DB", "auth.db")
    app.state.application = build_application(db_path)
    app.state.auth = build_auth(auth_db_path)
    yield
    app.state.application.close()
    app.state.auth.close()


app = FastAPI(title="Invoice System API", lifespan=lifespan)

# The web client (web/) is a separate origin in dev (Vite on its own port)
# and likely in prod too. Auth is a Bearer token, not a cookie, so there's no
# ambient credential for a wildcard origin to ride along with - allow_origins
# defaults to "*" with allow_credentials=False (the two are mutually
# exclusive per the CORS spec anyway). Tighten via INVOICE_SYSTEM_CORS_ORIGINS
# (comma-separated) once this is deployed somewhere real.
_cors_origins = os.environ.get("INVOICE_SYSTEM_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",")] if _cors_origins != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_application(request: Request) -> Application:
    return request.app.state.application


def get_organisation_id(
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
) -> str:
    """The tenant boundary for the current request - see CLAUDE.md and
    models.py's Organisation docstring. Every domain route depends on this
    (directly or via a handler that also needs `user`/`application` for
    something else) rather than resolving organisation_id itself, so "which
    user" -> "which organisation" is answered in exactly one place."""
    return application.organisations.get_or_create_for_user(user.id)


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    for error_type, status_code in _STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})
    raise exc


@app.exception_handler(AuthError)
def handle_auth_error(request: Request, exc: AuthError) -> JSONResponse:
    for error_type, status_code in _STATUS_BY_AUTH_ERROR:
        if isinstance(exc, error_type):
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})
    raise exc  # OtpInvalid outside login - no specific mapping requested, 422 default below


app.include_router(auth_public_router)
app.include_router(auth_protected_router)

# Every route below requires a valid session - see CLAUDE.md architecture
# rules. /healthz and POST /auth/login (mounted above) are the only exemptions.
domain_router = APIRouter(dependencies=[Depends(get_current_user)])


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@domain_router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(
    body: AccountIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> AccountOut:
    account = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name=body.business_name,
        contact_name=body.contact_name,
        email=body.email,
        phone=body.phone,
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        town_or_city=body.town_or_city,
        county=body.county,
        postcode=body.postcode,
    )
    return AccountOut.from_model(account)


@domain_router.get("/accounts", response_model=list[AccountOut])
def list_accounts(
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> list[AccountOut]:
    return [AccountOut.from_model(a) for a in application.accounts.list_accounts(organisation_id)]


@domain_router.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(
    account_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> AccountOut:
    return AccountOut.from_model(application.accounts.get_account(organisation_id, account_id))


@domain_router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(
    account_id: str,
    body: AccountIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> AccountOut:
    account = application.accounts.update_account(
        organisation_id,
        account_id,
        business_name=body.business_name,
        contact_name=body.contact_name,
        email=body.email,
        phone=body.phone,
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        town_or_city=body.town_or_city,
        county=body.county,
        postcode=body.postcode,
    )
    return AccountOut.from_model(account)


@domain_router.post("/quotes", response_model=QuoteOut, status_code=201)
def create_quote(
    body: QuoteCreateIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> QuoteOut:
    quote = application.quotes.create_quote(
        organisation_id=organisation_id,
        account_id=body.account_id,
        currency=body.currency,
        expiry_date=body.expiry_date,
    )
    return QuoteOut.from_model(quote)


@domain_router.get("/quotes", response_model=list[QuoteOut])
def list_quotes(
    account_id: str | None = None,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> list[QuoteOut]:
    return [
        QuoteOut.from_model(q) for q in application.quotes.list_quotes(organisation_id, account_id=account_id)
    ]


@domain_router.get("/quotes/{quote_id}", response_model=QuoteOut)
def get_quote(
    quote_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> QuoteOut:
    return QuoteOut.from_model(application.quotes.get_quote(organisation_id, quote_id))


@domain_router.post("/quotes/{quote_id}/line-items", response_model=QuoteOut, status_code=201)
def add_quote_line_item(
    quote_id: str,
    body: LineItemIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> QuoteOut:
    quote = application.quotes.add_line_item(
        organisation_id,
        quote_id,
        description=body.description,
        quantity=Decimal(body.quantity),
        unit_price=Decimal(body.unit_price),
        tax_rate=Decimal(body.tax_rate),
    )
    return QuoteOut.from_model(quote)


@domain_router.post("/quotes/{quote_id}/send", response_model=QuoteOut)
def send_quote(
    quote_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> QuoteOut:
    return QuoteOut.from_model(application.quotes.send(organisation_id, quote_id))


@domain_router.post("/quotes/{quote_id}/convert", response_model=InvoiceOut, status_code=201)
def convert_quote(
    quote_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> InvoiceOut:
    return InvoiceOut.from_model(application.quotes.convert_to_invoice(organisation_id, quote_id))


@domain_router.get("/quotes/{quote_id}/pdf")
def get_quote_pdf(
    quote_id: str,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> Response:
    quote = application.quotes.get_quote(organisation_id, quote_id)
    account = application.accounts.get_account(organisation_id, quote.account_id)
    profile = application.business_profiles.get_profile(user.id)
    return Response(content=render_quote_pdf(account, quote, profile), media_type="application/pdf")


@domain_router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(
    account_id: str | None = None,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> list[InvoiceOut]:
    return [
        InvoiceOut.from_model(i)
        for i in application.invoices.list_invoices(organisation_id, account_id=account_id)
    ]


@domain_router.get("/invoices/monthly-totals", response_model=MonthlyTotalsReportOut)
def invoice_monthly_totals(
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> MonthlyTotalsReportOut:
    # Registered before /invoices/{invoice_id} - a fixed path segment would
    # otherwise be swallowed by that route's int path param and 422.
    profile = application.business_profiles.get_profile(user.id)
    totals = application.invoices.monthly_totals(organisation_id, profile.currency)
    return MonthlyTotalsReportOut.from_models(profile.currency, totals)


@domain_router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.get_invoice(organisation_id, invoice_id))


@domain_router.post("/invoices/{invoice_id}/send", response_model=InvoiceOut)
def send_invoice(
    invoice_id: str,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> InvoiceOut:
    profile = application.business_profiles.get_profile(user.id)
    invoice = application.invoices.send(
        organisation_id, invoice_id, payment_terms_days=profile.payment_terms_days
    )
    return InvoiceOut.from_model(invoice)


@domain_router.post("/invoices/{invoice_id}/void", response_model=InvoiceOut)
def void_invoice(
    invoice_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.void(organisation_id, invoice_id))


@domain_router.post("/invoices/{invoice_id}/pay", response_model=InvoiceOut)
def pay_invoice(
    invoice_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.pay(organisation_id, invoice_id))


@domain_router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: str,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> Response:
    invoice = application.invoices.get_invoice(organisation_id, invoice_id)
    account = application.accounts.get_account(organisation_id, invoice.account_id)
    profile = application.business_profiles.get_profile(user.id)
    return Response(content=render_invoice_pdf(account, invoice, profile), media_type="application/pdf")


@domain_router.post("/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(
    body: ExpenseCreateIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseOut:
    expense = application.expenses.create_expense(
        organisation_id=organisation_id, account_id=body.account_id, currency=body.currency
    )
    return ExpenseOut.from_model(expense)


@domain_router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(
    account_id: str | None = None,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> list[ExpenseOut]:
    return [
        ExpenseOut.from_model(e)
        for e in application.expenses.list_expenses(organisation_id, account_id=account_id)
    ]


@domain_router.get("/expenses/{expense_id}", response_model=ExpenseOut)
def get_expense(
    expense_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseOut:
    return ExpenseOut.from_model(application.expenses.get_expense(organisation_id, expense_id))


@domain_router.post("/expenses/{expense_id}/line-items", response_model=ExpenseOut, status_code=201)
def add_expense_line_item(
    expense_id: str,
    body: LineItemIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseOut:
    expense = application.expenses.add_line_item(
        organisation_id,
        expense_id,
        description=body.description,
        quantity=Decimal(body.quantity),
        unit_price=Decimal(body.unit_price),
        tax_rate=Decimal(body.tax_rate),
    )
    return ExpenseOut.from_model(expense)


@domain_router.get("/expenses/{expense_id}/pdf")
def get_expense_pdf(
    expense_id: str,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> Response:
    expense = application.expenses.get_expense(organisation_id, expense_id)
    account = application.accounts.get_account(organisation_id, expense.account_id)
    profile = application.business_profiles.get_profile(user.id)
    return Response(content=render_expense_pdf(account, expense, profile), media_type="application/pdf")


@domain_router.get("/settings/business-profile", response_model=BusinessProfileOut)
def get_business_profile(
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
) -> BusinessProfileOut:
    return BusinessProfileOut.from_model(application.business_profiles.get_profile(user.id))


@domain_router.put("/settings/business-profile", response_model=BusinessProfileOut)
def save_business_profile(
    body: BusinessProfileIn,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
) -> BusinessProfileOut:
    profile = application.business_profiles.save_profile(
        user.id,
        title=body.title,
        first_name=body.first_name,
        last_name=body.last_name,
        business_name=body.business_name,
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        town_or_city=body.town_or_city,
        county=body.county,
        postcode=body.postcode,
        payment_terms_days=body.payment_terms_days,
        currency=body.currency,
        utr=body.utr,
        vat_number=body.vat_number,
        bank_account_name=body.bank_account_name,
        bank_sort_code=body.bank_sort_code,
        bank_account_number=body.bank_account_number,
        document_header=body.document_header,
        document_footer=body.document_footer,
    )
    return BusinessProfileOut.from_model(profile)


@domain_router.get("/stats", response_model=StatsOut)
def get_stats(
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> StatsOut:
    profile = application.business_profiles.get_profile(user.id)
    stats = application.stats.get_stats(organisation_id, profile.currency)
    return StatsOut.from_model(stats, profile.currency)


app.include_router(domain_router)
