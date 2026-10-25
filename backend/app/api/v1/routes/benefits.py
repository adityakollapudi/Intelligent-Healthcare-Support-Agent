from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.db.session import get_db
from app.schemas.benefit import BenefitsResponse
from app.schemas.common import BENEFIT_CATEGORY_PATTERN, PLAN_CODE_PATTERN, ErrorResponse
from app.services import benefit_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/benefits", tags=["benefits"])


@router.get(
    "/{plan_code}",
    response_model=BenefitsResponse,
    summary="Get plan-level benefits (members: own plan only)",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse},
               404: {"model": ErrorResponse, "description": "Not found or not permitted"},
               422: {"model": ErrorResponse}},
)
def get_benefits(
    db: Annotated[Session, Depends(get_db)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    principal: Annotated[Principal, Depends(require_any_permission(
        Permission.BENEFITS_READ_OWN, Permission.BENEFITS_READ_ANY))],
    plan_code: Annotated[str, Path(pattern=PLAN_CODE_PATTERN, examples=["SYN-PLAN-GOLD-01"])],
    benefit_category: Annotated[str | None, Query(pattern=BENEFIT_CATEGORY_PATTERN)] = None,
) -> BenefitsResponse:
    return benefit_service.get_benefits(db, audit, principal, plan_code, benefit_category)
