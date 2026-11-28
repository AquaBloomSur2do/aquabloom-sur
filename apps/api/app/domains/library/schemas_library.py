from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ReviewRequestStatus = Literal[
    "submitted",
    "approved",
    "changes_requested",
    "withdrawn",
]


class ResourceReviewRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    notes: str | None = Field(default=None, max_length=1000)


class ResourceReviewRequestResponse(BaseModel):
    id: UUID
    version_id: UUID
    author_id: UUID
    status: ReviewRequestStatus
    notes: str | None = None
    created_at: datetime
