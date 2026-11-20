class AccountFrozenError(Exception):
    """Exception raised when an operation is attempted on a frozen account."""
    def __init__(self, message="Account is frozen. Operation cannot be performed.", balance=None, amount=None):
        self.balance = balance
        self.amount = amount
        super().__init__(message)
    def __str__(self):
        return f"{self.__class__.__name__}: {self.args[0]} (Balance: {self.balance}, Amount: {self.amount})"

class AccountClosedError(Exception):
    """Exception raised when an operation is attempted on a closed account."""
    def __init__(self, message="Account is closed. Operation cannot be performed.", balance=None, amount=None):
        self.balance = balance
        self.amount = amount
        super().__init__(message)
    def __str__(self):
        return f"{self.__class__.__name__}: {self.args[0]} (Balance: {self.balance}, Amount: {self.amount})"

class InvalidOperationError(Exception):
    """Exception raised when a transaction is invalid."""
    def __init__(self, message="Invalid operation.", balance=None, amount=None):
        self.balance = balance
        self.amount = amount
        super().__init__(message)
    def __str__(self):
        return f"{self.__class__.__name__}: {self.args[0]} (Balance: {self.balance}, Amount: {self.amount})"

class InsufficientFundsError(Exception):
    """Exception raised when an account has insufficient funds for a transaction."""
    def __init__(self, message="Insufficient funds for the transaction.", balance=None, amount=None):
        self.balance = balance
        self.amount = amount
        super().__init__(message)
    def __str__(self):
        return f"{self.__class__.__name__}: {self.args[0]} (Balance: {self.balance}, Amount: {self.amount})"