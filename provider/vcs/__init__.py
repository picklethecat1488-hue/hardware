"""Version Control System provider package.

Provides unified GitEngine for smartlog DAG trees, diff analysis, commit manipulation,
and merge conflict resolution across review and diff viewer workstations.
"""

from .git_engine import (
    IGNORED_REVIEW_FILES,
    GitEngine,
    extract_line_snippet,
    extract_time_str,
    get_git_root,
    is_file_ignored,
    run_git_command,
)

__all__ = [
    "GitEngine",
    "IGNORED_REVIEW_FILES",
    "extract_line_snippet",
    "extract_time_str",
    "get_git_root",
    "is_file_ignored",
    "run_git_command",
]
