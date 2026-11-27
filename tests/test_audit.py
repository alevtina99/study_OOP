from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from bank.accounts import BankAccount
from bank.audit import AuditLog, RiskAnalyzer
from bank.bank import Bank
from bank.enums import AuditLevel, RiskLevel
from bank.exceptions import RiskBlockedError
from bank.transactions import Transaction, TransactionProcessor, TransactionQueue, TransactionStatus

DAY = datetime(2026, 11, 26, 15, 0)
NIGHT = datetime(2026, 11, 26, 2, 0)


def funded(account_id, holder, client_id, balance):
    account = BankAccount(account_id, holder)
    account._client_id = client_id
    account._clock = lambda: DAY
    if balance > 0:
        account.deposit(balance)
    return account


def test_audit_log_filters_and_reloads_from_file(tmp_path):
    path = tmp_path / "audit.log"
    log = AuditLog(path)
    log.log("info", "ordinary transfer", client_id="anna", time=DAY)
    log.log("warning", "large amount", client_id="boris", time=DAY)
    log.log("error", "not enough money", client_id="anna", time=DAY)
    assert [entry.level for entry in log.filter(client_id="anna")] == [AuditLevel.INFO, AuditLevel.ERROR]
    assert [entry.level for entry in log.filter(min_level="warning")] == [AuditLevel.WARNING, AuditLevel.ERROR]
    restored = AuditLog(path)
    restored.load()
    assert len(restored) == 3
    assert restored.error_statistics()["errors"] == 1


def test_high_risk_transfer_is_blocked_and_low_risk_passes():
    anna = funded("10000001", "Anna", "anna", 5000)
    boris = funded("10000002", "Boris", "boris", 0)
    accounts = {anna.account_id: anna, boris.account_id: boris}
    analyzer = RiskAnalyzer(large_amount="1000", frequent_limit=5)
    log = AuditLog()
    processor = TransactionProcessor(accounts, clock=lambda: DAY, risk_analyzer=analyzer, audit_log=log)
    queue = TransactionQueue()
    ordinary = Transaction(100, anna, boris, created_at=DAY, transaction_id="00000001")
    dangerous = Transaction(1500, anna, boris, created_at=NIGHT, transaction_id="00000002")
    queue.add(ordinary)
    queue.add(dangerous)
    processor.process(queue)
    assert ordinary.status is TransactionStatus.COMPLETED
    assert ordinary.attempts == 0
    assert dangerous.status is TransactionStatus.FAILED
    assert dangerous.attempts == 1
    assert anna.balance == Decimal("4900.00")
    assert boris.balance == Decimal("100.00")
    assert analyzer.suspicious_operations()[0].level is RiskLevel.HIGH
    assert log.filter(level="critical")[0].transaction_id == "00000002"


def test_new_account_and_frequency_build_client_profile():
    anna = funded("20000001", "Anna", "anna", 5000)
    first = funded("20000002", "Boris", "boris", 0)
    second = funded("20000003", "Clara", "clara", 0)
    accounts = {item.account_id: item for item in (anna, first, second)}
    analyzer = RiskAnalyzer(large_amount="1000", frequent_limit=3, frequent_window=timedelta(minutes=10))
    processor = TransactionProcessor(accounts, clock=lambda: DAY, risk_analyzer=analyzer, audit_log=AuditLog())
    queue = TransactionQueue()
    moment = DAY
    transactions = [
        Transaction(100, anna, first, created_at=moment, transaction_id="00000011"),
        Transaction(100, anna, first, created_at=moment + timedelta(minutes=1), transaction_id="00000012"),
        Transaction(100, anna, second, created_at=moment + timedelta(minutes=2), transaction_id="00000013"),
    ]
    for transaction in transactions:
        queue.add(transaction)
    processor.process(queue)
    assert transactions[0].status is TransactionStatus.COMPLETED
    assert transactions[1].status is TransactionStatus.COMPLETED
    assert transactions[2].status is TransactionStatus.FAILED
    profile = analyzer.client_risk_profile("anna")
    assert profile["known_recipients"] == [first.account_id]
    assert profile["signals"]["frequent operations"] == 1
    assert profile["signals"]["new account"] == 1
    assert profile["highest_risk"] == "high"


def test_bank_blocks_a_dangerous_withdrawal():
    log = AuditLog()
    analyzer = RiskAnalyzer(large_amount="1000")
    bank = Bank(clock=lambda: NIGHT, audit_log=log, risk_analyzer=analyzer)
    anna = bank.add_client("Anna Ivanova", "2000-01-01", {"phone": "+7999"}, "secret")
    account = bank.open_account(anna.client_id)
    bank._clock = lambda: DAY
    bank.deposit(account.account_id, 5000)
    bank._clock = lambda: NIGHT
    with pytest.raises(RiskBlockedError):
        bank.withdraw(account.account_id, 1500)
    assert account.balance == Decimal("5000")
    profile = analyzer.client_risk_profile(anna.client_id)
    assert profile["highest_risk"] == "high"
    assert log.error_statistics()["critical"] == 1
