from abc import ABC, abstractmethod
import uuid

from errors import AccountFrozenError, AccountClosedError, InvalidOperationError, InsufficientFundsError

# Абстрактный класс для представления банковского счета
class AbstractAccount(ABC):
    def __init__(self, account_id=None, account_holder="", account_status="active"):
        self.account_id = account_id if account_id else self._generate_account_id()
        self.account_holder = account_holder
        self.protected_balance = 0.0
        self.account_status = account_status # active, frozen, closed

    def _generate_account_id(self) -> str:
        return str(uuid.uuid4())[:8] # uuid.uuid4().hex[:8]
    
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
        self.currency = "RUB" # RUB, USD, EUR, KZT, CNY
        if not self.account_id:
            self.account_id = self.__generate_account_id__()

    def __str__(self):
        return f"BankAccount, \n \
            Account holder: {self.account_holder}, Account ID: *{self.account_id[-4:]}, Status: {self.account_status} \n \
            Balance: {self.protected_balance} {self.currency}"

    def deposit(self, amount):
        if self.account_status == "frozen":
            raise AccountFrozenError("Cannot deposit to a frozen account.")
        elif self.account_status == "closed":
            raise AccountClosedError("Cannot deposit to a closed account.")
        elif amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self.protected_balance += amount
        print(f"Deposited {amount} {self.currency}. New balance: {self.protected_balance} {self.currency}.")

    def withdraw(self, amount):
        if self.account_status == "frozen":
            raise AccountFrozenError("Cannot withdraw from a frozen account.")
        elif self.account_status == "closed":
            raise AccountClosedError("Cannot withdraw from a closed account.")
        elif amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        elif amount > self.protected_balance:
            raise InsufficientFundsError("Insufficient funds for withdrawal.")
        self.protected_balance -= amount
        print(f"Withdrew {amount} {self.currency}. New balance: {self.protected_balance} {self.currency}.")

    def get_account_info(self):
        return {
            "account_id": self.account_id,
            "account_holder": self.account_holder,
            "balance": self.protected_balance,
            "currency": self.currency,
            "status": self.account_status
        }