from enum import Enum

from .exceptions import InvalidOperationError


class AccountStatus(Enum):
    """Available account statuses"""

    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class Currency(Enum):
    """Available currencies"""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"

class InvestmentType(Enum):
    """Available investment types"""

    STOCK = "STOCK"
    BOND = "BOND"
    ETF = "ETF"


def parse_status(value):
    if isinstance(value, AccountStatus):
        return value
    try:
        return AccountStatus(str(value).strip().lower())
    except ValueError:
        allowed = ", ".join(item.value for item in AccountStatus)
        raise InvalidOperationError(
            f"Unknown account status: {value!r}. Expected: {allowed}."
        ) from None


def parse_currency(value):
    if isinstance(value, Currency):
        return value
    try:
        return Currency(str(value).strip().upper())
    except ValueError:
        allowed = ", ".join(item.value for item in Currency)
        raise InvalidOperationError(
            f"Unsupported currency: {value!r}. Expected: {allowed}."
        ) from None

def parse_investment_type(value):
    if isinstance(value, InvestmentType):
        return value
    try:
        return InvestmentType(str(value).strip().upper())
    except ValueError:
        allowed = ", ".join(item.value for item in InvestmentType)
        raise InvalidOperationError(
            f"Unsupported investment type: {value!r}. Expected: {allowed}."
        ) from None