from datetime import datetime, timezone
from typing import Callable

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(timezone.utc)
