import pytest
from bank.accounts import BankAccount
from bank.exceptions import AccountFrozenError, InsufficientFundsError, InvalidOperationError

def test_deposit_and_withdraw():
    account = BankAccount("12345678", "John Doe")
    assert account.deposit(200) == 200
    assert account.withdraw(100) == 100

def test_frozen_account_rejects_deposit():
    account = BankAccount("12345678", "Jane Smith", account_status="frozen")
    with pytest.raises(AccountFrozenError):
        account.deposit(100)

def test_invalid_amount():
    account = BankAccount("12345678", "John Doe")
    with pytest.raises(InvalidOperationError):
        account.deposit(0)
    with pytest.raises(InvalidOperationError):
        account.deposit(True)

def test_insufficient_funds():
    account = BankAccount("12345678", "John Doe")
    account.deposit(50)
    with pytest.raises(InsufficientFundsError):
        account.withdraw(100)

def test_unknown_currency():
    with pytest.raises(InvalidOperationError):
        BankAccount("12345678", "John Doe", currency="BTC")