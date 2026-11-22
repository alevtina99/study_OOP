from enum import Enum

from .exceptions import InvalidOperationError


class AccountStatus(Enum):
    """Допустимые статусы счёта."""

    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class Currency(Enum):
    """Допустимые валюты счёта."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


def parse_status(value):
    if isinstance(value, AccountStatus):
        return value
    try:
        return AccountStatus(str(value).strip().lower())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in AccountStatus)
        raise InvalidOperationError(
            f"Unknown account status: {value!r}. Expected: {allowed}."
        ) from exc


def parse_currency(value):
    if isinstance(value, Currency):
        return value
    try:
        return Currency(str(value).strip().upper())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in Currency)
        raise InvalidOperationError(
            f"Unsupported currency: {value!r}. Expected: {allowed}."
        ) from exc
