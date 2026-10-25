"""Role → permission map (doc 03 §2.1). The only place where role capabilities are defined."""

from enum import StrEnum

from app.models.enums import Role


class Permission(StrEnum):
    CHAT_USE = "chat:use"
    KNOWLEDGE_READ = "knowledge:read"
    CLAIMS_READ_OWN = "claims:read:own"
    CLAIMS_READ_CASE_LINKED = "claims:read:case_linked"
    BENEFITS_READ_OWN = "benefits:read:own"
    BENEFITS_READ_ANY = "benefits:read:any"
    REQUIREMENTS_READ = "requirements:read"
    DOCUMENTS_UPLOAD = "documents:upload"
    DOCUMENTS_READ_OWN = "documents:read:own"
    DOCUMENTS_READ_CASE_LINKED = "documents:read:case_linked"
    READINESS_CREATE = "readiness:create"
    READINESS_READ_OWN = "readiness:read:own"
    READINESS_READ_CASE_LINKED = "readiness:read:case_linked"
    CASES_CREATE = "cases:create"
    CASES_READ_OWN = "cases:read:own"
    CASES_UPDATE_OWN = "cases:update:own"
    CASES_READ_QUEUE = "cases:read:queue"
    CASES_READ_ASSIGNED = "cases:read:assigned"
    CASES_UPDATE_ASSIGNED = "cases:update:assigned"
    CASES_ASSIGN_SELF = "cases:assign:self"
    CASES_READ_METADATA_ALL = "cases:read:metadata_all"
    CASES_ASSIGN_ANY = "cases:assign:any"
    METRICS_READ = "metrics:read"
    KNOWLEDGE_GAPS_READ = "knowledge_gaps:read"
    AUDIT_READ = "audit:read"
    FEEDBACK_CREATE = "feedback:create"
    CONFIG_MANAGE = "config:manage"


P = Permission

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.MEMBER: frozenset({
        P.CHAT_USE, P.KNOWLEDGE_READ, P.CLAIMS_READ_OWN, P.BENEFITS_READ_OWN, P.REQUIREMENTS_READ,
        P.DOCUMENTS_UPLOAD, P.DOCUMENTS_READ_OWN, P.CASES_CREATE, P.CASES_READ_OWN, P.CASES_UPDATE_OWN,
        P.FEEDBACK_CREATE,
    }),
    Role.PROVIDER: frozenset({
        P.CHAT_USE, P.KNOWLEDGE_READ, P.BENEFITS_READ_ANY, P.REQUIREMENTS_READ, P.DOCUMENTS_UPLOAD,
        P.DOCUMENTS_READ_OWN, P.READINESS_CREATE, P.READINESS_READ_OWN, P.CASES_CREATE, P.CASES_READ_OWN,
        P.CASES_UPDATE_OWN, P.FEEDBACK_CREATE,
    }),
    Role.SUPPORT_AGENT: frozenset({
        P.CHAT_USE, P.KNOWLEDGE_READ, P.CLAIMS_READ_CASE_LINKED, P.BENEFITS_READ_ANY, P.REQUIREMENTS_READ,
        P.DOCUMENTS_READ_CASE_LINKED, P.READINESS_READ_CASE_LINKED, P.CASES_READ_QUEUE,
        P.CASES_READ_ASSIGNED, P.CASES_UPDATE_ASSIGNED, P.CASES_ASSIGN_SELF, P.FEEDBACK_CREATE,
    }),
    Role.ADMIN: frozenset({
        P.CHAT_USE, P.KNOWLEDGE_READ, P.BENEFITS_READ_ANY, P.REQUIREMENTS_READ, P.CASES_READ_METADATA_ALL,
        P.CASES_ASSIGN_ANY, P.METRICS_READ, P.KNOWLEDGE_GAPS_READ, P.AUDIT_READ, P.FEEDBACK_CREATE,
        P.CONFIG_MANAGE,
    }),
}


def permissions_for(role: str) -> frozenset[Permission]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()  # unknown role: deny everything
