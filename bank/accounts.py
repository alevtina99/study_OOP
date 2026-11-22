from abc import ABC, abstractmethod
from decimal import Decimal
from locale import currency
import uuid

from .exceptions import AccountFrozenError, AccountClosedError, InvalidOperationError, InsufficientFundsError
from .enums import AccountStatus, Currency, parse_status, parse_currency

# Абстрактный класс для представления банковского счета
class AbstractAccount(ABC):
    def __init__(self, account_id=None, account_holder="", account_status="active"):
        self._id = account_id if account_id else self._generate_account_id()
        self._holder = account_holder
        self._balance = Decimal("0.00") # Используем Decimal для точного представления денежных сумм
        self._status = parse_status(account_status)

    @property
    def balance(self):
        return self._balance
    
    def _generate_account_id(self) -> str:
        return f"{uuid.uuid4().int % 10**8:08d}" # str(uuid.uuid4())[:8] or uuid.uuid4().hex[:8] if characters allowed
    
    @abstractmethod
    def deposit(self, amount):
        pass

    @abstractmethod
    def withdraw(self, amount):
        pass

    @abstractmethod
    def get_account_info(self):
        pass

# Реализация конкретного типа счета
class BankAccount(AbstractAccount):
    def __init__(self, account_id=None, account_holder="", account_status="active"):
        super().__init__(account_id, account_holder, account_status)
        self._currency = parse_currency("RUB") # RUB, USD, EUR, KZT, CNY

    def __str__(self):
        return (
            f"{type(self).__name__}: "
            f"Account holder: {self._holder}, "
            f"Account ID: *{self._id[-4:]}, "
            f"Status: {self._status.value}, "
            f"Balance: {self._balance} {self._currency.value}")

    def _validate_active_status(self):
        if self._status == AccountStatus.FROZEN:
            raise AccountFrozenError("Operation cannot be performed on a frozen account.")
        elif self._status == AccountStatus.CLOSED:
            raise AccountClosedError("Operation cannot be performed on a closed account.")
        
    def _validate_amount(self, amount):
        if not isinstance(amount, (int, float, Decimal)):
            raise InvalidOperationError(f"Amount must be a positive number. Got {type(amount).__name__}.")
        if amount <= 0:
            raise InvalidOperationError("Amount must be positive.")

    def deposit(self, amount):
        self._validate_amount(amount)
        self._validate_active_status()
        self._balance += Decimal(str(amount))
        print(f"Deposited {amount} {self._currency.value}. New balance: {self._balance} {self._currency.value}.")

    def withdraw(self, amount):
        self._validate_amount(amount)
        self._validate_active_status()
        if amount > self._balance:
            raise InsufficientFundsError("Insufficient funds for withdrawal.", balance=self._balance, amount=amount)
        self._balance -= Decimal(str(amount))
        print(f"Withdrew {amount} {self._currency.value}. New balance: {self._balance} {self._currency.value}.")

    def get_account_info(self):
        return {
            "account_id": self._id,
            "account_holder": self._holder,
            "balance": self._balance,
            "currency": self._currency,
            "status": self._status
        }