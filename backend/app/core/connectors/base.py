from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QuestionCategory(StrEnum):
    A_PREFILLED_PLATFORM_PROFILE = "A"
    B_DETERMINISTIC_CANDIDATE_DATA = "B"
    C_STORED_USER_PREFERENCE = "C"
    D_AI_EVIDENCE_GROUNDED = "D"
    E_UNKNOWN_HIGH_RISK = "E"
    F_OPTIONAL_EMPTY = "F"


class ConnectorCapabilities(BaseModel):
    discovery: bool
    job_details: bool
    application_preparation: bool
    prefilled_profile_detection: bool
    resume_upload: bool
    question_handling: bool
    human_review: bool
    submission: bool
    status_monitoring: bool


class ApplicationQuestion(BaseModel):
    model_config = ConfigDict(frozen=False)

    question_id: str
    label: str
    input_type: str  # text, select, file, radio, checkbox
    required: bool = False
    options: list[str] = Field(default_factory=list)

    # State inspection fields
    current_value: str | None = None
    prefilled: bool = False
    editable: bool = True
    visible: bool = True

    # Engine resolution fields
    category: QuestionCategory | None = None
    answer: str | None = None
    confidence: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    requires_human: bool = False


class JobSource(ABC):
    """Generic interface for discovering and fetching jobs from external platforms."""

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def capabilities(self) -> ConnectorCapabilities:
        pass

    @abstractmethod
    async def discover_jobs(self, url: str) -> list[dict[str, Any]]:
        """Given a URL (e.g., career page), return list of raw job dicts."""
        pass

    @abstractmethod
    async def fetch_job(self, external_job_id: str) -> dict[str, Any]:
        """Fetch raw details for a specific job ID."""
        pass

    @abstractmethod
    def normalize_job(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw job payload to our canonical Job schema dict."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the integration is operational."""
        pass


class ApplicationConnector(ABC):
    """Generic interface for automating job applications."""

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this connector can automate the given URL."""
        pass

    @abstractmethod
    async def open_application(self, url: str, page) -> None:
        """Navigate to the application form."""
        pass

    @abstractmethod
    async def inspect_form(self, page) -> list[ApplicationQuestion]:
        """Parse the page to extract questions."""
        pass

    @abstractmethod
    async def fill_field(self, page, question_id: str, value: str) -> None:
        """Fill a specific field in the DOM."""
        pass

    @abstractmethod
    async def upload_resume(self, page, file_path: str) -> None:
        """Upload the CV to the appropriate file input."""
        pass

    @abstractmethod
    async def answer_question(self, page, question: ApplicationQuestion) -> None:
        """Answer a resolved question in the DOM."""
        pass

    @abstractmethod
    async def capture_state(self, page) -> dict[str, Any]:
        """Capture DOM snapshot, screenshot paths, and current values."""
        pass

    @abstractmethod
    async def submit(self, page) -> None:
        """Click the final submit button."""
        pass

    @abstractmethod
    async def capture_confirmation(self, page) -> str:
        """Verify submission and capture confirmation details."""
        pass
