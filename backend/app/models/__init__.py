"""Importing this package registers every model on Base.metadata (used by Alembic)."""

from app.models.audit_log import AuditLog, RevokedToken
from app.models.claim import Claim
from app.models.conversation import ConversationMessage, ConversationSession, MessageCitation
from app.models.document import (
    AuthorizationChecklist,
    AuthorizationChecklistItem,
    ChecklistDocument,
    DocumentProcessingJob,
    ExtractedField,
    UploadedDocument,
)
from app.models.knowledge import DocumentChunk, KnowledgeDocument
from app.models.member import Member
from app.models.organization import Organization
from app.models.plan import Plan, PlanBenefit
from app.models.support import (
    PaRequirement,
    PaRequirementSet,
    SupportCase,
    SupportCaseDocument,
    SupportCaseEvent,
    ToolInvocation,
)
from app.models.user import User

__all__ = [
    "AuditLog", "AuthorizationChecklist", "AuthorizationChecklistItem", "ChecklistDocument", "Claim",
    "ConversationMessage", "ConversationSession", "DocumentChunk", "DocumentProcessingJob", "ExtractedField",
    "KnowledgeDocument", "Member", "MessageCitation", "Organization", "PaRequirement", "PaRequirementSet", "Plan",
    "PlanBenefit", "RevokedToken", "SupportCase", "SupportCaseDocument", "SupportCaseEvent", "ToolInvocation",
    "UploadedDocument", "User",
]