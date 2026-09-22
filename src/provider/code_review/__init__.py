"""Code Review provider package.

Provides Git diff inspection, Quake-styled interactive web UI, REST API endpoints,
and Markdown export utilities.
"""

from .git_utils import (
    GitReviewEngine,
    get_git_root,
    extract_line_snippet,
    is_file_ignored,
    IGNORED_REVIEW_FILES,
)
from .markdown_exporter import MarkdownReviewExporter
from .server import ReviewServer
from .sqlite_store import SQLiteReviewStore

__all__ = [
    "GitReviewEngine",
    "get_git_root",
    "extract_line_snippet",
    "is_file_ignored",
    "IGNORED_REVIEW_FILES",
    "MarkdownReviewExporter",
    "ReviewServer",
    "SQLiteReviewStore",
]
