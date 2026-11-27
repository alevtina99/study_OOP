from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import uuid

from .accounts import PremiumAccount
from .enums import TransactionType, TransactionStatus, parse_currency, parse_transaction_type
from .exceptions import BankingError, InsufficientFundsError, InvalidOperationError

MONEY = Decimal("0.01")
RUB_PER_UNIT = {
    "RUB": Decimal("1"),
    "USD": Decimal("100"),
    "EUR": Decimal("110"),
    "KZT": Decimal("0.20"),
    "CNY": Decimal("13"),
}

def _money(value):
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


class Transaction:
    def __init__(
        self,
        amount,
        sender=None,
        receiver=None,
        currency="RUB",
        transaction_type=TransactionType.TRANSFER,
        priority=0,
        execute_at=None,
        max_attempts=3,
        transaction_id=None,
        created_at=None,
    ):
        self._type = parse_transaction_type(transaction_type)
        self._amount = self._parse_amount(amount)
        self._currency = parse_currency(currency)
        self._fee = Decimal("0.00")
        self._sender = self._account_id(sender)
        self._receiver = self._account_id(receiver)
        self._check_participants()
        self._status = TransactionStatus.PENDING
        self._reason = None
        self._id = transaction_id or f"{uuid.uuid4().int % 10**8:08d}"
        self._priority = int(priority)
        self._execute_at = execute_at
        self._attempts = 0
        self._max_attempts = int(max_attempts)
        now = created_at or datetime.now()
        self._created_at = now
        self._updated_at = now
        self._processed_at = None
        if execute_at is not None:
            self._status = TransactionStatus.DEFERRED

    def _parse_amount(self, amount):
        if isinstance(amount, bool) or not isinstance(amount, (int, float, Decimal)):
            raise InvalidOperationError("Transaction amount must be a positive number.")
        amount = _money(amount)
        if amount <= 0:
            raise InvalidOperationError("Transaction amount must be positive.")
        return amount

    def _account_id(self, account):
        if account is None:
            return None
        return getattr(account, "account_id", account)

    def _check_participants(self):
        if self._type is TransactionType.TRANSFER and (self._sender is None or self._receiver is None):
            raise InvalidOperationError("Transfer requires a sender and a receiver.")
        if self._type is TransactionType.EXTERNAL_OUT and self._sender is None:
            raise InvalidOperationError("External outgoing transfer requires a sender.")
        if self._type is TransactionType.EXTERNAL_IN and self._receiver is None:
            raise InvalidOperationError("External incoming transfer requires a receiver.")
        if self._sender is not None and self._sender == self._receiver:
            raise InvalidOperationError("Sender and receiver must be different accounts.")

    @property
    def transaction_id(self):
        return self._id

    @property
    def type(self):
        return self._type

    @property
    def amount(self):
        return self._amount

    @property
    def currency(self):
        return self._currency

    @property
    def fee(self):
        return self._fee

    @property
    def sender(self):
        return self._sender

    @property
    def receiver(self):
        return self._receiver

    @property
    def status(self):
        return self._status

    @property
    def reason(self):
        return self._reason

    @property
    def priority(self):
        return self._priority

    @property
    def execute_at(self):
        return self._execute_at

    @property
    def attempts(self):
        return self._attempts

    @property
    def max_attempts(self):
        return self._max_attempts

    @property
    def created_at(self):
        return self._created_at

    @property
    def updated_at(self):
        return self._updated_at

    @property
    def processed_at(self):
        return self._processed_at

    @property
    def is_external(self):
        return self._type is not TransactionType.TRANSFER

    def assign_fee(self, fee):
        self._fee = _money(fee)
        self._updated_at = datetime.now()

    def defer(self, when):
        self._ensure_open()
        self._execute_at = when
        self._status = TransactionStatus.DEFERRED
        self._updated_at = datetime.now()

    def cancel(self):
        self._ensure_open()
        self._status = TransactionStatus.CANCELLED
        self._reason = "Cancelled."
        self._touch_finished()

    def record_failure(self, reason):
        self._attempts += 1
        self._reason = reason
        self._updated_at = datetime.now()
        return self._attempts < self._max_attempts

    def complete(self, when):
        self._status = TransactionStatus.COMPLETED
        self._reason = None
        self._touch_finished(when)

    def fail(self, when):
        self._status = TransactionStatus.FAILED
        self._touch_finished(when)

    def _ensure_open(self):
        if self._status not in (TransactionStatus.PENDING, TransactionStatus.DEFERRED):
            raise InvalidOperationError(f"Transaction is already {self._status.value}.")

    def _touch_finished(self, when=None):
        moment = when or datetime.now()
        self._updated_at = moment
        self._processed_at = moment

    def __str__(self):
        return (
            f"Transaction {self._id}: {self._type.value}, "
            f"{self._amount} {self._currency.value}, fee {self._fee}, "
            f"{self._sender} -> {self._receiver}, "
            f"status {self._status.value}, priority {self._priority}"
        )


class TransactionQueue:
    def __init__(self):
        self._items = {}

    def add(self, transaction):
        if transaction.transaction_id in self._items:
            raise InvalidOperationError(f"Transaction {transaction.transaction_id!r} is already queued.")
        if transaction.status not in (TransactionStatus.PENDING, TransactionStatus.DEFERRED):
            raise InvalidOperationError("Only a pending transaction can be queued.")
        self._items[transaction.transaction_id] = transaction
        return transaction

    def cancel(self, transaction_id):
        transaction = self.get(transaction_id)
        transaction.cancel()
        return transaction

    def defer(self, transaction_id, when):
        transaction = self.get(transaction_id)
        transaction.defer(when)
        return transaction

    def get(self, transaction_id):
        try:
            return self._items[transaction_id]
        except KeyError:
            raise InvalidOperationError(f"Transaction {transaction_id!r} was not found.") from None

    def ready(self, now):
        items = [
            transaction for transaction in self._items.values()
            if transaction.status in (TransactionStatus.PENDING, TransactionStatus.DEFERRED)
            and (transaction.execute_at is None or transaction.execute_at <= now)
        ]
        items.sort(key=lambda transaction: (-transaction.priority, transaction.created_at, transaction.transaction_id))
        return items

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items.values())


class TransactionProcessor:
    def __init__(self, accounts, clock=None, external_fee_rate="0.01", max_attempts=3):
        if isinstance(accounts, dict):
            self._accounts = accounts
        else:
            self._accounts = accounts._accounts
        self._clock = clock or datetime.now
        self._external_fee_rate = Decimal(str(external_fee_rate))
        self._max_attempts = int(max_attempts)
        self._errors = []
        self._processed_ids = []

    @property
    def errors(self):
        return [dict(error) for error in self._errors]

    @property
    def processed_ids(self):
        return list(self._processed_ids)

    def calculate_fee(self, transaction):
        if not transaction.is_external:
            return Decimal("0.00")
        return _money(transaction.amount * self._external_fee_rate)

    def convert(self, amount, source, target):
        source = parse_currency(source)
        target = parse_currency(target)
        if source is target:
            return _money(amount)
        rub_amount = Decimal(str(amount)) * RUB_PER_UNIT[source.value]
        return _money(rub_amount / RUB_PER_UNIT[target.value])

    def process(self, queue):
        finished = []
        for transaction in queue.ready(self._clock()):
            finished.append(self.process_one(transaction))
        return finished

    def process_one(self, transaction):
        if transaction.status not in (TransactionStatus.PENDING, TransactionStatus.DEFERRED):
            return transaction
        if transaction.execute_at is not None and transaction.execute_at > self._clock():
            return transaction
        transaction._max_attempts = min(transaction.max_attempts, self._max_attempts)
        while transaction.attempts < transaction.max_attempts:
            try:
                self._apply(transaction)
            except BankingError as exc:
                can_retry = transaction.record_failure(str(exc))
                self._errors.append({
                    "transaction_id": transaction.transaction_id,
                    "attempt": transaction.attempts,
                    "reason": str(exc),
                    "time": self._clock(),
                })
                if can_retry:
                    continue
                transaction.fail(self._clock())
                self._processed_ids.append(transaction.transaction_id)
                return transaction
            transaction.complete(self._clock())
            self._processed_ids.append(transaction.transaction_id)
            return transaction
        transaction.fail(self._clock())
        self._processed_ids.append(transaction.transaction_id)
        return transaction

    def _apply(self, transaction):
        fee = self.calculate_fee(transaction)
        transaction.assign_fee(fee)
        if transaction.type is TransactionType.EXTERNAL_IN:
            credit = transaction.amount - fee
            if credit <= 0:
                raise InvalidOperationError("Fee is greater than or equal to the incoming amount.")
            self._credit(transaction.receiver, credit, transaction.currency)
            return
        debit = transaction.amount + fee
        self._debit(transaction.sender, debit, transaction.currency)
        if transaction.type is TransactionType.TRANSFER:
            try:
                self._credit(transaction.receiver, transaction.amount, transaction.currency)
            except BankingError:
                self._credit(transaction.sender, debit, transaction.currency)
                raise

    def _debit(self, account_id, amount, currency):
        account = self._get_account(account_id)
        debit = self.convert(amount, currency, account.currency)
        if not isinstance(account, PremiumAccount) and account.balance < debit:
            raise InsufficientFundsError(
                "Transfer would make the balance negative.",
                balance=account.balance,
                amount=debit,
            )
        account.withdraw(debit)

    def _credit(self, account_id, amount, currency):
        account = self._get_account(account_id)
        account.deposit(self.convert(amount, currency, account.currency))

    def _get_account(self, account_id):
        try:
            return self._accounts[account_id]
        except KeyError:
            raise InvalidOperationError(f"Account {account_id!r} was not found.") from None
