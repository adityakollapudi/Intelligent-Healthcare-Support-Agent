from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.requirements import RequirementSetResponse
from app.services import requirements_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/authorization", tags=["requirements"])


@router.get(
    "/requirements/{procedure_code}",
    response_model=RequirementSetResponse,
    summary="Configured documentation requirements for a fictional procedure, with verified sources",
    responses={s: {"model": ErrorResponse} for s in (401, 403, 404, 422)},
)
def get_requirements(
    db: Annotated[Session, Depends(get_db)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    principal: Annotated[Principal, Depends(require_any_permission(Permission.REQUIREMENTS_READ))],
    procedure_code: Annotated[str, Path(pattern=r"^SYN-PROC-[A-Z0-9-]{2,30}$")],
) -> RequirementSetResponse:
    return requirements_service.get_requirements(
        db, audit, principal, procedure_code=procedure_code, procedure_text=None
    )
