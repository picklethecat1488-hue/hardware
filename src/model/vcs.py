"""Domain data models for Version Control, Git diffs, and Smartlog DAG trees.

Provides structured schemas for diff lines, hunks, side-by-side rows, file diffs,
commits, smartlog nodes, working tree states, and merge conflicts.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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
    new_path: Optional[str] = None
    status: str = "M"  # M, A, D, R, ??, etc.
    is_binary: bool = False
    is_lfs: bool = False
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
    time: str = ""
    subject: str
    body: str = ""
    additions: int = 0
    deletions: int = 0
    files_count: int = 0
    ignored_files_count: int = 0
    ignored_files: List[str] = Field(default_factory=list)


class BranchInfoModel(BaseModel):
    """Branch metadata including tracking information."""

    name: str
    is_current: bool = False
    is_remote: bool = False
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0

    @property
    def is_release_branch_candidate(self) -> bool:
        """Return True if this branch represents a main, master, or release branch."""
        name_lower = self.name.lower()
        if self.name in [
            "main",
            "master",
            "heads/main",
            "origin/main",
            "origin/master",
            "remotes/origin/main",
            "remotes/origin/master",
        ]:
            return True
        return bool(
            self.name.endswith("/main")
            or self.name.endswith("/master")
            or "release" in name_lower
            or "rel/" in name_lower
            or self.name.startswith("v")
            or self.name.startswith("origin/v")
            or self.name.startswith("remotes/origin/v")
            or "/v" in name_lower
        )


class CommitBugTagModel(BaseModel):
    """Bug status badge associated with a commit."""

    id: str
    title: str = ""
    status: str = "OPEN"
    severity: str = "LOW"


class CommitNodeModel(BaseModel):
    """Node in the smartlog topological DAG tree."""

    commit_hash: str
    short_hash: str
    parents: List[str] = Field(default_factory=list)
    children: List[str] = Field(default_factory=list)
    author: str
    email: str = ""
    date: str
    time: str = ""
    relative_date: str = ""
    subject: str
    body: str = ""
    branches: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    is_head: bool = False
    is_ancestor_top: bool = False
    is_merged: bool = False
    is_merged_into_tracking: bool = False
    ancestor_name: Optional[str] = None

    graph_symbol: str = "o"  # '@' for HEAD, 'o' for commit, 'x' for conflict/error
    graph_art: str = ""  # ASCII / Unicode tree column prefix (e.g. '@', '| o', '| /')
    bug_tags: List[CommitBugTagModel] = Field(default_factory=list)
    pr_status: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    files_count: int = 0
    is_feedback_only: bool = False
    cr_open_count: int = 0
    cr_resolved_count: int = 0
    cr_total_count: int = 0
    cr_reviewed: bool = False


class WorkingTreeFileModel(BaseModel):
    """Status record for a working tree file (staged, unstaged, untracked, conflicted)."""

    path: str
    status: str = "M"  # M, A, D, R, ??, UU, etc.
    index_status: str = " "
    worktree_status: str = " "
    is_staged: bool = False
    is_untracked: bool = False
    is_conflicted: bool = False
    is_feedback: bool = False
    is_lfs: bool = False
    additions: int = 0
    deletions: int = 0


class MergeConflictFileModel(BaseModel):
    """Conflicted file requiring manual or automatic merge resolution."""

    path: str
    conflict_type: str = "both_modified"
    conflict_markers_count: int = 0
    ours_summary: str = ""
    theirs_summary: str = ""


class DiffViewSessionModel(BaseModel):
    """Full session state for the interactive Quake Diff Viewer and Smartlog workstation."""

    repo_name: str = "hardware"
    repo_web_url: Optional[str] = None
    github_repo: str = ""
    current_branch: str = ""
    head_commit: str = ""
    active_commit: str = "working"
    active_file: Optional[str] = None
    selected_commits: List[str] = Field(default_factory=list)
    branches: List[BranchInfoModel] = Field(default_factory=list)
    smartlog_nodes: List[CommitNodeModel] = Field(default_factory=list)
    working_files: List[WorkingTreeFileModel] = Field(default_factory=list)
    conflicts: List[MergeConflictFileModel] = Field(default_factory=list)
    initial_sync_done: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
