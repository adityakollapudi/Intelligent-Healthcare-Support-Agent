from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.authz.dependencies import CurrentPrincipal
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.schemas.common import ErrorResponse
from app.services import auth_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/auth", tags=["auth"])

Db = Annotated[Session, Depends(get_db)]
Audit = Annotated[AuditService, Depends(get_audit_service)]


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Exchange email and password for an access token (public)",
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
def login(body: LoginRequest, db: Db, audit: Audit,
          settings: Annotated[Settings, Depends(get_settings)]) -> LoginResponse:
    return auth_service.login(db, settings, audit, body.email, body.password)


@router.post("/logout", status_code=204, summary="Revoke the current access token",
             responses={401: {"model": ErrorResponse}})
def logout(principal: CurrentPrincipal, db: Db, audit: Audit) -> Response:
    auth_service.logout(db, audit, principal)
    return Response(status_code=204)


@router.get("/me", response_model=MeResponse, summary="Current user profile",
            responses={401: {"model": ErrorResponse}})
def me(principal: CurrentPrincipal) -> MeResponse:
    return auth_service.me(principal)
