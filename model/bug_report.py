"""Domain data models for Bug Report CLI and Markdown Tracker.

Provides structured schemas for bug reports, severities, statuses, categories,
attachments (logs, screenshots, references), and bug collection management.
"""

from collections.abc import Collection
from enum import StrEnum
from typing import Dict, List, Optional
import uuid as uuid_pkg
from pydantic import BaseModel, Field

from model.id_generator import generate_docker_pattern_id


class BugSeverity(StrEnum):
    """Severity ratings for engineering bug reports."""

    CRITICAL = "CRITICAL"  # Blocker / Severe defect preventing build or execution
    HIGH = "HIGH"  # Major functional defect or design flaw
    MEDIUM = "MEDIUM"  # Moderate issue with workaround available
    LOW = "LOW"  # Minor defect, cosmetic issue, or low-priority polish


class BugStatus(StrEnum):
    """Lifecycle status for a bug report."""

    OPEN = "OPEN"
    PLANNED = "PLANNED"
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


class ReviewTaskStatus(StrEnum):
    """Lifecycle status for a functional review task."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BugAttachmentModel(BaseModel):
    """File attachment (log, screenshot, CAD artifact, reference) associated with a bug."""

    id: str
    filename: str
    file_type: str = "reference"  # log, screenshot, reference, cad
    file_path: str
    size_bytes: int = 0
    description: str = ""
    created_at: str = ""


class ReviewTaskModel(BaseModel):
    """A functional verification or review task for a bug."""

    id: str = Field(default_factory=lambda: str(uuid_pkg.uuid4())[:8])
    title: str
    command: str = ""  # Shell command or visualization action to demo functionality
    status: ReviewTaskStatus = ReviewTaskStatus.PENDING
    notes: str = ""


class BugReportModel(BaseModel):
    """Complete specification of an engineering bug report."""

    id: str
    uuid: str = Field(default_factory=lambda: str(uuid_pkg.uuid4()))
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
    commit_ids: List[str] = Field(default_factory=list)
    review_tasks: List[ReviewTaskModel] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    resolved_at: Optional[str] = None
    resolution_notes: str = ""
    rejection_notes: Optional[str] = None
    accepted_at: Optional[str] = None
    rejected_at: Optional[str] = None


class BugDatabaseModel(BaseModel):
    """Container and serialization model for tracking repository bugs."""

    title: str = "Hardware Engineering Bug Tracker"
    summary: str = ""
    bugs: List[BugReportModel] = Field(default_factory=list)
    updated_at: str = ""

    def get_bug(self, bug_id: str) -> Optional[BugReportModel]:
        """Find a bug by its unique ID (exact, case-insensitive, or prefix-normalized)."""
        clean_target = bug_id.strip()
        for b in self.bugs:
            if b.id == clean_target:
                return b
        for b in self.bugs:
            if b.id.upper() == clean_target.upper():
                return b
        for b in self.bugs:
            norm_b = b.id.removeprefix("BUG-").removeprefix("WORM-").upper()
            norm_target = clean_target.removeprefix("BUG-").removeprefix("WORM-").upper()
            if norm_b == norm_target:
                return b
        return None

    def get_bug_by_uuid(self, bug_uuid: str) -> Optional[BugReportModel]:
        """Find a bug by its unique UUID."""
        for b in self.bugs:
            if b.uuid == bug_uuid:
                return b
        return None

    def add_or_update(self, bug: BugReportModel) -> str:
        """Add a new bug or update an existing bug matching UUID or ID.

        Performs collision detection: If a bug arrives with an existing ID but a different
        UUID, it is identified as a distinct entity and automatically assigned a new unique
        ID to prevent data loss or clobbering.

        Returns:
            The canonical (possibly reassigned) bug ID.
        """
        existing_by_uuid_idx = None
        existing_by_id_idx = None
        for idx, existing in enumerate(self.bugs):
            if bug.uuid and existing.uuid == bug.uuid:
                existing_by_uuid_idx = idx
            if existing.id == bug.id:
                existing_by_id_idx = idx

        if existing_by_uuid_idx is not None and existing_by_id_idx is not None:
            if existing_by_uuid_idx == existing_by_id_idx:
                self.bugs[existing_by_uuid_idx] = bug
                return bug.id
            else:
                # UUID matches bug A, but requested ID is already held by bug B
                known_ids = {b.id for b in self.bugs}
                bug.id = self.generate_bug_id(existing_ids=known_ids)
                self.bugs[existing_by_uuid_idx] = bug
                return bug.id
        elif existing_by_uuid_idx is not None:
            self.bugs[existing_by_uuid_idx] = bug
            return bug.id
        elif existing_by_id_idx is not None:
            # Collision! Different UUID (or new bug) has an ID already taken by an existing bug
            known_ids = {b.id for b in self.bugs}
            bug.id = self.generate_bug_id(existing_ids=known_ids)
            if not bug.uuid:
                bug.uuid = str(uuid_pkg.uuid4())
            self.bugs.append(bug)
            return bug.id
        else:
            if not bug.uuid:
                bug.uuid = str(uuid_pkg.uuid4())
            self.bugs.append(bug)
            return bug.id

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

    def generate_bug_id(self, existing_ids: Optional[Collection[str]] = None) -> str:
        """Generate a random Docker-pattern bug ID using a CRNG (secrets/os.urandom).

        Format: BUG-[ADJECTIVE]-[ANIMAL/NOUN]-[3 digits]
        Examples:
            - BUG-BUZZING-BEETLE-42
            - BUG-CHITINOUS-MANTIS-809
            - BUG-SCUTTLING-CICADA-17
        """
        known = set(existing_ids or [])
        for b in self.bugs:
            known.add(b.id)
        return generate_docker_pattern_id(prefix="BUG", existing_ids=known)
