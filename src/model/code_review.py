"""Domain data models for Code Review Web UI and Markdown Exporter.

Provides structured schemas for code review sessions, commits, file diffs,
inline line comments, file statuses, and review severity tags.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
import uuid as uuid_pkg
from pydantic import BaseModel, Field


class ReviewSeverity(str, Enum):
    """Severity ratings for code review comments."""

    MUST_FIX = "MUST_FIX"  # Blocker / Critical defect that must be fixed
    PROPOSAL = "PROPOSAL"  # Architecture suggestion or conceptual enhancement
    NIT = "NIT"  # Trivial formatting, naming, or cosmetic cleanup


class ReviewStatus(str, Enum):
    """Overall review session verdict."""

    IN_REVIEW = "IN_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"


class FileReviewStatus(str, Enum):
    """Review completion state for individual files."""

    PENDING = "PENDING"
    REVIEWED = "REVIEWED"


from model.vcs import (
    CommitInfoModel,
    DiffHunk,
    DiffLine,
    DiffLineType,
    DiffMode,
    DiffSideBySideRow,
    FileDiffModel,
)


class CommentModel(BaseModel):
    """Inline or file-level review comment."""

    id: str
    uuid: str = Field(default_factory=lambda: str(uuid_pkg.uuid4()))
    file_path: str
    start_line: int
    end_line: int
    severity: ReviewSeverity = ReviewSeverity.MUST_FIX
    body: str
    author: str = "Reviewer"
    code_snippet: str = ""
    created_at: str
    resolved: bool = False
    commit: str = ""


class FileStateModel(BaseModel):
    """Review progress and notes for a specific file."""

    path: str
    status: FileReviewStatus = FileReviewStatus.PENDING
    notes: str = ""


class CommitUpdateModel(BaseModel):
    """Record of a commit update event (rebase, merge, amend, etc.)."""

    id: str = Field(default_factory=lambda: str(uuid_pkg.uuid4()))
    session_uuid: str = ""
    original_commit: str = ""
    current_commit: str = ""
    action: str = "update"  # e.g. rebase, merge, amend, sync, cherry-pick
    notes: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReviewSessionModel(BaseModel):
    """Stateful container for an entire code review session."""

    title: str = "Code Review"
    uuid: str = Field(default_factory=lambda: str(uuid_pkg.uuid4()))
    commit_hash: Optional[str] = None
    original_commit: Optional[str] = None
    update_action: Optional[str] = None
    commit_history: List[CommitUpdateModel] = Field(default_factory=list)
    summary: str = ""
    verdict: ReviewStatus = ReviewStatus.IN_REVIEW
    repo_name: str = "hardware"
    revisions: List[str] = Field(default_factory=list)
    files: Dict[str, FileStateModel] = Field(default_factory=dict)
    comments: List[CommentModel] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def record_commit_update(
        self, original_commit: str, current_commit: str, action: str, notes: str = ""
    ) -> CommitUpdateModel:
        """Record a commit update event in the review session."""
        update = CommitUpdateModel(
            session_uuid=self.uuid,
            original_commit=original_commit,
            current_commit=current_commit,
            action=action,
            notes=notes,
        )
        self.commit_history.append(update)
        self.original_commit = original_commit
        self.commit_hash = current_commit
        self.update_action = action
        return update

    def get_comment_by_uuid(self, comment_uuid: str) -> Optional[CommentModel]:
        """Find a comment by its unique UUID."""
        for c in self.comments:
            if c.uuid == comment_uuid:
                return c
        return None

    def get_file_state(self, file_path: str) -> FileStateModel:
        """Retrieve or create default file review state."""
        if file_path not in self.files:
            self.files[file_path] = FileStateModel(path=file_path)
        return self.files[file_path]

    def count_by_severity(self) -> Dict[str, int]:
        """Tally comments by severity level."""
        counts = {sev.value: 0 for sev in ReviewSeverity}
        for comment in self.comments:
            counts[comment.severity.value] += 1
        return counts

    def get_progress_stats(self, total_files: int) -> Dict[str, int]:
        """Calculate review completion statistics."""
        reviewed_count = sum(1 for f in self.files.values() if f.status == FileReviewStatus.REVIEWED)
        return {
            "reviewed": reviewed_count,
            "total": total_files,
            "comments_count": len(self.comments),
        }

    def auto_update_status_on_comment(self) -> None:
        """Reset review status back to IN_REVIEW when comments are added or feedback is drafted."""
        if self.verdict == ReviewStatus.APPROVED:
            self.verdict = ReviewStatus.IN_REVIEW
