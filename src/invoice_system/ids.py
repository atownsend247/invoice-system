import uuid
from collections.abc import Callable

IdGenerator = Callable[[], str]


def new_id() -> str:
    """A random UUID4 string - every primary key in this app is one, not an
    autoincrementing integer, matching sessionkit's own User.id since
    v0.2.0. A sequential id leaks information it has no business leaking:
    an id in a URL or API response tells a caller roughly how many rows
    exist and in what order they were created - which nothing should be
    able to infer about another organisation's activity (see
    docs/data-model.md's Multi-tenancy). Injectable (like Clock) so tests
    can supply deterministic ids instead of asserting against a random one."""
    return str(uuid.uuid4())
