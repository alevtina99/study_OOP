import pytest
from decimal import Decimal
from bank.accounts import BankAccount, InvestmentAccount, PremiumAccount, SavingsAccount
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


def test_savings_interest_and_minimum_balance():
    account = SavingsAccount("10000001", "Anna", interest_rate="0.01", min_balance="40")
    account.deposit(100)
    assert account.apply_monthly_interest() == Decimal("1.00")
    assert account.balance == Decimal("101.00")
    account.withdraw(61)
    assert account.balance == Decimal("40.00")
    with pytest.raises(InsufficientFundsError):
        account.withdraw(1)
def test_frozen_savings_rejects_interest():
    account = SavingsAccount("10000002", "Anna", account_status="frozen")
    with pytest.raises(AccountFrozenError):
        account.apply_monthly_interest()
def test_premium_overdraft_and_commission():
    account = PremiumAccount("20000001", "Boris", overdraft_limit="50", commission_fixed="10")
    account.deposit(100)
    account.withdraw(100)
    assert account.balance == Decimal("-10.00")
    with pytest.raises(InsufficientFundsError):
        account.withdraw(50)
def test_investment_moves_cash_and_portfolio():
    account = InvestmentAccount("30000001", "Clara")
    account.deposit(1000)
    with pytest.raises(InsufficientFundsError):
        account.buy_funds("stocks", 1001)
    account.buy_funds("stocks", 500)
    account.buy_funds("bonds", 200)
    account.buy_funds("etf", 100)
    assert account.balance == Decimal("200")
    assert account.get_account_info()["portfolio"] == {
        "STOCK": Decimal("500"),
        "BOND": Decimal("200"),
        "ETF": Decimal("100"),
    }
    with pytest.raises(InvalidOperationError):
        account.buy_funds("crypto", 10)
    with pytest.raises(InsufficientFundsError):
        account.sell_funds("stocks", 501)
    account.sell_funds("etf", 40)
    assert account.balance == Decimal("240")
    account.withdraw(40)
    assert account.balance == Decimal("200")
    assert account.get_account_info()["portfolio"]["ETF"] == Decimal("60")
def test_investment_yearly_growth():
    account = InvestmentAccount("30000002", "Clara")
    account.deposit(800)
    account.buy_funds("stocks", 500)
    account.buy_funds("bonds", 200)
    account.buy_funds("etf", 100)
    assert account.project_yearly_growth({
        "stocks": "0.10",
        "bonds": "0.04",
        "etf": "0.07",
    }) == {
        "STOCK": Decimal("50.00"),
        "BOND": Decimal("8.00"),
        "ETF": Decimal("7.00"),
        "total": Decimal("65.00"),
    }
def test_polymorphic_withdraw_and_info():
    savings = SavingsAccount("10000003", "Anna", min_balance="0")
    premium = PremiumAccount("20000002", "Boris", commission_fixed="0", overdraft_limit="0")
    investment = InvestmentAccount("30000003", "Clara")
    for account in (savings, premium, investment):
        account.deposit(100)
        account.withdraw(30)
        info = account.get_account_info()
        assert info["balance"] == Decimal("70")
        assert info["account_holder"] == account._holder
        assert type(account).__name__ in str(account)