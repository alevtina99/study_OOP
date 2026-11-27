from datetime import datetime, timedelta
import json
from decimal import Decimal

from .enums import AuditLevel, RiskLevel, parse_audit_level

LEVEL_RANK = {
    AuditLevel.INFO: 0,
    AuditLevel.WARNING: 1,
    AuditLevel.ERROR: 2,
    AuditLevel.CRITICAL: 3,
}
RISK_RANK = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}
RISK_TO_AUDIT = {
    RiskLevel.LOW: AuditLevel.INFO,
    RiskLevel.MEDIUM: AuditLevel.WARNING,
    RiskLevel.HIGH: AuditLevel.CRITICAL,
}


class AuditEntry:
    def __init__(self, level, message, time=None, client_id=None, transaction_id=None, risk=None, signals=None):
        self.level = parse_audit_level(level)
        self.message = message
        self.time = time or datetime.now()
        self.client_id = client_id
        self.transaction_id = transaction_id
        self.risk = risk
        self.signals = list(signals or [])

    def as_dict(self):
        return {
            "time": self.time.isoformat(sep=" ", timespec="seconds"),
            "level": self.level.value,
            "message": self.message,
            "client_id": self.client_id,
            "transaction_id": self.transaction_id,
            "risk": self.risk.value if self.risk is not None else None,
            "signals": list(self.signals),
        }

    def __str__(self):
        return f"[{self.level.value}] {self.time:%Y-%m-%d %H:%M:%S} {self.message}"


class AuditLog:
    def __init__(self, path=None):
        self._entries = []
        self._path = path

    def log(self, level, message, client_id=None, transaction_id=None, risk=None, signals=None, time=None):
        entry = AuditEntry(level, message, time, client_id, transaction_id, risk, signals)
        self._entries.append(entry)
        if self._path is not None:
            with open(self._path, "a", encoding="utf-8") as storage:
                storage.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")
        return entry

    def filter(self, level=None, client_id=None, min_level=None):
        min_rank = LEVEL_RANK[parse_audit_level(min_level)] if min_level is not None else None
        exact = parse_audit_level(level) if level is not None else None
        found = []
        for entry in self._entries:
            if exact is not None and entry.level is not exact:
                continue
            if min_rank is not None and LEVEL_RANK[entry.level] < min_rank:
                continue
            if client_id is not None and entry.client_id != client_id:
                continue
            found.append(entry)
        return found

    def load(self, path=None):
        path = path or self._path
        self._entries = []
        if path is None:
            return self._entries
        with open(path, encoding="utf-8") as storage:
            for line in storage:
                if not line.strip():
                    continue
                raw = json.loads(line)
                risk = RiskLevel(raw["risk"]) if raw.get("risk") else None
                self._entries.append(AuditEntry(
                    raw["level"],
                    raw["message"],
                    datetime.fromisoformat(raw["time"]),
                    raw.get("client_id"),
                    raw.get("transaction_id"),
                    risk,
                    raw.get("signals") or [],
                ))
        return self._entries

    def error_statistics(self):
        by_message = {}
        errors = 0
        critical = 0
        for entry in self._entries:
            if entry.level is AuditLevel.ERROR:
                errors += 1
                by_message[entry.message] = by_message.get(entry.message, 0) + 1
            elif entry.level is AuditLevel.CRITICAL:
                critical += 1
                by_message[entry.message] = by_message.get(entry.message, 0) + 1
        return {"errors": errors, "critical": critical, "by_message": by_message}

    def __len__(self):
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)


class RiskAssessment:
    def __init__(self, client_id, level, signals, transaction_id=None, amount=None):
        self.client_id = client_id
        self.level = level
        self.signals = list(signals)
        self.transaction_id = transaction_id
        self.amount = amount

    @property
    def summary(self):
        if not self.signals:
            return "No risk signals."
        return "Risk signals: " + ", ".join(self.signals) + "."


class RiskAnalyzer:
    def __init__(self, large_amount="100000", frequent_limit=3, frequent_window=timedelta(minutes=10)):
        self._large_amount = Decimal(str(large_amount))
        self._frequent_limit = int(frequent_limit)
        self._frequent_window = frequent_window
        self._times = {}
        self._recipients = {}
        self._assessments = []

    def assess(self, client_id, amount, moment, receiver_id=None, transaction_id=None):
        if isinstance(amount, bool) or not isinstance(amount, (int, float, Decimal)):
            amount = Decimal("0")
        else:
            amount = Decimal(str(amount))
        signals = []
        if amount >= self._large_amount:
            signals.append("large amount")
        recent = [
            stamp for stamp in self._times.get(client_id, [])
            if moment - self._frequent_window <= stamp <= moment
        ]
        if len(recent) + 1 >= self._frequent_limit:
            signals.append("frequent operations")
        known = self._recipients.get(client_id, set())
        if receiver_id is not None and known and receiver_id not in known:
            signals.append("new account")
        if 0 <= moment.hour < 5:
            signals.append("night operation")
        if len(signals) >= 2:
            level = RiskLevel.HIGH
        elif signals:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW
        self._times.setdefault(client_id, []).append(moment)
        assessment = RiskAssessment(client_id, level, signals, transaction_id, amount)
        self._assessments.append(assessment)
        return assessment

    def remember(self, client_id, receiver_id):
        if receiver_id is not None:
            self._recipients.setdefault(client_id, set()).add(receiver_id)

    def suspicious_operations(self):
        return [item for item in self._assessments if item.level is not RiskLevel.LOW]

    def client_risk_profile(self, client_id):
        items = [item for item in self._assessments if item.client_id == client_id]
        signals = {}
        highest = RiskLevel.LOW
        for item in items:
            if RISK_RANK[item.level] > RISK_RANK[highest]:
                highest = item.level
            for signal in item.signals:
                signals[signal] = signals.get(signal, 0) + 1
        return {
            "client_id": client_id,
            "operations": len(items),
            "highest_risk": highest.value,
            "signals": signals,
            "known_recipients": sorted(self._recipients.get(client_id, set())),
        }


def audit_risk(log, assessment, message, time=None):
    if log is None:
        return None
    return log.log(
        RISK_TO_AUDIT[assessment.level],
        message,
        client_id=assessment.client_id,
        transaction_id=assessment.transaction_id,
        risk=assessment.level,
        signals=assessment.signals,
        time=time,
    )
