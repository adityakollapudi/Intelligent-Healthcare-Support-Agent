"""Plan benefit lookups (FR-015). Members may read only their own plan; others any active plan."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.authz.dependencies import Principal
from app.authz.permissions import Permission
from app.core.exceptions import NotFoundError
from app.models.enums import AuditOutcome
from app.repositories import plan_repository
from app.schemas.benefit import BenefitItem, BenefitsResponse
from app.services.audit_service import AuditService


def get_benefits(
    db: Session, audit: AuditService, principal: Principal, plan_code: str, benefit_category: str | None
) -> BenefitsResponse:
    plan = None
    reason = "NOT_EXISTS"
    if principal.has(Permission.BENEFITS_READ_ANY):
        candidate = plan_repository.get_by_code(db, plan_code)
        if candidate is not None and candidate.is_active:
            plan = candidate
    elif principal.has(Permission.BENEFITS_READ_OWN):
        if plan_code == principal.plan_code:
            plan = plan_repository.get_by_code(db, plan_code)
        else:
            reason = "NOT_OWNER"

    if plan is None:
        audit.record("ACCESS_DENIED", AuditOutcome.DENIED, actor=principal, resource_type="plan",
                     resource_ref=plan_code, reason_code=reason)
        raise NotFoundError()

    benefits = [b for b in plan.benefits if benefit_category is None or b.benefit_category == benefit_category]
    metadata = {"benefit_category": benefit_category} if benefit_category else {}
    audit.record("BENEFITS_LOOKUP", AuditOutcome.SUCCESS, actor=principal, resource_type="plan",
                 resource_ref=plan_code, metadata=metadata)
    return BenefitsResponse(
        plan_code=plan.plan_code,
        plan_name=plan.plan_name,
        plan_year=plan.plan_year,
        effective_start=plan.effective_start,
        effective_end=plan.effective_end,
        benefits=[
            BenefitItem(
                benefit_category=b.benefit_category,
                service_name=b.service_name,
                in_network_cost_share=b.in_network_cost_share,
                out_of_network_cost_share=b.out_of_network_cost_share,
                prior_auth_required=b.prior_auth_required,
                visit_limit=b.visit_limit,
                limitations=b.limitations,
            )
            for b in benefits
        ],
    )
