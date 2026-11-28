from typing import Literal

from pydantic import BaseModel, ConfigDict


class LibraryAuthorizationInfo(BaseModel):
    provider: Literal["core_supabase_jwt_rbac"] = "core_supabase_jwt_rbac"
    required_permission: str
    authenticated_subject: str | None = None

    model_config = ConfigDict(extra="forbid")


class LibraryStartupStatus(BaseModel):
    module: Literal["library"] = "library"
    status: Literal["ready", "disabled"]
    enabled: bool
    environment: str
    authorization: LibraryAuthorizationInfo
    routes: list[str]

    model_config = ConfigDict(extra="forbid")


