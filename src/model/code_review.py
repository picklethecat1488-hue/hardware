"""Domain data models for Code Review Web UI and Markdown Exporter.

Provides structured schemas for code review sessions, commits, file diffs,
inline line comments, file statuses, and review severity tags.
"""

from enum import Enum
from typing import Dict, List, Optional
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


class DiffMode(str, Enum):
    """Visual presentation mode for code diffs."""

    SIDE_BY_SIDE = "side_by_side"
    UNIFIED = "unified"
    FULL_FILE = "full_file"


class DiffLineType(str, Enum):
    """Type classification for individual diff lines."""

    CONTEXT = "context"
    ADD = "add"
    DELETE = "delete"
    HEADER = "header"


class DiffLine(BaseModel):
    """Single line within a diff hunk."""

    type: DiffLineType
    old_line_no: Optional[int] = None
    new_line_no: Optional[int] = None
    content: str = ""


class DiffHunk(BaseModel):
    """Grouped section of contiguous diff lines with header."""

    header: str
    old_start: int = 1
    old_count: int = 0
    new_start: int = 1
    new_count: int = 0
    lines: List[DiffLine] = Field(default_factory=list)


class DiffSideBySideRow(BaseModel):
    """Paired row comparing old and new file state side-by-side."""

    old_no: Optional[int] = None
    old_text: str = ""
    new_no: Optional[int] = None
    new_text: str = ""
    row_type: str = "equal"  # equal, insert, delete, replace


class FileDiffModel(BaseModel):
    """Complete diff and content representation for a single file."""

    file_path: str
    old_path: Optional[str] = None
    status: str = "M"  # M, A, D, R, etc.
    is_binary: bool = False
    additions: int = 0
    deletions: int = 0
    hunks: List[DiffHunk] = Field(default_factory=list)
    side_by_side: List[DiffSideBySideRow] = Field(default_factory=list)
    full_content: str = ""
    old_content: str = ""
    new_content: str = ""
    raw_diff: str = ""


class CommitInfoModel(BaseModel):
    """Git commit metadata and change statistics."""

    commit_hash: str
    short_hash: str
    author: str
    email: str = ""
    date: str
    subject: str
    body: str = ""
    additions: int = 0
    deletions: int = 0
    files_count: int = 0


class CommentModel(BaseModel):
    """Inline or file-level review comment."""

    id: str
    file_path: str
    start_line: int
    end_line: int
    severity: ReviewSeverity = ReviewSeverity.MUST_FIX
    body: str
    author: str = "Reviewer"
    code_snippet: str = ""
    created_at: str
    resolved: bool = False


class FileStateModel(BaseModel):
    """Review progress and notes for a specific file."""

    path: str
    status: FileReviewStatus = FileReviewStatus.PENDING
    notes: str = ""


class ReviewSessionModel(BaseModel):
    """Stateful container for an entire code review session."""

    title: str = "Code Review"
    summary: str = ""
    verdict: ReviewStatus = ReviewStatus.IN_REVIEW
    repo_name: str = "hardware"
    revisions: List[str] = Field(default_factory=list)
    files: Dict[str, FileStateModel] = Field(default_factory=dict)
    comments: List[CommentModel] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

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
