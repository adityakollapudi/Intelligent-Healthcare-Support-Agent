from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.core.exceptions import AppError
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.support_case import (
    CaseCategory,
    CaseDetail,
    CasePage,
    CaseStatus,
    CreateCaseRequest,
    UpdateCaseRequest,
)
from app.services import support_case_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/support-cases", tags=["support cases"])

Db = Annotated[Session, Depends(get_db)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Creator = Annotated[Principal, Depends(require_any_permission(Permission.CASES_CREATE))]
Reader = Annotated[Principal, Depends(require_any_permission(
    Permission.CASES_READ_OWN, Permission.CASES_READ_QUEUE, Permission.CASES_READ_ASSIGNED,
    Permission.CASES_READ_METADATA_ALL))]
Updater = Annotated[Principal, Depends(require_any_permission(
    Permission.CASES_UPDATE_OWN, Permission.CASES_UPDATE_ASSIGNED, Permission.CASES_ASSIGN_ANY))]
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


@router.get("", response_model=CasePage, responses=_ERRORS,
            summary="Cases in a permitted scope: mine | queue (unassigned OPEN) | assigned | all (admin)")
def list_cases(
    db: Db,
    principal: Reader,
    scope: Annotated[Literal["mine", "queue", "assigned", "all"] | None, Query()] = None,
    status: Annotated[list[CaseStatus] | None, Query()] = None,
    category: Annotated[CaseCategory | None, Query()] = None,
    case_number: Annotated[str | None, Query(pattern=r"^CASE-\d{4}-\d{6}$")] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> CasePage:
    return support_case_service.list_cases(
        db, principal, scope=scope, statuses=status, category=category, case_number=case_number,
        created_from=created_from, created_to=created_to, limit=limit, cursor=cursor,
    )


@router.get("/{case_id}", response_model=CaseDetail, responses=_ERRORS,
            summary="A case visible to me (creator, assigned agent, queue agent or admin)")
def get_case(case_id: UUID, db: Db, audit: Audit, principal: Reader) -> CaseDetail:
    return support_case_service.get_case(db, audit, principal, case_id)


@router.patch("/{case_id}", response_model=CaseDetail, responses=_ERRORS,
              summary="Validated status/assignment change or note (optimistic version check)")
def update_case(case_id: UUID, body: UpdateCaseRequest, db: Db, audit: Audit, principal: Updater) -> CaseDetail:
    return support_case_service.update_case(db, audit, principal, case_id, body)