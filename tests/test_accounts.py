from datetime import datetime
from decimal import Decimal

import pytest

from bank.accounts import BankAccount, InvestmentAccount, PremiumAccount, SavingsAccount
from bank.enums import InvestmentType
from bank.exceptions import AccountFrozenError, InsufficientFundsError, InvalidOperationError

DAY = datetime(2026, 11, 26, 15, 0)


def at_day(account):
    account._clock = lambda: DAY
    return account


def test_deposit_and_withdraw():
    account = at_day(BankAccount("12345678", "John Doe"))
    assert account.deposit(200) == Decimal("200.00")
    assert account.withdraw(100) == Decimal("100.00")


def test_frozen_account_rejects_deposit():
    account = at_day(BankAccount("12345678", "Jane Smith", account_status="frozen"))
    with pytest.raises(AccountFrozenError):
        account.deposit(100)


def test_invalid_amount():
    account = at_day(BankAccount("12345678", "John Doe"))
    with pytest.raises(InvalidOperationError):
        account.deposit(0)
    with pytest.raises(InvalidOperationError):
        account.deposit(True)


def test_insufficient_funds():
    account = at_day(BankAccount("12345678", "John Doe"))
    account.deposit(50)
    with pytest.raises(InsufficientFundsError):
        account.withdraw(100)


def test_default_currency_is_rub():
    account = BankAccount("12345678", "John Doe")
    assert account.currency.value == "RUB"


def test_savings_interest_and_minimum_balance():
    account = at_day(SavingsAccount("10000001", "Anna", interest_rate="0.01", min_balance="40"))
    account.deposit(100)
    assert account.apply_monthly_interest() == Decimal("1.00")
    assert account.balance == Decimal("101.00")
    account.withdraw(61)
    assert account.balance == Decimal("40.00")
    with pytest.raises(InsufficientFundsError):
        account.withdraw(1)


def test_frozen_savings_rejects_interest():
    account = at_day(SavingsAccount("10000002", "Anna", account_status="frozen"))
    with pytest.raises(AccountFrozenError):
        account.apply_monthly_interest()


def test_premium_overdraft_and_commission():
    account = at_day(PremiumAccount("20000001", "Boris", overdraft_limit="50", commission_fixed="10"))
    account.deposit(100)
    assert account.withdraw(100) == Decimal("-10.00")
    with pytest.raises(InsufficientFundsError):
        account.withdraw(50)


def test_investment_moves_cash_and_portfolio():
    account = at_day(InvestmentAccount("30000001", "Clara"))
    account.deposit(1000)
    with pytest.raises(InsufficientFundsError):
        account.buy_funds("stock", 1001)
    account.buy_funds("stock", 500)
    account.buy_funds("bond", 200)
    account.buy_funds("etf", 100)
    assert account.balance == Decimal("200")
    assert account.get_account_info()["portfolio"] == {
        InvestmentType.STOCK: Decimal("500"),
        InvestmentType.BOND: Decimal("200"),
        InvestmentType.ETF: Decimal("100"),
    }
    with pytest.raises(InvalidOperationError):
        account.buy_funds("crypto", 10)
    with pytest.raises(InsufficientFundsError):
        account.sell_funds("stock", 501)
    account.sell_funds("etf", 40)
    assert account.balance == Decimal("240")
    account.withdraw(40)
    assert account.balance == Decimal("200")
    assert account.get_account_info()["portfolio"][InvestmentType.ETF] == Decimal("60")


def test_investment_yearly_growth():
    account = at_day(InvestmentAccount("30000002", "Clara"))
    account.deposit(800)
    account.buy_funds("stock", 500)
    account.buy_funds("bond", 200)
    account.buy_funds("etf", 100)
    assert account.project_yearly_growth({
        "stock": "0.10",
        "bond": "0.04",
        "etf": "0.07",
    }) == {
        InvestmentType.STOCK: Decimal("50.00"),
        InvestmentType.BOND: Decimal("8.00"),
        InvestmentType.ETF: Decimal("7.00"),
    }


def test_polymorphic_withdraw_and_info():
    savings = at_day(SavingsAccount("10000003", "Anna", min_balance="0"))
    premium = at_day(PremiumAccount("20000002", "Boris", commission_fixed="0", overdraft_limit="0"))
    investment = at_day(InvestmentAccount("30000003", "Clara"))
    for account in (savings, premium, investment):
        account.deposit(100)
        account.withdraw(30)
        info = account.get_account_info()
        assert info["balance"] == Decimal("70")
        assert info["account_holder"] == account.holder
        assert type(account).__name__ in str(account)
