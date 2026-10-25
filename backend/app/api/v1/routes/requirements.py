from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.readiness import ChecklistDetail, ChecklistPage, ReadinessRequest, RequirementSetSummary
from app.schemas.requirements import RequirementSetResponse
from app.services import readiness_service, requirements_service
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


_ERRORS = {s: {"model": ErrorResponse} for s in (401, 403, 404, 409, 422)}
Db = Annotated[Session, Depends(get_db)]
Audit = Annotated[AuditService, Depends(get_audit_service)]


@router.get(
    "/requirement-sets",
    response_model=list[RequirementSetSummary],
    responses=_ERRORS,
    summary="Active fictional requirement sets (for choosing a procedure; added in Phase 6, D6-07)",
)
def list_requirement_sets(
    db: Db, principal: Annotated[Principal, Depends(require_any_permission(Permission.REQUIREMENTS_READ))]
) -> list[RequirementSetSummary]:
    return readiness_service.list_requirement_sets(db)


@router.post(
    "/readiness",
    response_model=ChecklistDetail,
    status_code=201,
    responses=_ERRORS,
    summary="Create a documentation-readiness checklist (NOT an approval or denial)",
)
def create_readiness_checklist(
    body: ReadinessRequest,
    db: Db,
    audit: Audit,
    principal: Annotated[Principal, Depends(require_any_permission(Permission.READINESS_CREATE))],
) -> ChecklistDetail:
    return readiness_service.create_checklist(db, audit, principal, body)


Reader = Annotated[Principal, Depends(require_any_permission(Permission.READINESS_READ_OWN))]


@router.get("/checklists", response_model=ChecklistPage, responses=_ERRORS, summary="My readiness checklists")
def list_checklists(db: Db, principal: Reader) -> ChecklistPage:
    return readiness_service.list_checklists(db, principal)


@router.get("/checklists/{checklist_id}", response_model=ChecklistDetail, responses=_ERRORS,
            summary="One of my readiness checklists")
def get_checklist(checklist_id: UUID, db: Db, audit: Audit, principal: Reader) -> ChecklistDetail:
    return readiness_service.get_checklist(db, audit, principal, checklist_id)