import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import APIRouter, Depends, FastAPI, File, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sessionkit import AuthenticationError, AuthError, DuplicateUser
from sessionkit import User as SessionUser
from sessionkit import UserNotFound as AuthUserNotFound
from sessionkit import ValidationError as AuthValidationError

from ..auth import build_auth
from ..errors import AppError, Conflict, Duplicate, InvalidTransition, NotFound, ValidationFailed
from ..factory import Application, build_application
from ..models import InvoiceStatus, QuoteStatus
from ..paths import DEFAULT_STORAGE_DIR, StoragePaths
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
    AccountListOut,
    AccountOut,
    BusinessProfileIn,
    BusinessProfileOut,
    DomainIn,
    DomainOut,
    ExpenseAttachmentOut,
    ExpenseCreateIn,
    ExpenseDateIn,
    ExpenseOut,
    InvoiceListOut,
    InvoiceOut,
    LineItemIn,
    MonthlyExpenseTotalsReportOut,
    MonthlyTotalsReportOut,
    NextNumberIn,
    QuoteConvertIn,
    QuoteCreateIn,
    QuoteListOut,
    QuoteOut,
    RegistrarIn,
    RegistrarOut,
    StatsOut,
)

_STATUS_BY_ERROR: list[tuple[type[AppError], int]] = [
    (NotFound, 404),
    (Duplicate, 409),
    (InvalidTransition, 409),
    (Conflict, 409),
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
    # INVOICE_SYSTEM_STORAGE_DIR (default "storage/") sets where every kind
    # of persistent file lives by default - see paths.py. The three
    # per-path env vars below still override individually when set (e.g.
    # putting attachments on different storage than the databases); they
    # just no longer hardcode their own bare-CWD-relative defaults.
    storage_dir = os.environ.get("INVOICE_SYSTEM_STORAGE_DIR", DEFAULT_STORAGE_DIR)
    paths = StoragePaths(storage_dir)
    if "INVOICE_SYSTEM_DB" not in os.environ or "INVOICE_SYSTEM_AUTH_DB" not in os.environ:
        # Only touch disk for whichever derived default actually ends up
        # used - explicitly overriding both means storage-dir's own db/
        # subdirectory is never touched, so nothing should create it (see
        # the matching guard/comment in cli/main.py's cli() group).
        paths.ensure_db_dir()
    db_path = os.environ.get("INVOICE_SYSTEM_DB", str(paths.domain_db_path))
    auth_db_path = os.environ.get("INVOICE_SYSTEM_AUTH_DB", str(paths.auth_db_path))
    attachments_dir = os.environ.get("INVOICE_SYSTEM_ATTACHMENTS_DIR", str(paths.attachments_dir))
    app.state.application = build_application(db_path, attachments_dir=attachments_dir)
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
# rules. /healthz, POST /auth/login, GET /auth/register/validate, and POST
# /auth/register (all mounted above, the last two on api/auth.py's own
# public_router) are the only exemptions.
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


@domain_router.get("/accounts", response_model=AccountListOut)
def list_accounts(
    query: str | None = None,
    page: int = 1,
    page_size: int = 20,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> AccountListOut:
    result = application.accounts.list_accounts(organisation_id, query=query, page=page, page_size=page_size)
    return AccountListOut(items=[AccountOut.from_model(a) for a in result.items], total=result.total)


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


@domain_router.post("/accounts/{account_id}/domains", response_model=DomainOut, status_code=201)
def create_domain(
    account_id: str,
    body: DomainIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> DomainOut:
    domain = application.domains.create_domain(
        organisation_id,
        account_id,
        domain_name=body.domain_name,
        expiry_date=body.expiry_date,
        registrar=body.registrar,
        auto_renew=body.auto_renew,
    )
    return DomainOut.from_model(domain)


@domain_router.get("/accounts/{account_id}/domains", response_model=list[DomainOut])
def list_domains(
    account_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> list[DomainOut]:
    domains = application.domains.list_domains(organisation_id, account_id)
    return [DomainOut.from_model(d) for d in domains]


@domain_router.put("/accounts/{account_id}/domains/{domain_id}", response_model=DomainOut)
def update_domain(
    account_id: str,
    domain_id: str,
    body: DomainIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> DomainOut:
    domain = application.domains.update_domain(
        organisation_id,
        account_id,
        domain_id,
        domain_name=body.domain_name,
        expiry_date=body.expiry_date,
        registrar=body.registrar,
        auto_renew=body.auto_renew,
    )
    return DomainOut.from_model(domain)


@domain_router.delete("/accounts/{account_id}/domains/{domain_id}", status_code=204)
def delete_domain(
    account_id: str,
    domain_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> None:
    application.domains.delete_domain(organisation_id, account_id, domain_id)


@domain_router.post("/registrars", response_model=RegistrarOut, status_code=201)
def create_registrar(
    body: RegistrarIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> RegistrarOut:
    registrar = application.registrars.create_registrar(organisation_id, name=body.name, notes=body.notes)
    return RegistrarOut.from_model(registrar)


@domain_router.get("/registrars", response_model=list[RegistrarOut])
def list_registrars(
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> list[RegistrarOut]:
    usages = application.registrars.list_registrars_with_usage(organisation_id)
    return [RegistrarOut.from_usage(u) for u in usages]


@domain_router.put("/registrars/{registrar_id}", response_model=RegistrarOut)
def update_registrar(
    registrar_id: str,
    body: RegistrarIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> RegistrarOut:
    application.registrars.update_registrar(organisation_id, registrar_id, name=body.name, notes=body.notes)
    # Re-fetch usage against the (possibly renamed) current name, not the
    # pre-update one - a rename can change which domains actually match.
    usage = application.registrars.get_registrar_usage(organisation_id, registrar_id)
    return RegistrarOut.from_usage(usage)


@domain_router.delete("/registrars/{registrar_id}", status_code=204)
def delete_registrar(
    registrar_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> None:
    application.registrars.delete_registrar(organisation_id, registrar_id)


@domain_router.post("/quotes", response_model=QuoteOut, status_code=201)
def create_quote(
    body: QuoteCreateIn,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> QuoteOut:
    profile = application.business_profiles.get_profile(user.id)
    quote = application.quotes.create_quote(
        organisation_id=organisation_id,
        account_id=body.account_id,
        currency=body.currency,
        issue_date=body.issue_date,
        quote_validity_days=profile.quote_validity_days,
    )
    return QuoteOut.from_model(quote)


@domain_router.get("/quotes", response_model=QuoteListOut)
def list_quotes(
    account_id: str | None = None,
    account_name: str | None = None,
    status: QuoteStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> QuoteListOut:
    result = application.quotes.list_quotes(
        organisation_id,
        account_id=account_id,
        account_name=account_name,
        status=status,
        page=page,
        page_size=page_size,
    )
    return QuoteListOut(items=[QuoteOut.from_model(q) for q in result.items], total=result.total)


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
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> QuoteOut:
    profile = application.business_profiles.get_profile(user.id)
    quote = application.quotes.send(
        organisation_id,
        quote_id,
        number_prefix=profile.quote_number_prefix,
        number_digits=profile.quote_number_digits,
    )
    return QuoteOut.from_model(quote)


@domain_router.post("/quotes/next-number", status_code=204)
def set_next_quote_number(
    body: NextNumberIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> None:
    application.quotes.set_next_number(organisation_id, body.next_number)


@domain_router.post("/quotes/{quote_id}/convert", response_model=InvoiceOut, status_code=201)
def convert_quote(
    quote_id: str,
    body: QuoteConvertIn | None = None,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> InvoiceOut:
    issue_date = body.issue_date if body is not None else None
    invoice = application.quotes.convert_to_invoice(organisation_id, quote_id, issue_date=issue_date)
    return InvoiceOut.from_model(invoice)


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


@domain_router.get("/invoices", response_model=InvoiceListOut)
def list_invoices(
    account_id: str | None = None,
    account_name: str | None = None,
    status: InvoiceStatus | None = None,
    quote_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> InvoiceListOut:
    result = application.invoices.list_invoices(
        organisation_id,
        account_id=account_id,
        account_name=account_name,
        status=status,
        quote_id=quote_id,
        page=page,
        page_size=page_size,
    )
    return InvoiceListOut(items=[InvoiceOut.from_model(i) for i in result.items], total=result.total)


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
        organisation_id,
        invoice_id,
        payment_terms_days=profile.payment_terms_days,
        number_prefix=profile.invoice_number_prefix,
        number_digits=profile.invoice_number_digits,
    )
    return InvoiceOut.from_model(invoice)


@domain_router.post("/invoices/next-number", status_code=204)
def set_next_invoice_number(
    body: NextNumberIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> None:
    application.invoices.set_next_number(organisation_id, body.next_number)


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
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseOut:
    profile = application.business_profiles.get_profile(user.id)
    expense = application.expenses.create_expense(
        organisation_id=organisation_id,
        account_id=body.account_id,
        currency=body.currency,
        expense_date=body.expense_date,
        number_prefix=profile.expense_number_prefix,
        number_digits=profile.expense_number_digits,
    )
    return ExpenseOut.from_model(expense)


@domain_router.post("/expenses/next-number", status_code=204)
def set_next_expense_number(
    body: NextNumberIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> None:
    application.expenses.set_next_number(organisation_id, body.next_number)


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


@domain_router.get("/expenses/monthly-totals", response_model=MonthlyExpenseTotalsReportOut)
def expense_monthly_totals(
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
    organisation_id: str = Depends(get_organisation_id),
) -> MonthlyExpenseTotalsReportOut:
    # Registered before /expenses/{expense_id} - same route-ordering
    # reasoning as /invoices/monthly-totals above.
    profile = application.business_profiles.get_profile(user.id)
    totals = application.expenses.monthly_totals(organisation_id, profile.currency)
    return MonthlyExpenseTotalsReportOut.from_models(profile.currency, totals)


@domain_router.get("/expenses/{expense_id}", response_model=ExpenseOut)
def get_expense(
    expense_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseOut:
    return ExpenseOut.from_model(application.expenses.get_expense(organisation_id, expense_id))


@domain_router.put("/expenses/{expense_id}/expense-date", response_model=ExpenseOut)
def update_expense_date(
    expense_id: str,
    body: ExpenseDateIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseOut:
    expense = application.expenses.update_expense_date(organisation_id, expense_id, body.expense_date)
    return ExpenseOut.from_model(expense)


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


@domain_router.put("/expenses/{expense_id}/line-items/{item_id}", response_model=ExpenseOut)
def update_expense_line_item(
    expense_id: str,
    item_id: str,
    body: LineItemIn,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseOut:
    expense = application.expenses.update_line_item(
        organisation_id,
        expense_id,
        item_id,
        description=body.description,
        quantity=Decimal(body.quantity),
        unit_price=Decimal(body.unit_price),
        tax_rate=Decimal(body.tax_rate),
    )
    return ExpenseOut.from_model(expense)


@domain_router.delete("/expenses/{expense_id}/line-items/{item_id}", response_model=ExpenseOut)
def delete_expense_line_item(
    expense_id: str,
    item_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseOut:
    expense = application.expenses.delete_line_item(organisation_id, expense_id, item_id)
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


@domain_router.post(
    "/expenses/{expense_id}/attachments", response_model=ExpenseAttachmentOut, status_code=201
)
async def add_expense_attachment(
    expense_id: str,
    file: UploadFile = File(...),
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> ExpenseAttachmentOut:
    data = await file.read()
    attachment = application.expenses.add_attachment(
        organisation_id,
        expense_id,
        filename=file.filename or "attachment.pdf",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return ExpenseAttachmentOut.from_model(attachment)


@domain_router.get("/expenses/{expense_id}/attachments/{attachment_id}")
def get_expense_attachment(
    expense_id: str,
    attachment_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> Response:
    attachment, data = application.expenses.get_attachment_bytes(organisation_id, expense_id, attachment_id)
    # inline, not attachment - the web UI's "View" action loads this
    # straight into PdfViewerModal's <iframe>, same as the generated
    # quote/invoice/expense PDFs; "Download" is a client-side <a download>
    # over the same bytes (see CLAUDE.md's PDF-preview conventions).
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'inline; filename="{attachment.filename}"'},
    )


@domain_router.delete("/expenses/{expense_id}/attachments/{attachment_id}", status_code=204)
def delete_expense_attachment(
    expense_id: str,
    attachment_id: str,
    application: Application = Depends(get_application),
    organisation_id: str = Depends(get_organisation_id),
) -> None:
    application.expenses.delete_attachment(organisation_id, expense_id, attachment_id)


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
        quote_validity_days=body.quote_validity_days,
        currency=body.currency,
        utr=body.utr,
        vat_number=body.vat_number,
        bank_account_name=body.bank_account_name,
        bank_sort_code=body.bank_sort_code,
        bank_account_number=body.bank_account_number,
        quote_document_header=body.quote_document_header,
        quote_document_footer=body.quote_document_footer,
        invoice_document_header=body.invoice_document_header,
        invoice_document_footer=body.invoice_document_footer,
        expense_document_header=body.expense_document_header,
        expense_document_footer=body.expense_document_footer,
        quote_number_prefix=body.quote_number_prefix,
        quote_number_digits=body.quote_number_digits,
        invoice_number_prefix=body.invoice_number_prefix,
        invoice_number_digits=body.invoice_number_digits,
        expense_number_prefix=body.expense_number_prefix,
        expense_number_digits=body.expense_number_digits,
        accent_color=body.accent_color,
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
