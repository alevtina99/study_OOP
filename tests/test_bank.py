from datetime import datetime
from decimal import Decimal

import pytest

from bank.bank import Bank
from bank.exceptions import (
    AccountFrozenError,
    AuthenticationError,
    ClientLockedError,
    InvalidOperationError,
    NightOperationError,
)

DAY = datetime(2026, 11, 26, 15, 0)
NIGHT = datetime(2026, 11, 26, 3, 0)


def test_underage_client_is_rejected():
    bank = Bank(clock=lambda: DAY)
    with pytest.raises(InvalidOperationError):
        bank.add_client("Kid Ivanov", "2015-01-01", {"phone": "1"}, "secret")


def test_open_accounts_and_total_balance():
    bank = Bank(clock=lambda: DAY)
    anna = bank.add_client("Anna Ivanova", "2000-01-01", {"phone": "+7999"}, "secret")
    savings = bank.open_account(anna.client_id, "savings", min_balance="10")
    investment = bank.open_account(anna.client_id, "investment")
    bank.deposit(savings.account_id, 100)
    bank.deposit(investment.account_id, 500)
    investment.buy_funds("stock", 200)
    assert bank.get_total_balance(anna.client_id)["RUB"] == Decimal("600")
    assert set(anna.account_ids) == {savings.account_id, investment.account_id}


def test_freeze_and_close():
    bank = Bank(clock=lambda: DAY)
    anna = bank.add_client("Anna Ivanova", "2000-01-01", {"phone": "+7999"}, "secret")
    account = bank.open_account(anna.client_id)
    bank.deposit(account.account_id, 50)
    bank.freeze_account(account.account_id)
    with pytest.raises(AccountFrozenError):
        bank.deposit(account.account_id, 10)
    bank.unfreeze_account(account.account_id)
    bank.withdraw(account.account_id, 50)
    closed = bank.close_account(account.account_id)
    assert closed.status.value == "closed"


def test_three_failed_logins_lock_client():
    bank = Bank(clock=lambda: DAY)
    anna = bank.add_client("Anna Ivanova", "2000-01-01", {"phone": "+7999"}, "secret")
    for _ in range(2):
        with pytest.raises(AuthenticationError):
            bank.authenticate_client(anna.client_id, "wrong")
    with pytest.raises(ClientLockedError):
        bank.authenticate_client(anna.client_id, "wrong")
    with pytest.raises(ClientLockedError):
        bank.open_account(anna.client_id)
    bank.unlock_client(anna.client_id)
    assert bank.authenticate_client(anna.client_id, "secret") is anna


def test_night_operation_is_marked_suspicious():
    bank = Bank(clock=lambda: NIGHT)
    boris = bank.add_client("Boris Petrov", "1990-05-05", {"email": "b@x.ru"}, "pass")
    account = bank.open_account(boris.client_id)
    with pytest.raises(NightOperationError):
        bank.deposit(account.account_id, 10)
    assert any("night" in action["reason"] for action in boris.suspicious_actions)


def test_search_and_ranking():
    bank = Bank(clock=lambda: DAY)
    anna = bank.add_client("Anna Ivanova", "2000-01-01", {"phone": "+7999"}, "secret")
    boris = bank.add_client("Boris Petrov", "1990-05-05", {"email": "b@x.ru"}, "pass")
    anna_account = bank.open_account(anna.client_id, "savings", min_balance="0")
    boris_account = bank.open_account(boris.client_id, "premium", commission_fixed="0")
    bank.deposit(anna_account.account_id, 300)
    bank.deposit(boris_account.account_id, 100)
    found = bank.search_accounts(client_id=anna.client_id, account_type="savings", status="active")
    assert found == [anna_account]
    ranking = bank.get_clients_ranking()
    assert [item["client_id"] for item in ranking] == [anna.client_id, boris.client_id]
    assert ranking[0]["total"] == Decimal("300")
