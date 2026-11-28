import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
ORCID_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$")

LibraryVersionStatus = Literal[
    "draft", "submitted", "approved", "published", "withdrawn"
]


def _validate_optional_http_url(value: str | None, field_label: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_label} no puede ser una cadena vacía.")
    if len(cleaned) > 2048:
        raise ValueError(f"{field_label} excede el máximo de 2048 caracteres.")
    if any(ch.isspace() for ch in cleaned):
        raise ValueError(f"{field_label} no puede contener espacios.")
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_label} debe ser una URL http:// o https:// válida.")
    return cleaned


class LibraryAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["known", "unknown"]
    name: str | None = Field(default=None, max_length=200)
    orcid: str | None = Field(default=None, max_length=32)

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
        if self.status == "known":
            if not self.name:
                raise ValueError(
                    "Cuando author.status es 'known', author.name es obligatorio."
                )
            if self.orcid is not None and not ORCID_PATTERN.match(self.orcid):
                raise ValueError(
                    "author.orcid debe cumplir el formato estándar 0000-0000-0000-000X."
                )
        else:
            if self.name is not None:
                raise ValueError(
                    "Cuando author.status es 'unknown', author.name debe ser null."
                )
            if self.orcid is not None:
                raise ValueError(
                    "Cuando author.status es 'unknown', author.orcid debe ser null."
                )
        return self


class LibraryLicense(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spdx_id: str = Field(..., max_length=100)
    url: str | None = Field(default=None, max_length=2048)

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
        return _validate_optional_http_url(value, "license.url")


class LibrarySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=255)
    url: str | None = Field(default=None, max_length=2048)

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
        return _validate_optional_http_url(value, "source.url")


class LibraryAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author: LibraryAuthor
    license: LibraryLicense | None
    version: str = Field(..., max_length=64)
    source: LibrarySource

    @field_validator("version")
    @classmethod
    def validate_semver(cls, value: str) -> str:
        cleaned = value.strip()
        if not SEMVER_PATTERN.match(cleaned):
            raise ValueError(
                "version debe cumplir formato SemVer MAJOR.MINOR.PATCH sin ceros a la izquierda."
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
