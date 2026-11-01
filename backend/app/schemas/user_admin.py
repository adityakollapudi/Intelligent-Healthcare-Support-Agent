"""Administrator-managed user accounts. Password hashes are never part of any response."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import PLAN_CODE_PATTERN, ApiModel, RequestModel, UtcDatetime

ManagedRole = Literal["MEMBER", "PROVIDER", "SUPPORT_AGENT"]
SYNTHETIC_EMAIL_DOMAIN = "example.test"


class CreateUserRequest(RequestModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    role: ManagedRole
    password: str = Field(min_length=12, max_length=128)
    plan_code: str | None = Field(default=None, pattern=PLAN_CODE_PATTERN)
    organization_id: UUID | None = None

    @field_validator("email")
    @classmethod
    def _synthetic_email(cls, value: str) -> str:
        local, _, domain = value.lower().partition("@")
        if not local or " " in value or domain != SYNTHETIC_EMAIL_DOMAIN:
            raise ValueError(f"must be an @{SYNTHETIC_EMAIL_DOMAIN} address")
        return value.lower()

    @model_validator(mode="after")
    def _role_link(self) -> Self:
        if self.role == "MEMBER" and not self.plan_code:
            raise ValueError("a member needs a plan")
        if self.role != "MEMBER" and not self.organization_id:
            raise ValueError("providers and support agents need an organization")
        return self


class ManagedUser(ApiModel):
    id: UUID
    email: str
    display_name: str
    role: str
    account_status: str
    organization_name: str | None
    member_number: str | None
    plan_name: str | None
    created_at: UtcDatetime
    last_login_at: UtcDatetime | None


class PlanOption(ApiModel):
    plan_code: str
    plan_name: str


class OrganizationOption(ApiModel):
    id: UUID
    name: str
    role: ManagedRole


class UserFormOptions(ApiModel):
    plans: list[PlanOption]
    organizations: list[OrganizationOption]
