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
from ..pdf import render_invoice_pdf, render_quote_pdf
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
def create_account(body: AccountIn, application: Application = Depends(get_application)) -> AccountOut:
    account = application.accounts.create_account(
        business_name=body.business_name,
        contact_name=body.contact_name,
        email=body.email,
        phone=body.phone,
        address=body.address,
    )
    return AccountOut.from_model(account)


@domain_router.get("/accounts", response_model=list[AccountOut])
def list_accounts(application: Application = Depends(get_application)) -> list[AccountOut]:
    return [AccountOut.from_model(a) for a in application.accounts.list_accounts()]


@domain_router.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(account_id: int, application: Application = Depends(get_application)) -> AccountOut:
    return AccountOut.from_model(application.accounts.get_account(account_id))


@domain_router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, body: AccountIn, application: Application = Depends(get_application)
) -> AccountOut:
    account = application.accounts.update_account(
        account_id,
        business_name=body.business_name,
        contact_name=body.contact_name,
        email=body.email,
        phone=body.phone,
        address=body.address,
    )
    return AccountOut.from_model(account)


@domain_router.post("/quotes", response_model=QuoteOut, status_code=201)
def create_quote(body: QuoteCreateIn, application: Application = Depends(get_application)) -> QuoteOut:
    quote = application.quotes.create_quote(
        account_id=body.account_id, currency=body.currency, expiry_date=body.expiry_date
    )
    return QuoteOut.from_model(quote)


@domain_router.get("/quotes", response_model=list[QuoteOut])
def list_quotes(
    account_id: int | None = None, application: Application = Depends(get_application)
) -> list[QuoteOut]:
    return [QuoteOut.from_model(q) for q in application.quotes.list_quotes(account_id=account_id)]


@domain_router.get("/quotes/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: int, application: Application = Depends(get_application)) -> QuoteOut:
    return QuoteOut.from_model(application.quotes.get_quote(quote_id))


@domain_router.post("/quotes/{quote_id}/line-items", response_model=QuoteOut, status_code=201)
def add_quote_line_item(
    quote_id: int, body: LineItemIn, application: Application = Depends(get_application)
) -> QuoteOut:
    quote = application.quotes.add_line_item(
        quote_id,
        description=body.description,
        quantity=Decimal(body.quantity),
        unit_price=Decimal(body.unit_price),
        tax_rate=Decimal(body.tax_rate),
    )
    return QuoteOut.from_model(quote)


@domain_router.post("/quotes/{quote_id}/send", response_model=QuoteOut)
def send_quote(quote_id: int, application: Application = Depends(get_application)) -> QuoteOut:
    return QuoteOut.from_model(application.quotes.send(quote_id))


@domain_router.post("/quotes/{quote_id}/convert", response_model=InvoiceOut, status_code=201)
def convert_quote(quote_id: int, application: Application = Depends(get_application)) -> InvoiceOut:
    return InvoiceOut.from_model(application.quotes.convert_to_invoice(quote_id))


@domain_router.get("/quotes/{quote_id}/pdf")
def get_quote_pdf(
    quote_id: int,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
) -> Response:
    quote = application.quotes.get_quote(quote_id)
    account = application.accounts.get_account(quote.account_id)
    profile = application.business_profiles.get_profile(user.id)
    return Response(content=render_quote_pdf(account, quote, profile), media_type="application/pdf")


@domain_router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(
    account_id: int | None = None, application: Application = Depends(get_application)
) -> list[InvoiceOut]:
    return [InvoiceOut.from_model(i) for i in application.invoices.list_invoices(account_id=account_id)]


@domain_router.get("/invoices/monthly-totals", response_model=MonthlyTotalsReportOut)
def invoice_monthly_totals(
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
) -> MonthlyTotalsReportOut:
    # Registered before /invoices/{invoice_id} - a fixed path segment would
    # otherwise be swallowed by that route's int path param and 422.
    profile = application.business_profiles.get_profile(user.id)
    totals = application.invoices.monthly_totals(profile.currency)
    return MonthlyTotalsReportOut.from_models(profile.currency, totals)


@domain_router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, application: Application = Depends(get_application)) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.get_invoice(invoice_id))


@domain_router.post("/invoices/{invoice_id}/send", response_model=InvoiceOut)
def send_invoice(
    invoice_id: int,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
) -> InvoiceOut:
    profile = application.business_profiles.get_profile(user.id)
    invoice = application.invoices.send(invoice_id, payment_terms_days=profile.payment_terms_days)
    return InvoiceOut.from_model(invoice)


@domain_router.post("/invoices/{invoice_id}/void", response_model=InvoiceOut)
def void_invoice(invoice_id: int, application: Application = Depends(get_application)) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.void(invoice_id))


@domain_router.post("/invoices/{invoice_id}/pay", response_model=InvoiceOut)
def pay_invoice(invoice_id: int, application: Application = Depends(get_application)) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.pay(invoice_id))


@domain_router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: int,
    application: Application = Depends(get_application),
    user: SessionUser = Depends(get_current_user),
) -> Response:
    invoice = application.invoices.get_invoice(invoice_id)
    account = application.accounts.get_account(invoice.account_id)
    profile = application.business_profiles.get_profile(user.id)
    return Response(content=render_invoice_pdf(account, invoice, profile), media_type="application/pdf")


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
    )
    return BusinessProfileOut.from_model(profile)


@domain_router.get("/stats", response_model=StatsOut)
def get_stats(application: Application = Depends(get_application)) -> StatsOut:
    return StatsOut.from_model(application.stats.get_stats())


app.include_router(domain_router)
