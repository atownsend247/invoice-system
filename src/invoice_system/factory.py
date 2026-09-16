from pathlib import Path

from .clock import Clock, system_clock
from .core import AccountService, BusinessProfileService, InvoiceService, QuoteService, StatsService
from .repository import Repository
from .storage.sqlite_repository import SqliteRepository


class Application:
    def __init__(
        self,
        repository: Repository,
        accounts: AccountService,
        quotes: QuoteService,
        invoices: InvoiceService,
        business_profiles: BusinessProfileService,
        stats: StatsService,
    ) -> None:
        self.repository = repository
        self.accounts = accounts
        self.quotes = quotes
        self.invoices = invoices
        self.business_profiles = business_profiles
        self.stats = stats

    def close(self) -> None:
        self.repository.close()

    def __enter__(self) -> "Application":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def build_application(db_path: str | Path, clock: Clock = system_clock) -> Application:
    repository = SqliteRepository(db_path)
    repository.migrate()
    return Application(
        repository=repository,
        accounts=AccountService(repository, clock=clock),
        quotes=QuoteService(repository, clock=clock),
        invoices=InvoiceService(repository, clock=clock),
        business_profiles=BusinessProfileService(repository, clock=clock),
        stats=StatsService(repository, clock=clock),
    )
