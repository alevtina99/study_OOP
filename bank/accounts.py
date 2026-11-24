from abc import ABC, abstractmethod
from decimal import Decimal
from locale import currency
import uuid

from .exceptions import AccountFrozenError, AccountClosedError, InvalidOperationError, InsufficientFundsError
from .enums import AccountStatus, Currency, InvestmentType, parse_status, parse_currency, parse_investment_type


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
        if isinstance(amount, bool) or not isinstance(amount, (int, float, Decimal)):
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
        if Decimal(str(amount)) > self._balance:
            raise InsufficientFundsError("Insufficient funds for withdrawal.", balance=self._balance, amount=amount)
        self._balance -= Decimal(str(amount))
        print(f"Withdrew {amount} {self._currency.value}. New balance: {self._balance} {self._currency.value}.")

    def get_account_info(self):
        return {
            "account_id": self._id,
            "account_holder": self._holder,
            "status": self._status,
            "balance": self._balance,
            "currency": self._currency
        }


class SavingsAccount(BankAccount):
    def __init__(self, account_id=None, account_holder="", account_status="active", \
                 interest_rate=0.01, min_balance=0):
        super().__init__(account_id, account_holder, account_status)
        self._min_balance = Decimal(str(min_balance))
        self._interest_rate = Decimal(str(interest_rate))

    def __str__(self):
        return (
            super().__str__() + ", "
            f"Interest Rate: {self._interest_rate * 100}%, "
            f"Minimum Balance: {self._min_balance} {self._currency.value}")

    def apply_monthly_interest(self):
        self._validate_active_status()
        interest = self._balance * self._interest_rate
        self._balance += interest
        print(f"Applied monthly interest: {interest} {self._currency.value}. New balance: {self._balance} {self._currency.value}.")

    def withdraw(self, amount):
        self._validate_amount(amount)
        self._validate_active_status()
        if (self._balance - Decimal(str(amount))) < self._min_balance:
            raise InsufficientFundsError("Withdrawal would breach minimum balance requirement.",
                                            balance=self._balance, amount=amount, min_balance=self._min_balance)
        self._balance -= Decimal(str(amount))
        print(f"Withdrew {amount} {self._currency.value}. New balance: {self._balance} {self._currency.value}.")

    def get_account_info(self):
        info = super().get_account_info()
        info.update({
            "interest_rate": self._interest_rate,
            "min_balance": self._min_balance
        })
        return info

    
class PremiumAccount(BankAccount):
    def __init__(self, account_id=None, account_holder="", account_status="active", \
                 overdraft_limit=1000, commission_fixed=0.01):
        super().__init__(account_id, account_holder, account_status)
        self._overdraft_limit = Decimal(str(overdraft_limit))
        self._commission_fixed = Decimal(str(commission_fixed))

    def __str__(self):
        return (
            super().__str__() + ", "
            f"Overdraft Limit: {self._overdraft_limit} {self._currency.value}, "
            f"Commission Fixed: {self._commission_fixed * 100}%")


    def withdraw(self, amount):
        self._validate_amount(amount)
        self._validate_active_status()
        if (self._balance - Decimal(str(amount)) - self._commission_fixed) < -self._overdraft_limit:
            raise InsufficientFundsError("Withdrawal would exceed overdraft limit.",
                                            balance=self._balance, amount=(amount+self._commission_fixed), overdraft_limit=-self._overdraft_limit)
        self._balance -= (Decimal(str(amount)) + self._commission_fixed)
        print(f"Withdrew {amount} {self._currency.value}. New balance: {self._balance} {self._currency.value}.")

    def get_account_info(self):
        info = super().get_account_info()
        info.update({
            "overdraft_limit": self._overdraft_limit,
            "commission_fixed": self._commission_fixed
        })
        return info


class AmountMap(dict):
    def __str__(self):
        parts = (
            f"{key.value if isinstance(key, InvestmentType) else key}: {Decimal(value):.2f}"
            for key, value in self.items()
        )
        return "{" + ", ".join(parts) + "}"

    __repr__ = __str__

    
class InvestmentAccount(BankAccount):
    def __init__(self, account_id=None, account_holder="", account_status="active"):
        super().__init__(account_id, account_holder, account_status)
        self._portfolio = AmountMap({
            InvestmentType.STOCK: Decimal('0.00'),
            InvestmentType.BOND: Decimal('0.00'),
            InvestmentType.ETF: Decimal('0.00')})

    def __str__(self):
        return (
            super().__str__() + ", " +
            f"Portfolio: {self._portfolio}")

    def buy_funds(self, investment_type, amount):
        investment_type = parse_investment_type(investment_type)
        self._validate_amount(amount)
        self._validate_active_status()
        if Decimal(str(amount)) > self._balance:
            raise InsufficientFundsError("Not enough balance to buy.", balance=self._balance, amount=amount)
        self._portfolio[investment_type] += Decimal(str(amount))
        self._balance -= Decimal(str(amount))
        print(f"Bought {amount} {self._currency.value} of {investment_type.value}. New portfolio: {self._portfolio}. New balance: {self._balance} {self._currency.value}.")

    def sell_funds(self, investment_type, amount):
        investment_type = parse_investment_type(investment_type)
        self._validate_amount(amount)
        self._validate_active_status()
        if self._portfolio[investment_type] < Decimal(str(amount)):
            raise InsufficientFundsError("Not enough funds to sell.", portfolio=self._portfolio, amount=amount)
        self._portfolio[investment_type] -= Decimal(str(amount))
        self._balance += Decimal(str(amount))
        print(f"Sold {amount} {self._currency.value} of {investment_type.value}. New portfolio: {self._portfolio}. New balance: {self._balance} {self._currency.value}.")
    
    def withdraw(self, amount):
        self._validate_amount(amount)
        self._validate_active_status()
        if Decimal(str(amount)) > self._balance:
            raise InsufficientFundsError("Insufficient funds for withdrawal.", balance=self._balance, amount=amount)
        self._balance -= Decimal(str(amount))
        print(f"Withdrew {amount} {self._currency.value}. New balance: {self._balance} {self._currency.value}.")

    def project_yearly_growth(self, growth_rates):
        self._validate_active_status()
        growth_rates = {parse_investment_type(k): Decimal(str(v)) for k, v in growth_rates.items()}
        projected_growth = AmountMap()
        for investment_type, amount in self._portfolio.items():
            if investment_type not in growth_rates:
                raise InvalidOperationError(f"Growth rate for {investment_type} not provided.")
            growth_rate = Decimal(str(growth_rates[investment_type]))
            projected_growth[investment_type] = amount * growth_rate
        print(f"Projected yearly growth based on provided rates: {projected_growth}.")

    def get_account_info(self):
        info = super().get_account_info()
        info.update({
            "portfolio": self._portfolio
        })
        return info
