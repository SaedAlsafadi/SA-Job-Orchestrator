from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MonitoringRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    schedule_id: str
    status: str
    duration: float | None = None
    error: str | None = None
    jobs_found: int
    jobs_new: int
    jobs_eligible: int
    jobs_matched: int
    jobs_selected: int
    created_at: datetime


class MonitoringScheduleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    platform: str
    source: str
    interval_minutes: int
    is_active: bool
    last_checked_at: datetime | None = None
    match_threshold: float
    max_preparations_per_cycle: int
    runs: list[MonitoringRunSchema] = []
