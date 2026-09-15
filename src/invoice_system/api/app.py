import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from ..errors import AppError, Duplicate, InvalidTransition, NotFound, ValidationFailed
from ..factory import Application, build_application
from ..pdf import render_invoice_pdf, render_quote_pdf
from .schemas import AccountIn, AccountOut, InvoiceOut, LineItemIn, QuoteCreateIn, QuoteOut

_STATUS_BY_ERROR: list[tuple[type[AppError], int]] = [
    (NotFound, 404),
    (Duplicate, 409),
    (InvalidTransition, 409),
    (ValidationFailed, 422),
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_path = os.environ.get("INVOICE_SYSTEM_DB", "invoice_system.db")
    app.state.application = build_application(db_path)
    yield
    app.state.application.close()


app = FastAPI(title="Invoice System API", lifespan=lifespan)


def get_application(request: Request) -> Application:
    return request.app.state.application


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    for error_type, status_code in _STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})
    raise exc


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountIn, application: Application = Depends(get_application)) -> AccountOut:
    account = application.accounts.create_account(
        business_name=body.business_name,
        contact_name=body.contact_name,
        email=body.email,
        phone=body.phone,
        address=body.address,
    )
    return AccountOut.from_model(account)


@app.get("/accounts", response_model=list[AccountOut])
def list_accounts(application: Application = Depends(get_application)) -> list[AccountOut]:
    return [AccountOut.from_model(a) for a in application.accounts.list_accounts()]


@app.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(account_id: int, application: Application = Depends(get_application)) -> AccountOut:
    return AccountOut.from_model(application.accounts.get_account(account_id))


@app.post("/quotes", response_model=QuoteOut, status_code=201)
def create_quote(body: QuoteCreateIn, application: Application = Depends(get_application)) -> QuoteOut:
    quote = application.quotes.create_quote(
        account_id=body.account_id, currency=body.currency, expiry_date=body.expiry_date
    )
    return QuoteOut.from_model(quote)


@app.get("/quotes", response_model=list[QuoteOut])
def list_quotes(
    account_id: int | None = None, application: Application = Depends(get_application)
) -> list[QuoteOut]:
    return [QuoteOut.from_model(q) for q in application.quotes.list_quotes(account_id=account_id)]


@app.get("/quotes/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: int, application: Application = Depends(get_application)) -> QuoteOut:
    return QuoteOut.from_model(application.quotes.get_quote(quote_id))


@app.post("/quotes/{quote_id}/line-items", response_model=QuoteOut, status_code=201)
def add_quote_line_item(
    quote_id: int, body: LineItemIn, application: Application = Depends(get_application)
) -> QuoteOut:
    quote = application.quotes.add_line_item(
        quote_id,
        description=body.description,
        quantity=Decimal(body.quantity),
        unit_price=Decimal(body.unit_price),
    )
    return QuoteOut.from_model(quote)


@app.post("/quotes/{quote_id}/send", response_model=QuoteOut)
def send_quote(quote_id: int, application: Application = Depends(get_application)) -> QuoteOut:
    return QuoteOut.from_model(application.quotes.send(quote_id))


@app.post("/quotes/{quote_id}/convert", response_model=InvoiceOut, status_code=201)
def convert_quote(quote_id: int, application: Application = Depends(get_application)) -> InvoiceOut:
    return InvoiceOut.from_model(application.quotes.convert_to_invoice(quote_id))


@app.get("/quotes/{quote_id}/pdf")
def get_quote_pdf(quote_id: int, application: Application = Depends(get_application)) -> Response:
    quote = application.quotes.get_quote(quote_id)
    account = application.accounts.get_account(quote.account_id)
    return Response(content=render_quote_pdf(account, quote), media_type="application/pdf")


@app.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(
    account_id: int | None = None, application: Application = Depends(get_application)
) -> list[InvoiceOut]:
    return [InvoiceOut.from_model(i) for i in application.invoices.list_invoices(account_id=account_id)]


@app.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, application: Application = Depends(get_application)) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.get_invoice(invoice_id))


@app.post("/invoices/{invoice_id}/send", response_model=InvoiceOut)
def send_invoice(invoice_id: int, application: Application = Depends(get_application)) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.send(invoice_id))


@app.post("/invoices/{invoice_id}/void", response_model=InvoiceOut)
def void_invoice(invoice_id: int, application: Application = Depends(get_application)) -> InvoiceOut:
    return InvoiceOut.from_model(application.invoices.void(invoice_id))


@app.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: int, application: Application = Depends(get_application)) -> Response:
    invoice = application.invoices.get_invoice(invoice_id)
    account = application.accounts.get_account(invoice.account_id)
    return Response(content=render_invoice_pdf(account, invoice), media_type="application/pdf")
