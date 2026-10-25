"""Authoritative enumeration values (doc 02 §3), shared by models, schemas and CHECK constraints."""

from enum import StrEnum


class Role(StrEnum):
    MEMBER = "MEMBER"
    PROVIDER = "PROVIDER"
    SUPPORT_AGENT = "SUPPORT_AGENT"
    ADMIN = "ADMIN"


class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class OrgType(StrEnum):
    PROVIDER_PRACTICE = "PROVIDER_PRACTICE"
    SUPPORT_CENTER = "SUPPORT_CENTER"


class ClaimStatus(StrEnum):
    RECEIVED = "RECEIVED"
    UNDER_PROCESSING = "UNDER_PROCESSING"
    PENDING_INFORMATION = "PENDING_INFORMATION"
    PROCESSED_PAID = "PROCESSED_PAID"
    PROCESSED_DENIED = "PROCESSED_DENIED"


class AuditOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILURE = "FAILURE"


def sql_in(enum: type[StrEnum]) -> str:
    """Renders the value list for a CHECK (col IN (...)) constraint."""
    return ", ".join(f"'{member.value}'" for member in enum)
