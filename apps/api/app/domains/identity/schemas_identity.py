import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None


class DashboardSummaryResponse(BaseModel):
    active_lakes_count: int
    active_stations_count: int
    visible_organizations_count: int


class MembershipCreate(BaseModel):
    profile_id: UUID
    role: Literal["admin", "member"]


class UserOrganizationResponse(BaseModel):
    id: UUID
    name: str
    role: str


class OrganizationMemberResponse(BaseModel):
    user_id: UUID
    profile_id: UUID | None = None
    full_name: str | None = None
    email: str | None = None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProfileOption(BaseModel):
    id: UUID
    email: str | None = None
    name: str | None = None


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    identifier: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9\-]+$", v):
            raise ValueError("El identificador solo admite minúsculas, números y guiones.")
        return v


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    identifier: str
    description: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
    