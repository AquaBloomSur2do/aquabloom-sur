import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

SEMVER_PATTERN = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)

LibraryVersionStatus = Literal[
    "draft", "submitted", "approved", "published", "withdrawn"
]


class LibraryAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["known", "unknown"]
    name: str | None
    orcid: str | None = None

    @field_validator("name", "orcid")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El campo de texto no puede estar vacío.")
        return cleaned

    @model_validator(mode="after")
    def validate_author_consistency(self) -> "LibraryAuthor":
        if self.status == "known" and not self.name:
            raise ValueError(
                "Cuando author.status es 'known', author.name es obligatorio."
            )
        if self.status == "unknown" and self.name is not None:
            raise ValueError(
                "Cuando author.status es 'unknown', author.name debe ser null."
            )
        return self


class LibraryLicense(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spdx_id: str
    url: str | None = None

    @field_validator("spdx_id")
    @classmethod
    def validate_spdx_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("license.spdx_id es obligatorio.")
        return cleaned

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("license.url no puede ser una cadena vacía.")
        return cleaned


class LibrarySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str | None = None

    @field_validator("name")
    @classmethod
    def validate_source_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("source.name es obligatorio.")
        return cleaned

    @field_validator("url")
    @classmethod
    def normalize_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("source.url no puede ser una cadena vacía.")
        return cleaned


class LibraryAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author: LibraryAuthor
    license: LibraryLicense | None
    version: str
    source: LibrarySource

    @field_validator("version")
    @classmethod
    def validate_semver(cls, value: str) -> str:
        cleaned = value.strip()
        if not SEMVER_PATTERN.match(cleaned):
            raise ValueError(
                "version debe cumplir formato SemVer MAJOR.MINOR.PATCH."
            )
        return cleaned


class LibraryVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: UUID
    attribution: LibraryAttribution


class LibraryVersionResponse(BaseModel):
    id: UUID
    resource_id: UUID
    status: LibraryVersionStatus = "draft"
    attribution: LibraryAttribution
    created_by: str | None = None
    created_at: datetime
