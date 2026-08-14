from contextvars import ContextVar
from datetime import UTC, datetime

_clock_override: ContextVar[datetime | None] = ContextVar("phase3_clock", default=None)


def utc_now() -> datetime:
    override = _clock_override.get()
    if override is not None:
        return override if override.tzinfo else override.replace(tzinfo=UTC)
    return datetime.now(UTC)


def set_clock(value: datetime | None) -> None:
    _clock_override.set(value)


class frozen_clock:
    def __init__(self, value: datetime) -> None:
        self.value = value
        self._token = None

    def __enter__(self) -> datetime:
        self._token = _clock_override.set(self.value)
        return self.value

    def __exit__(self, *args: object) -> None:
        if self._token is not None:
            _clock_override.reset(self._token)
