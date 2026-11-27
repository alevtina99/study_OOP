from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from bank.accounts import BankAccount, PremiumAccount
from bank.transactions import (
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
    TransactionType,
)
from bank.exceptions import InvalidOperationError

DAY = datetime(2026, 11, 26, 15, 0)


def at_day(account, balance=0):
    account._clock = lambda: DAY
    if balance:
        account.deposit(balance)
    return account


def test_internal_transfer_and_external_fee():
    source = at_day(BankAccount("10000001", "Anna"), 1000)
    target = at_day(BankAccount("10000002", "Boris"))
    accounts = {source.account_id: source, target.account_id: target}
    processor = TransactionProcessor(accounts, clock=lambda: DAY)
    queue = TransactionQueue()
    internal = Transaction(100, source, target, priority=1)
    external = Transaction(100, source, transaction_type=TransactionType.EXTERNAL_OUT)
    queue.add(internal)
    queue.add(external)
    processor.process(queue)
    assert internal.status is TransactionStatus.COMPLETED
    assert internal.fee == Decimal("0.00")
    assert external.status is TransactionStatus.COMPLETED
    assert external.fee == Decimal("1.00")
    assert source.balance == Decimal("799.00")
    assert target.balance == Decimal("100.00")


def test_premium_can_go_negative_and_regular_cannot():
    regular = at_day(BankAccount("20000001", "Anna"), 10)
    premium = at_day(PremiumAccount("20000002", "Boris", commission_fixed="0", overdraft_limit="100"))
    target = at_day(BankAccount("20000003", "Clara"))
    accounts = {item.account_id: item for item in (regular, premium, target)}
    processor = TransactionProcessor(accounts, clock=lambda: DAY, max_attempts=1)
    queue = TransactionQueue()
    denied = Transaction(50, regular, target)
    allowed = Transaction(40, premium, target)
    queue.add(denied)
    queue.add(allowed)
    processor.process(queue)
    assert denied.status is TransactionStatus.FAILED
    assert regular.balance == Decimal("10.00")
    assert allowed.status is TransactionStatus.COMPLETED
    assert premium.balance == Decimal("-40.00")
    assert target.balance == Decimal("40.00")


def test_frozen_account_is_rejected_and_recorded():
    frozen = at_day(BankAccount("30000001", "Anna"), 500)
    frozen.freeze()
    target = at_day(BankAccount("30000002", "Boris"))
    processor = TransactionProcessor(
        {frozen.account_id: frozen, target.account_id: target},
        clock=lambda: DAY,
        max_attempts=3,
    )
    queue = TransactionQueue()
    transaction = Transaction(20, frozen, target, max_attempts=3)
    queue.add(transaction)
    processor.process(queue)
    assert transaction.status is TransactionStatus.FAILED
    assert transaction.attempts == 3
    assert len(processor.errors) == 3
    assert frozen.balance == Decimal("500")


def test_priority_deferred_and_cancel():
    source = at_day(BankAccount("40000001", "Anna"), 1000)
    target = at_day(BankAccount("40000002", "Boris"))
    processor = TransactionProcessor(
        {source.account_id: source, target.account_id: target},
        clock=lambda: DAY,
    )
    queue = TransactionQueue()
    low = Transaction(10, source, target, priority=1, transaction_id="00000001")
    high = Transaction(10, source, target, priority=5, transaction_id="00000002")
    later = Transaction(10, source, target, execute_at=DAY + timedelta(days=1), transaction_id="00000003")
    cancelled = Transaction(10, source, target, transaction_id="00000004")
    for transaction in (low, high, later, cancelled):
        queue.add(transaction)
    queue.cancel(cancelled.transaction_id)
    processed = processor.process(queue)
    assert [item.transaction_id for item in processed] == ["00000002", "00000001"]
    assert later.status is TransactionStatus.DEFERRED
    assert cancelled.status is TransactionStatus.CANCELLED
    with pytest.raises(InvalidOperationError):
        queue.cancel(cancelled.transaction_id)


def test_ten_transactions_are_queued_and_processed():
    source = at_day(BankAccount("50000001", "Anna"), 5000)
    first = at_day(BankAccount("50000002", "Boris"))
    second = at_day(BankAccount("50000003", "Clara"))
    premium = at_day(PremiumAccount("50000004", "Dmitry", commission_fixed="0"))
    frozen = at_day(BankAccount("50000005", "Eva"), 100)
    frozen.freeze()
    accounts = {item.account_id: item for item in (source, first, second, premium, frozen)}
    processor = TransactionProcessor(accounts, clock=lambda: DAY)
    queue = TransactionQueue()
    transactions = [
        Transaction(100, source, first, priority=1, transaction_id="00000010"),
        Transaction(200, source, second, priority=3, transaction_id="00000011"),
        Transaction(50, source, premium, priority=2, transaction_id="00000012"),
        Transaction(75, source, transaction_type=TransactionType.EXTERNAL_OUT, transaction_id="00000013"),
        Transaction(25, sender=None, receiver=first, transaction_type=TransactionType.EXTERNAL_IN, transaction_id="00000014"),
        Transaction(10, premium, second, priority=4, transaction_id="00000015"),
        Transaction(30, source, second, priority=0, transaction_id="00000016"),
        Transaction(15, source, first, execute_at=DAY + timedelta(days=2), transaction_id="00000017"),
        Transaction(40, frozen, first, transaction_id="00000018"),
        Transaction(5, source, first, transaction_id="00000019"),
    ]
    for transaction in transactions:
        queue.add(transaction)
    assert len(queue) == 10
    processed = processor.process(queue)
    assert len(processed) == 9
    assert transactions[7].status is TransactionStatus.DEFERRED
    assert transactions[8].status is TransactionStatus.FAILED
    completed = [item for item in transactions if item.status is TransactionStatus.COMPLETED]
    assert len(completed) == 8
    assert processed[0].transaction_id == "00000015"
