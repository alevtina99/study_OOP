from datetime import date, datetime
import uuid

from .enums import ClientStatus, parse_client_status
from .exceptions import AuthenticationError, ClientLockedError, InvalidOperationError


class Client:
    def __init__(self, fio, birth_date, contacts, password, client_id=None, status=ClientStatus.ACTIVE):
        if not isinstance(fio, str) or not fio.strip():
            raise InvalidOperationError("Client name must be a non-empty string.")
        if not isinstance(password, str) or not password:
            raise InvalidOperationError("Password must be a non-empty string.")
        self._fio = fio.strip()

        self._id = client_id or f"{uuid.uuid4().int % 10**8:08d}"

        self._birth_date = self._parse_birth_date(birth_date)
        if self.age < 18:
            raise InvalidOperationError("Client must be at least 18 years old.")
        
        self._contacts = self._parse_contacts(contacts)
        self._status = parse_client_status(status)
        self._password = password
        self._account_ids = []
        self._failed_attempts = 0
        self._is_locked = False
        self._suspicious_actions = []

    def _parse_birth_date(self, value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                raise InvalidOperationError("Birth date must use the YYYY-MM-DD format.") from None
        raise InvalidOperationError("Birth date must be a date or a YYYY-MM-DD string.")

    def _parse_contacts(self, contacts):
        if not isinstance(contacts, dict):
            raise InvalidOperationError("Contacts must be a dictionary.")
        cleaned = {str(key): str(value).strip() for key, value in contacts.items()}
        if not any(cleaned.values()):
            raise InvalidOperationError("Client must have at least one contact.")
        return cleaned

    @property
    def age(self):
        today = date.today()
        years = today.year - self._birth_date.year
        if (today.month, today.day) < (self._birth_date.month, self._birth_date.day):
            years -= 1
        return years

    @property
    def client_id(self):
        return self._id

    @property
    def fio(self):
        return self._fio

    @property
    def status(self):
        return self._status

    @property
    def contacts(self):
        return dict(self._contacts)

    @property
    def account_ids(self):
        return list(self._account_ids)

    @property
    def is_locked(self):
        return self._is_locked

    @property
    def failed_attempts(self):
        return self._failed_attempts

    @property
    def suspicious_actions(self):
        return [dict(action) for action in self._suspicious_actions]

    def add_account_id(self, account_id):
        if account_id not in self._account_ids:
            self._account_ids.append(account_id)

    def mark_suspicious(self, reason):
        self._suspicious_actions.append({
            "time": datetime.now(),
            "reason": reason,
        })

    def verify_password(self, password):
        if self._status is ClientStatus.GONE:
            raise AuthenticationError("Client is gone.")
        if self._is_locked:
            raise ClientLockedError()
        if password != self._password:
            self._failed_attempts += 1
            self.mark_suspicious("failed login")
            if self._failed_attempts >= 3:
                self._is_locked = True
                self.mark_suspicious("client locked after 3 failed login attempts")
                raise ClientLockedError()
            raise AuthenticationError("Wrong password.")
        self._failed_attempts = 0
        return True

    def unlock(self):
        self._is_locked = False
        self._failed_attempts = 0

    def set_status(self, status):
        self._status = parse_client_status(status)

    def get_client_info(self):
        return {
            "client_id": self._id,
            "fio": self._fio,
            "age": self.age,
            "status": self._status,
            "contacts": self.contacts,
            "account_ids": self.account_ids,
            "is_locked": self._is_locked,
            "suspicious_actions": self.suspicious_actions,
        }

    def __str__(self):
        return (
            f"Client: {self._fio}, "
            f"ID: {self._id}, "
            f"Status: {self._status.value}, "
            f"Age: {self.age}, "
            f"Accounts: {len(self._account_ids)}"
        )
