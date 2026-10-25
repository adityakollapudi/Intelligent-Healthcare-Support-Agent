from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import ApiModel, RequestModel


class LoginRequest(RequestModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        local, sep, domain = value.partition("@")
        if not sep or not local or "." not in domain or " " in value:
            raise ValueError("must be an email address")
        return value.lower()


class UserSummary(ApiModel):
    id: UUID
    display_name: str
    role: str


class LoginResponse(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_in: int
    user: UserSummary


class OrganizationRef(ApiModel):
    id: UUID
    name: str


class MemberRef(ApiModel):
    member_number: str
    plan_code: str


class MeResponse(ApiModel):
    id: UUID
    display_name: str
    email: str
    role: str
    organization: OrganizationRef | None
    member: MemberRef | None
    permissions: list[str] = Field(description="For UI rendering only; the backend enforces access.")
