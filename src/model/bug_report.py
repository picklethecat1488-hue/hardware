"""Domain data models for Bug Report CLI and Markdown Tracker.

Provides structured schemas for bug reports, severities, statuses, categories,
attachments (logs, screenshots, references), and bug collection management.
"""

from enum import StrEnum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class BugSeverity(StrEnum):
    """Severity ratings for engineering bug reports."""

    CRITICAL = "CRITICAL"  # Blocker / Severe defect preventing build or execution
    HIGH = "HIGH"  # Major functional defect or design flaw
    MEDIUM = "MEDIUM"  # Moderate issue with workaround available
    LOW = "LOW"  # Minor defect, cosmetic issue, or low-priority polish


class BugStatus(StrEnum):
    """Lifecycle status for a bug report."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class BugCategory(StrEnum):
    """Subsystem classification for bug reports."""

    CAD = "CAD"
    PCB = "PCB"
    SIMULATION = "SIMULATION"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    UI = "UI"
    GENERAL = "GENERAL"


class BugAttachmentModel(BaseModel):
    """File attachment (log, screenshot, CAD artifact, reference) associated with a bug."""

    id: str
    filename: str
    file_type: str = "reference"  # log, screenshot, reference, cad
    file_path: str
    size_bytes: int = 0
    description: str = ""
    created_at: str = ""


class BugReportModel(BaseModel):
    """Complete specification of an engineering bug report."""

    id: str
    title: str
    status: BugStatus = BugStatus.OPEN
    severity: BugSeverity = BugSeverity.MEDIUM
    category: BugCategory = BugCategory.PCB
    component: str = ""
    description: str = ""
    reproduction_steps: List[str] = Field(default_factory=list)
    expected_behavior: str = ""
    actual_behavior: str = ""
    logs: str = ""
    attachments: List[BugAttachmentModel] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    resolved_at: Optional[str] = None
    resolution_notes: str = ""


class BugDatabaseModel(BaseModel):
    """Container and serialization model for tracking repository bugs."""

    title: str = "Hardware Engineering Bug Tracker"
    summary: str = ""
    bugs: List[BugReportModel] = Field(default_factory=list)
    updated_at: str = ""

    def get_bug(self, bug_id: str) -> Optional[BugReportModel]:
        """Find a bug by its unique ID."""
        for b in self.bugs:
            if b.id == bug_id:
                return b
        return None

    def add_or_update(self, bug: BugReportModel) -> None:
        """Add a new bug or update an existing bug matching the ID."""
        for idx, existing in enumerate(self.bugs):
            if existing.id == bug.id:
                self.bugs[idx] = bug
                return
        self.bugs.append(bug)

    def count_by_status(self) -> Dict[str, int]:
        """Tally bugs grouped by lifecycle status."""
        counts = {st.value: 0 for st in BugStatus}
        for b in self.bugs:
            counts[b.status.value] = counts.get(b.status.value, 0) + 1
        return counts

    def count_by_severity(self) -> Dict[str, int]:
        """Tally bugs grouped by severity level."""
        counts = {sev.value: 0 for sev in BugSeverity}
        for b in self.bugs:
            counts[b.severity.value] = counts.get(b.severity.value, 0) + 1
        return counts

    def count_by_category(self) -> Dict[str, int]:
        """Tally bugs grouped by subsystem category."""
        counts = {cat.value: 0 for cat in BugCategory}
        for b in self.bugs:
            counts[b.category.value] = counts.get(b.category.value, 0) + 1
        return counts

    def generate_bug_id(self) -> str:
        """Generate next sequential bug ID (e.g. BUG-001, BUG-002)."""
        max_idx = 0
        for b in self.bugs:
            if b.id.startswith("BUG-"):
                try:
                    idx = int(b.id[4:])
                    if idx > max_idx:
                        max_idx = idx
                except ValueError:
                    pass
        return f"BUG-{max_idx + 1:03d}"
