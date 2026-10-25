from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.core.exceptions import AppError
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.support_case import CaseDetail, CasePage, CaseStatus, CreateCaseRequest
from app.services import support_case_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/support-cases", tags=["support cases"])

Db = Annotated[Session, Depends(get_db)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Creator = Annotated[Principal, Depends(require_any_permission(Permission.CASES_CREATE))]
Reader = Annotated[Principal, Depends(require_any_permission(Permission.CASES_READ_OWN))]
_ERRORS = {s: {"model": ErrorResponse} for s in (400, 401, 403, 404, 409, 422, 500)}


class IdempotencyKeyRequiredError(AppError):
    status_code = 400
    code = "IDEMPOTENCY_KEY_REQUIRED"
    message = "An Idempotency-Key header (UUID) is required to create a support case."


@router.post(
    "",
    response_model=CaseDetail,
    status_code=201,
    responses={**_ERRORS, 200: {"model": CaseDetail}},
    summary="Create a support case (user-confirmed; idempotent per Idempotency-Key)",
)
def create_case(
    body: CreateCaseRequest,
    response: Response,
    db: Db,
    audit: Audit,
    principal: Creator,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CaseDetail:
    try:
        key = UUID(idempotency_key or "")
    except ValueError:
        raise IdempotencyKeyRequiredError() from None
    case, created = support_case_service.create_case(db, audit, principal, body, key)
    if not created:
        response.status_code = 200  # replay of an earlier, identical request: same case, nothing new created
    return case


@router.get("", response_model=CasePage, responses=_ERRORS, summary="List my support cases")
def list_cases(
    db: Db,
    principal: Reader,
    status: Annotated[list[CaseStatus] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CasePage:
    return support_case_service.list_cases(db, principal, statuses=status, limit=limit)


@router.get("/{case_id}", response_model=CaseDetail, responses=_ERRORS, summary="One of my support cases")
def get_case(case_id: UUID, db: Db, audit: Audit, principal: Reader) -> CaseDetail:
    return support_case_service.get_case(db, audit, principal, case_id)
