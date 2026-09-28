"""Quake Diff Viewer and Smartlog ancestor tree workstation package.

Provides HTTP server, REST APIs, and UI templates for interactive VCS inspection,
branch navigation, smartlog DAG trees, commit manipulation, working tree management,
and seamless inter-tool coordination with code_review and bug_report.
"""

from provider.diff_view.server import DiffViewServer

__all__ = ["DiffViewServer"]
