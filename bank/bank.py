from datetime import datetime
from decimal import Decimal

from .accounts import (
    AbstractAccount,
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from .audit import audit_risk
from .client import Client
from .enums import ClientStatus, RiskLevel, parse_account_status
from .exceptions import ClientLockedError, InvalidOperationError, NightOperationError, RiskBlockedError

LARGE_WITHDRAWAL = Decimal("100000")
ACCOUNT_TYPES = {
    "bank": BankAccount,
    "savings": SavingsAccount,
    "premium": PremiumAccount,
    "investment": InvestmentAccount,
}

class Bank:
    def __init__(self, clock=None, audit_log=None, risk_analyzer=None):
        self._clients = {}
        self._accounts = {}
        self._clock = clock or datetime.now
        self._audit = audit_log
        self._risk = risk_analyzer

    def add_client(self, fio, birth_date, contacts, password, client_id=None, status="active"):
        if client_id is not None and client_id in self._clients:
            raise InvalidOperationError(f"Client {client_id!r} already exists.")
        client = Client(fio, birth_date, contacts, password, client_id, status)
        while client.client_id in self._clients:
            client = Client(fio, birth_date, contacts, password, status=status)
        self._clients[client.client_id] = client
        return client

    def set_client_status(self, client_id, status):
        client = self._get_client(client_id)
        client.set_status(status)
        return client

    def unlock_client(self, client_id):
        client = self._get_client(client_id)
        client.unlock()
        return client

    def open_account(self, client_id, account_cls=BankAccount, **account_kwargs):
        client = self._get_client(client_id)
        self._ensure_client_can_operate(client)
        account_cls = self._resolve_account_cls(account_cls)
        account_kwargs.pop("account_holder", None)
        account_kwargs.pop("client_id", None)
        account = account_cls(account_holder=client.fio, **account_kwargs)
        while account.account_id in self._accounts:
            account._id = account._generate_account_id()
        account._client_id = client.client_id
        account._clock = lambda: self._clock()
        self._accounts[account.account_id] = account
        client.add_account_id(account.account_id)
        return account

    def close_account(self, account_id):
        account = self._get_account(account_id)
        account.close()
        return account

    def freeze_account(self, account_id):
        account = self._get_account(account_id)
        account.freeze()
        return account

    def unfreeze_account(self, account_id):
        account = self._get_account(account_id)
        account.unfreeze()
        return account

    def authenticate_client(self, client_id, password):
        client = self._get_client(client_id)
        client.verify_password(password)
        return client

    def search_accounts(self, client_id=None, status=None, account_type=None):
        if status is not None:
            status = parse_account_status(status)
        if isinstance(account_type, str):
            account_type = self._resolve_account_cls(account_type)
        found = []
        for account in self._accounts.values():
            if client_id is not None and account.client_id != client_id:
                continue
            if status is not None and account.status is not status:
                continue
            if account_type is not None and not isinstance(account, account_type):
                continue
            found.append(account)
        return found

    def get_total_balance(self, client_id):
        client = self._get_client(client_id)
        totals = {}
        for account_id in client.account_ids:
            account = self._accounts[account_id]
            currency = account.currency.value
            totals[currency] = totals.get(currency, Decimal("0.00")) + account.total_value()
        return totals

    def get_clients_ranking(self):
        ranking = []
        for client in self._clients.values():
            totals = self.get_total_balance(client.client_id)
            total = sum(totals.values(), Decimal("0.00"))
            ranking.append({
                "client_id": client.client_id,
                "fio": client.fio,
                "totals": totals,
                "total": total,
            })
        ranking.sort(key=lambda item: (-item["total"], item["client_id"]))
        return ranking

    def deposit(self, account_id, amount):
        return self._operate(account_id, "deposit", amount, lambda account: account.deposit(amount))

    def withdraw(self, account_id, amount):
        account = self._operate(account_id, "withdrawal", amount, lambda account: account.withdraw(amount))
        if not isinstance(amount, bool) and isinstance(amount, (int, float, Decimal)):
            if Decimal(str(amount)) >= LARGE_WITHDRAWAL:
                client = self._get_client(account.client_id)
                client.mark_suspicious(
                    f"large withdrawal of {Decimal(str(amount))} on account {account.account_id}"
                )
        return account

    def _operate(self, account_id, action, amount, operation):
        account = self._get_account(account_id)
        client = self._get_client(account.client_id)
        self._ensure_client_can_operate(client)
        self._guard_risk(client, amount, action)
        try:
            operation(account)
        except NightOperationError:
            client.mark_suspicious(f"night {action} on account {account.account_id}")
            raise
        return account

    def _guard_risk(self, client, amount, action):
        if self._risk is None:
            return
        assessment = self._risk.assess(client.client_id, amount, self._clock())
        if self._audit is not None:
            audit_risk(self._audit, assessment, f"{action}: {assessment.summary}", self._clock())
        if assessment.level is RiskLevel.HIGH:
            raise RiskBlockedError(assessment.summary)

    def _ensure_client_can_operate(self, client):
        if client.is_locked:
            raise ClientLockedError()
        if client.status is ClientStatus.GONE:
            raise InvalidOperationError("Client is gone.")
        if client.status is ClientStatus.SLEEPING:
            raise InvalidOperationError("Sleeping client cannot perform operations.")

    def _resolve_account_cls(self, account_cls):
        if isinstance(account_cls, str):
            try:
                return ACCOUNT_TYPES[account_cls.strip().lower()]
            except KeyError:
                allowed = ", ".join(ACCOUNT_TYPES)
                raise InvalidOperationError(
                    f"Unknown account type: {account_cls!r}. Expected: {allowed}."
                ) from None
        if isinstance(account_cls, type) and issubclass(account_cls, AbstractAccount):
            return account_cls
        raise InvalidOperationError("Unknown account type.")

    def _get_client(self, client_id):
        try:
            return self._clients[client_id]
        except KeyError:
            raise InvalidOperationError(f"Client {client_id!r} was not found.") from None

    def _get_account(self, account_id):
        try:
            return self._accounts[account_id]
        except KeyError:
            raise InvalidOperationError(f"Account {account_id!r} was not found.") from None
