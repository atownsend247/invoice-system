from pathlib import Path

from .attachments import DEFAULT_ATTACHMENTS_DIR, AttachmentStore
from .clock import Clock, system_clock
from .core import (
    AccountService,
    BusinessProfileService,
    DomainService,
    ExpenseService,
    InvoiceService,
    OrganisationService,
    QuoteService,
    RegistrarService,
    RegistrationInviteService,
    StatsService,
)
from .repository import Repository
from .storage.sqlite_repository import SqliteRepository


class Application:
    def __init__(
        self,
        repository: Repository,
        organisations: OrganisationService,
        accounts: AccountService,
        domains: DomainService,
        registrars: RegistrarService,
        quotes: QuoteService,
        invoices: InvoiceService,
        expenses: ExpenseService,
        business_profiles: BusinessProfileService,
        stats: StatsService,
        registration_invites: RegistrationInviteService,
        attachment_store: AttachmentStore,
    ) -> None:
        self.repository = repository
        self.organisations = organisations
        self.accounts = accounts
        self.domains = domains
        self.registrars = registrars
        self.quotes = quotes
        self.invoices = invoices
        self.expenses = expenses
        self.business_profiles = business_profiles
        self.stats = stats
        self.registration_invites = registration_invites
        self.attachment_store = attachment_store

    def close(self) -> None:
        self.repository.close()

    def __enter__(self) -> "Application":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def build_application(
    db_path: str | Path,
    clock: Clock = system_clock,
    attachments_dir: str | Path = DEFAULT_ATTACHMENTS_DIR,
) -> Application:
    repository = SqliteRepository(db_path)
    repository.migrate()
    attachment_store = AttachmentStore(attachments_dir)
    return Application(
        repository=repository,
        organisations=OrganisationService(repository, clock=clock),
        accounts=AccountService(repository, clock=clock),
        domains=DomainService(repository, clock=clock),
        registrars=RegistrarService(repository, clock=clock),
        quotes=QuoteService(repository, clock=clock),
        invoices=InvoiceService(repository, clock=clock),
        expenses=ExpenseService(repository, clock=clock, attachments=attachment_store),
        business_profiles=BusinessProfileService(repository, clock=clock),
        stats=StatsService(repository, clock=clock),
        registration_invites=RegistrationInviteService(repository, clock=clock),
        attachment_store=attachment_store,
    )
