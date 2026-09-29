"""Dashboard feed dismissal schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DashboardDismissalCreate(BaseModel):
    entity_type: str = Field(pattern="^(application|activity)$")
    entity_id: str = Field(min_length=1, max_length=32)
    fingerprint: str = Field(min_length=1, max_length=200)


class DashboardDismissalResponse(DashboardDismissalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dismissed_at: datetime


class DashboardDismissalList(BaseModel):
    items: list[DashboardDismissalResponse]
