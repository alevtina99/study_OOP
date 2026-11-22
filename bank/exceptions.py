class BankingError(Exception):
    def __init__(self, message, *, balance=None, amount=None):
        self.balance = balance
        self.amount = amount
        super().__init__(message)
    def __str__(self):
        details = []
        if self.balance is not None:
            details.append(f"Balance: {self.balance}")
        if self.amount is not None:
            details.append(f"Amount: {self.amount}")
        if not details:
            return self.args[0]
        return f"{self.args[0]} ({', '.join(details)})"

class AccountFrozenError(BankingError):
    """Exception raised when an operation is attempted on a frozen account."""
    def __init__(self, message="Account is frozen. Operation cannot be performed.", **kwargs):
        super().__init__(message, **kwargs)

class AccountClosedError(BankingError):
    """Exception raised when an operation is attempted on a closed account."""
    def __init__(self, message="Account is closed. Operation cannot be performed.", **kwargs):
        super().__init__(message, **kwargs)

class InvalidOperationError(BankingError):
    """Exception raised when a transaction is invalid."""
    def __init__(self, message="Invalid operation.", **kwargs):
        super().__init__(message, **kwargs)

class InsufficientFundsError(BankingError):
    """Exception raised when an account has insufficient funds for a transaction."""
    def __init__(self, message="Insufficient funds for the transaction.", **kwargs):
        super().__init__(message, **kwargs)