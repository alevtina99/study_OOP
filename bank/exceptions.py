class BankingError(Exception):
    def __init__(self, message, *, balance=None, amount=None, **kwargs):
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
    """Exception raised when a transaction/client action is invalid."""
    def __init__(self, message="Invalid operation.", **kwargs):
        super().__init__(message, **kwargs)

class InsufficientFundsError(BankingError):
    """Exception raised when an account has insufficient funds for a transaction."""
    def __init__(self, message="Insufficient funds for the transaction.", **kwargs):
        super().__init__(message, **kwargs)


class AuthenticationError(BankingError):
    """Exception raised when a client fails authentication."""
    def __init__(self, message="Authentication failed.", **kwargs):
        super().__init__(message, **kwargs)

class ClientLockedError(BankingError):
    """Exception raised when a client is locked after failed login attempts."""
    def __init__(self, message="Client is locked after failed login attempts.", **kwargs):
        super().__init__(message, **kwargs)

class NightOperationError(InvalidOperationError):
    """Exception raised when an operation is attempted during the night ban."""
    def __init__(self, message="Operations are not allowed from 00:00 to 05:00.", **kwargs):
        super().__init__(message, **kwargs)

class RiskBlockedError(BankingError):
    """Exception raised when a high-risk operation is blocked."""
    def __init__(self, message="Operation blocked because the risk level is high.", **kwargs):
        super().__init__(message, **kwargs)