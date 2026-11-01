"""Accounts an administrator can create: members, providers and support agents.

Administrator accounts stay with the seed script, so a stolen admin session can't mint more of them."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal
from app.core.exceptions import AppError
from app.core.security import hash_password
from app.models import Member, Organization, Plan, User
from app.models.enums import AuditOutcome, OrgType, Role
from app.schemas.user_admin import (
    CreateUserRequest,
    ManagedUser,
    OrganizationOption,
    PlanOption,
    UserFormOptions,
)
from app.services.audit_service import AuditService

_ROLE_FOR_ORG = {OrgType.PROVIDER_PRACTICE: Role.PROVIDER, OrgType.SUPPORT_CENTER: Role.SUPPORT_AGENT}
_LIST_LIMIT = 500


class EmailInUseError(AppError):
    status_code = 409
    code = "EMAIL_IN_USE"
    message = "An account with this email already exists."


class InvalidLinkError(AppError):
    status_code = 422
    code = "INVALID_ACCOUNT_LINK"
    message = "The selected plan or organization can't be used for this role."


def _managed(user: User, member: Member | None) -> ManagedUser:
    return ManagedUser(
        id=user.id, email=user.email, display_name=user.display_name, role=user.role,
        account_status=user.account_status, organization_name=user.organization.name if user.organization else None,
        member_number=member.member_number if member else None, plan_name=member.plan.plan_name if member else None,
        created_at=user.created_at, last_login_at=user.last_login_at,
    )


def list_users(db: Session, role: str | None) -> list[ManagedUser]:
    query = select(User, Member).outerjoin(Member, Member.user_id == User.id).order_by(User.role, User.display_name)
    if role:
        query = query.where(User.role == role)
    return [_managed(user, member) for user, member in db.execute(query.limit(_LIST_LIMIT))]


def _open_plans():
    """Plans a new member can join: retired ones keep their history but take nobody new."""
    today = datetime.now(UTC).date()
    return select(Plan).where(or_(Plan.effective_end.is_(None), Plan.effective_end >= today))


def form_options(db: Session) -> UserFormOptions:
    return UserFormOptions(
        plans=[PlanOption(plan_code=p.plan_code, plan_name=p.plan_name)
               for p in db.scalars(_open_plans().order_by(Plan.plan_name))],
        organizations=[OrganizationOption(id=o.id, name=o.name, role=_ROLE_FOR_ORG[OrgType(o.org_type)].value)
                       for o in db.scalars(select(Organization).order_by(Organization.name))],
    )


def _next_member_number(db: Session) -> str:
    highest = db.scalar(select(func.max(Member.member_number)))
    return f"SYN-M-{int(highest.rsplit('-', 1)[1]) + 1 if highest else 1:06d}"


def create_user(db: Session, audit: AuditService, principal: Principal, request: CreateUserRequest) -> ManagedUser:
    if db.scalar(select(User.id).where(User.email == request.email)):
        raise EmailInUseError()
    plan = None
    if request.role == Role.MEMBER:
        plan = db.scalars(_open_plans().where(Plan.plan_code == request.plan_code)).first()
        if plan is None:
            raise InvalidLinkError()
    else:
        organization = db.get(Organization, request.organization_id)
        if organization is None or _ROLE_FOR_ORG[OrgType(organization.org_type)] != request.role:
            raise InvalidLinkError()

    user = User(email=request.email, display_name=request.display_name, role=request.role,
                password_hash=hash_password(request.password),
                organization_id=None if plan else request.organization_id)
    db.add(user)
    member = None
    try:
        db.flush()
        if plan:
            member = Member(member_number=_next_member_number(db), user_id=user.id, plan_id=plan.id,
                            coverage_start=datetime.now(UTC).date(), plan=plan)
            db.add(member)
            db.flush()
        audit.add_to_transaction(db, "USER_CREATED", AuditOutcome.SUCCESS, actor=principal, resource_type="user",
                                 resource_ref=str(user.id))
        db.commit()
    except IntegrityError:  # another request took this email or member number first
        db.rollback()
        raise EmailInUseError("That account couldn't be created. Please try again.") from None
    db.refresh(user)
    return _managed(user, member)
