"""Git interaction and diff analysis utilities for code review.

Provides routines to query commits, list changed files, parse unified diffs,
generate side-by-side split lines, and retrieve code line snippets.
"""

from datetime import datetime, timezone
import difflib
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Sequence, Tuple

from model.code_review import (
    CommitInfoModel,
    DiffHunk,
    DiffLine,
    DiffLineType,
    DiffSideBySideRow,
    FileDiffModel,
)


def extract_time_str(date_str: str) -> str:
    """Extract HH:MM:SS from ISO or git timestamp string."""
    if not date_str:
        return ""
    if "T" in date_str:
        return date_str.split("T")[1][:8]
    parts = date_str.split()
    if len(parts) >= 2 and ":" in parts[1]:
        return parts[1][:8]
    return ""


def run_git_command(args: List[str], cwd: Optional[Path] = None) -> str:
    """Execute a Git subcommand and return its standard output string.

    Args:
        args: List of command arguments passed to git.
        cwd: Directory where git command should execute.

    Returns:
        Standard output string from git command.

    Raises:
        RuntimeError: If git command fails with non-zero exit code.
    """
    cmd = ["git"] + args
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        err_msg = result.stderr.strip() or f"Git command failed with code {result.returncode}"
        raise RuntimeError(f"Error running {' '.join(cmd)}: {err_msg}")
    return result.stdout


def get_git_root(cwd: Optional[Path] = None) -> Path:
    """Determine the top-level root directory of the current git repository.

    Args:
        cwd: Starting search directory.

    Returns:
        Path to git repository root.
    """
    root_str = run_git_command(["rev-parse", "--show-toplevel"], cwd=cwd).strip()
    return Path(root_str)


class GitReviewEngine:
    """Git inspection engine providing revisions, diffs, and content."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        """Initialize GitReviewEngine with repository root.

        Args:
            repo_root: Root path of git repository.
        """
        self.repo_root = repo_root or get_git_root()

    def resolve_revisions(self, rev_args: Optional[Sequence[str]] = None) -> List[str]:
        """Resolve revision arguments (hashes, references, or ranges like A..B) into concrete revision identifiers.

        Supports:
        - "working" (local uncommitted working tree modifications)
        - Individual commit hashes or refs (e.g. "HEAD", "HEAD~1", "eff9b07")
        - Two-dot revision ranges (e.g. "A..B", "A..", "..B")
        - Three-dot symmetric difference ranges (e.g. "A...B")

        Args:
            rev_args: Sequence of revision strings or ranges from CLI or configuration.

        Returns:
            List of concrete commit hashes (and/or "working"), ordered newest to oldest, with duplicates removed.

        Raises:
            ValueError: If a revision range syntax is invalid or resolves to zero commits.
        """
        if not rev_args:
            return []

        resolved: List[str] = []
        for arg in rev_args:
            arg_str = str(arg).strip()
            if not arg_str:
                continue
            if arg_str == "working":
                if "working" not in resolved:
                    resolved.append("working")
            elif ".." in arg_str:
                try:
                    out = run_git_command(["rev-list", "--reverse", arg_str], cwd=self.repo_root).strip()
                except RuntimeError as err:
                    raise ValueError(f"Invalid git revision range '{arg_str}': {err}") from err

                if not out:
                    raise ValueError(f"No commits found in revision range '{arg_str}'.")

                for line in out.splitlines():
                    commit_hash = line.strip()
                    if commit_hash and commit_hash not in resolved:
                        resolved.append(commit_hash)
            else:
                try:
                    commit_hash = run_git_command(
                        ["rev-parse", "--verify", f"{arg_str}^{{commit}}"], cwd=self.repo_root
                    ).strip()
                except RuntimeError as err:
                    raise ValueError(f"Invalid git revision '{arg_str}': {err}") from err

                if commit_hash and commit_hash not in resolved:
                    resolved.append(commit_hash)

        return resolved

    def get_commits(self, limit: int = 30, rev_args: Optional[List[str]] = None) -> List[CommitInfoModel]:
        """Fetch list of commits or requested revisions in ascending chronological order.

        Args:
            limit: Maximum commits to return if no explicit revisions given.
            rev_args: Optional specific commits or ranges to fetch.

        Returns:
            List of CommitInfoModel instances.
        """
        commits: List[CommitInfoModel] = []

        # Check for working tree changes
        working_info = self._get_working_tree_info()

        if rev_args and len(rev_args) > 0:
            resolved_revs = self.resolve_revisions(rev_args)
            for rev in resolved_revs:
                if rev == "working":
                    if working_info and working_info.commit_hash not in [c.commit_hash for c in commits]:
                        commits.append(working_info)
                    continue
                commit = self._get_single_commit_info(rev)
                if commit and commit.commit_hash not in [c.commit_hash for c in commits]:
                    commits.append(commit)
            return commits

        # Query recent commit history in ascending chronological order
        fmt = "%H%x1f%h%x1f%an%x1f%ae%x1f%ad%x1f%s%x1f%b%x1e"
        cmd = ["log", f"-n{limit}", f"--format={fmt}", "--date=iso-strict", "--reverse"]
        output = run_git_command(cmd, cwd=self.repo_root)

        records = output.strip().split("\x1e")
        for rec in records:
            if not rec.strip():
                continue
            parts = rec.strip().split("\x1f")
            if len(parts) >= 6:
                c_hash = parts[0].strip()
                s_hash = parts[1].strip()
                author = parts[2].strip()
                email = parts[3].strip()
                date_str = parts[4].strip()
                subject = parts[5].strip()
                body = parts[6].strip() if len(parts) > 6 else ""

                additions, deletions, file_count = self._get_commit_stat_summary(c_hash)
                commits.append(
                    CommitInfoModel(
                        commit_hash=c_hash,
                        short_hash=s_hash,
                        author=author,
                        email=email,
                        date=date_str,
                        time=extract_time_str(date_str),
                        subject=subject,
                        body=body,
                        additions=additions,
                        deletions=deletions,
                        files_count=file_count,
                    )
                )

        if working_info is not None:
            commits.append(working_info)

        return commits

    def has_working_tree_changes(self) -> bool:
        """Check whether repository contains any uncommitted or untracked changes."""
        status_output = run_git_command(["status", "--porcelain"], cwd=self.repo_root).strip()
        return bool(status_output)

    def _get_working_tree_info(self) -> Optional[CommitInfoModel]:
        """Check if working tree has unstaged, staged, or untracked modifications."""
        status_output = run_git_command(["status", "--porcelain"], cwd=self.repo_root).strip()
        if not status_output:
            return None

        diff_stat = run_git_command(["diff", "HEAD", "--numstat"], cwd=self.repo_root).strip()
        additions = 0
        deletions = 0
        file_count = 0
        for line in diff_stat.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                file_count += 1
                if cols[0].isdigit():
                    additions += int(cols[0])
                if cols[1].isdigit():
                    deletions += int(cols[1])

        # Include untracked files in count and additions
        for line in status_output.splitlines():
            if line.startswith("?? "):
                file_path = line[3:].strip()
                file_count += 1
                full_path = self.repo_root / file_path
                if full_path.is_file():
                    try:
                        additions += len(full_path.read_text(encoding="utf-8", errors="replace").splitlines())
                    except OSError:
                        pass

        now = datetime.now(timezone.utc)
        return CommitInfoModel(
            commit_hash="working",
            short_hash="WORKING",
            author="Local Working Tree",
            email="local@workspace",
            date=f"Now ({now.strftime('%Y-%m-%d')})",
            time=now.strftime("%H:%M:%S"),
            subject=f"Uncommitted Changes ({file_count} modified files)",
            body=status_output,
            additions=additions,
            deletions=deletions,
            files_count=file_count,
        )

    def _get_single_commit_info(self, rev: str) -> Optional[CommitInfoModel]:
        """Fetch metadata for a single git commit revision."""
        fmt = "%H%x1f%h%x1f%an%x1f%ae%x1f%ad%x1f%s%x1f%b"
        try:
            output = run_git_command(["log", "-1", f"--format={fmt}", "--date=iso-strict", rev], cwd=self.repo_root)
        except RuntimeError:
            return None

        parts = output.strip().split("\x1f")
        if len(parts) >= 6:
            c_hash = parts[0].strip()
            s_hash = parts[1].strip()
            author = parts[2].strip()
            email = parts[3].strip()
            date_str = parts[4].strip()
            subject = parts[5].strip()
            body = parts[6].strip() if len(parts) > 6 else ""

            additions, deletions, file_count = self._get_commit_stat_summary(c_hash)
            return CommitInfoModel(
                commit_hash=c_hash,
                short_hash=s_hash,
                author=author,
                email=email,
                date=date_str,
                time=extract_time_str(date_str),
                subject=subject,
                body=body,
                additions=additions,
                deletions=deletions,
                files_count=file_count,
            )
        return None

    def search_code(self, query: str, commit: str = "working", max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for symbol, identifier, or text occurrences across files in revision or repository.

        Args:
            query: Search query pattern.
            commit: Revision hash, "HEAD", or "working".
            max_results: Maximum number of matches to return.

        Returns:
            List of match dictionaries containing file_path, line_number, and line_content.
        """
        if not query.strip():
            return []

        results: List[Dict[str, Any]] = []
        q = query.strip()

        if commit == "working":
            try:
                out = run_git_command(["grep", "-n", "-I", "-i", q], cwd=self.repo_root)
                for line in out.splitlines():
                    if len(results) >= max_results:
                        break
                    parts = line.split(":", 2)
                    if len(parts) >= 3 and parts[1].isdigit():
                        results.append(
                            {
                                "file_path": parts[0],
                                "line_number": int(parts[1]),
                                "line_content": parts[2].strip(),
                            }
                        )
            except RuntimeError:
                pass
        else:
            try:
                out = run_git_command(["grep", "-n", "-I", "-i", q, commit], cwd=self.repo_root)
                for line in out.splitlines():
                    if len(results) >= max_results:
                        break
                    parts = line.split(":", 3)
                    if len(parts) >= 4 and parts[2].isdigit():
                        results.append(
                            {
                                "file_path": parts[1],
                                "line_number": int(parts[2]),
                                "line_content": parts[3].strip(),
                            }
                        )
            except RuntimeError:
                pass

        return results

    def _get_commit_stat_summary(self, commit_hash: str) -> Tuple[int, int, int]:
        """Calculate additions, deletions, and file count for a commit."""
        cmd = ["diff-tree", "--no-commit-id", "--numstat", "-r", commit_hash]
        try:
            output = run_git_command(cmd, cwd=self.repo_root)
        except RuntimeError:
            return 0, 0, 0

        additions = 0
        deletions = 0
        file_count = 0
        for line in output.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                file_count += 1
                if cols[0].isdigit():
                    additions += int(cols[0])
                if cols[1].isdigit():
                    deletions += int(cols[1])
        return additions, deletions, file_count

    def get_changed_files(self, commit: str) -> List[Dict[str, str]]:
        """List changed files with status and stats for a revision."""
        if commit == "working":
            return self._get_working_tree_files()

        # Get status
        cmd_status = ["diff-tree", "--no-commit-id", "--name-status", "-r", commit]
        try:
            status_out = run_git_command(cmd_status, cwd=self.repo_root)
        except RuntimeError:
            return []

        # Get numstat
        cmd_numstat = ["diff-tree", "--no-commit-id", "--numstat", "-r", commit]
        try:
            numstat_out = run_git_command(cmd_numstat, cwd=self.repo_root)
        except RuntimeError:
            numstat_out = ""

        stats_map: Dict[str, Tuple[int, int]] = {}
        for line in numstat_out.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                path = cols[2].strip()
                adds = int(cols[0]) if cols[0].isdigit() else 0
                dels = int(cols[1]) if cols[1].isdigit() else 0
                stats_map[path] = (adds, dels)

        files = []
        for line in status_out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                status_code = parts[0].strip()
                file_path = parts[-1].strip()
                adds, dels = stats_map.get(file_path, (0, 0))
                files.append(
                    {
                        "path": file_path,
                        "status": status_code,
                        "additions": str(adds),
                        "deletions": str(dels),
                    }
                )
        return files

    def _get_working_tree_files(self) -> List[Dict[str, str]]:
        """List modified and untracked files in local working directory."""
        status_out = run_git_command(["status", "--porcelain"], cwd=self.repo_root)
        numstat_out = run_git_command(["diff", "HEAD", "--numstat"], cwd=self.repo_root)

        stats_map: Dict[str, Tuple[int, int]] = {}
        for line in numstat_out.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                path = cols[2].strip()
                adds = int(cols[0]) if cols[0].isdigit() else 0
                dels = int(cols[1]) if cols[1].isdigit() else 0
                stats_map[path] = (adds, dels)

        files = []
        for line in status_out.splitlines():
            if len(line) < 4:
                continue
            status_code = line[:2].strip()
            file_path = line[3:].strip()
            if " -> " in file_path:
                file_path = file_path.split(" -> ")[1].strip()
            adds, dels = stats_map.get(file_path, (0, 0))
            if status_code == "??" and adds == 0 and dels == 0:
                full_path = self.repo_root / file_path
                if full_path.is_file():
                    try:
                        adds = len(full_path.read_text(encoding="utf-8", errors="replace").splitlines())
                    except OSError:
                        pass
            files.append(
                {
                    "path": file_path,
                    "status": status_code or "M",
                    "additions": str(adds),
                    "deletions": str(dels),
                }
            )
        return files

    def get_file_content(self, commit: str, file_path: str, parent: bool = False) -> str:
        """Retrieve full text content of a file at a commit or parent."""
        if commit == "working":
            if parent:
                try:
                    return run_git_command(["show", f"HEAD:{file_path}"], cwd=self.repo_root)
                except RuntimeError:
                    return ""
            full_path = self.repo_root / file_path
            if full_path.exists() and full_path.is_file():
                try:
                    return full_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    return ""
            return ""

        rev_spec = f"{commit}^:{file_path}" if parent else f"{commit}:{file_path}"
        try:
            return run_git_command(["show", rev_spec], cwd=self.repo_root)
        except RuntimeError:
            return ""

    def get_file_diff(self, commit: str, file_path: str) -> FileDiffModel:
        """Construct comprehensive diff model including hunks and side-by-side rows."""
        old_content = self.get_file_content(commit, file_path, parent=True)
        new_content = self.get_file_content(commit, file_path, parent=False)

        raw_diff = ""
        try:
            if commit == "working":
                raw_diff = run_git_command(["diff", "HEAD", "--", file_path], cwd=self.repo_root)
            else:
                raw_diff = run_git_command(["diff", f"{commit}^", commit, "--", file_path], cwd=self.repo_root)
        except RuntimeError:
            raw_diff = ""

        if commit == "working" and not raw_diff and new_content:
            old_lines = old_content.splitlines(keepends=True) if old_content else []
            new_lines = new_content.splitlines(keepends=True)
            raw_diff = "".join(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{file_path}",
                    tofile=f"b/{file_path}",
                )
            )

        is_binary = "\x00" in old_content[:8000] or "\x00" in new_content[:8000]
        if is_binary:
            return FileDiffModel(
                file_path=file_path,
                is_binary=True,
                raw_diff=raw_diff or "Binary file differs",
                full_content="Binary file preview unavailable.",
            )

        hunks = self._parse_unified_diff(raw_diff)
        side_by_side = self._build_side_by_side_rows(old_content, new_content)

        additions = sum(1 for hunk in hunks for line in hunk.lines if line.type == DiffLineType.ADD)
        deletions = sum(1 for hunk in hunks for line in hunk.lines if line.type == DiffLineType.DELETE)

        return FileDiffModel(
            file_path=file_path,
            is_binary=False,
            additions=additions,
            deletions=deletions,
            hunks=hunks,
            side_by_side=side_by_side,
            full_content=new_content or old_content,
            old_content=old_content,
            new_content=new_content,
            raw_diff=raw_diff,
        )

    def _parse_unified_diff(self, raw_diff: str) -> List[DiffHunk]:
        """Parse raw git diff string into structured DiffHunks and DiffLines."""
        hunks: List[DiffHunk] = []
        current_hunk: Optional[DiffHunk] = None
        old_cur = 0
        new_cur = 0

        hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")

        for raw_line in raw_diff.splitlines():
            if raw_line.startswith("@@"):
                match = hunk_header_re.match(raw_line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2)) if match.group(2) else 1
                    new_start = int(match.group(3))
                    new_count = int(match.group(4)) if match.group(4) else 1
                    header_rest = match.group(5) or ""

                    current_hunk = DiffHunk(
                        header=f"@@ -{old_start},{old_count} +{new_start},{new_count} @@{header_rest}",
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                        lines=[],
                    )
                    hunks.append(current_hunk)
                    old_cur = old_start
                    new_cur = new_start
                continue

            if current_hunk is None:
                continue

            if raw_line.startswith("+"):
                current_hunk.lines.append(
                    DiffLine(
                        type=DiffLineType.ADD,
                        new_line_no=new_cur,
                        content=raw_line[1:],
                    )
                )
                new_cur += 1
            elif raw_line.startswith("-"):
                current_hunk.lines.append(
                    DiffLine(
                        type=DiffLineType.DELETE,
                        old_line_no=old_cur,
                        content=raw_line[1:],
                    )
                )
                old_cur += 1
            elif raw_line.startswith(" ") or raw_line == "":
                content = raw_line[1:] if raw_line.startswith(" ") else ""
                current_hunk.lines.append(
                    DiffLine(
                        type=DiffLineType.CONTEXT,
                        old_line_no=old_cur,
                        new_line_no=new_cur,
                        content=content,
                    )
                )
                old_cur += 1
                new_cur += 1

        return hunks

    def _build_side_by_side_rows(self, old_text: str, new_text: str) -> List[DiffSideBySideRow]:
        """Generate side-by-side aligned diff rows using SequenceMatcher."""
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        rows: List[DiffSideBySideRow] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            match tag:
                case "equal":
                    for offset in range(i2 - i1):
                        rows.append(
                            DiffSideBySideRow(
                                old_no=i1 + offset + 1,
                                old_text=old_lines[i1 + offset],
                                new_no=j1 + offset + 1,
                                new_text=new_lines[j1 + offset],
                                row_type="equal",
                            )
                        )
                case "delete":
                    for idx in range(i1, i2):
                        rows.append(
                            DiffSideBySideRow(
                                old_no=idx + 1,
                                old_text=old_lines[idx],
                                new_no=None,
                                new_text="",
                                row_type="delete",
                            )
                        )
                case "insert":
                    for idx in range(j1, j2):
                        rows.append(
                            DiffSideBySideRow(
                                old_no=None,
                                old_text="",
                                new_no=idx + 1,
                                new_text=new_lines[idx],
                                row_type="insert",
                            )
                        )
                case "replace":
                    count = max(i2 - i1, j2 - j1)
                    for offset in range(count):
                        old_idx = i1 + offset if i1 + offset < i2 else None
                        new_idx = j1 + offset if j1 + offset < j2 else None
                        rows.append(
                            DiffSideBySideRow(
                                old_no=old_idx + 1 if old_idx is not None else None,
                                old_text=old_lines[old_idx] if old_idx is not None else "",
                                new_no=new_idx + 1 if new_idx is not None else None,
                                new_text=new_lines[new_idx] if new_idx is not None else "",
                                row_type="replace",
                            )
                        )

        return rows


def extract_line_snippet(
    file_path: str,
    start_line: int,
    end_line: int,
    commit: str = "working",
    repo_root: Optional[Path] = None,
) -> str:
    """Extract slice of code lines from repository file for comment reference.

    Args:
        file_path: Relative path to target file.
        start_line: 1-indexed starting line number.
        end_line: 1-indexed ending line number.
        commit: Target revision or 'working'.
        repo_root: Git repository root.

    Returns:
        Formatted code snippet string.
    """
    engine = GitReviewEngine(repo_root=repo_root)
    content = engine.get_file_content(commit, file_path, parent=False)
    if not content:
        content = engine.get_file_content(commit, file_path, parent=True)
    if not content:
        return ""

    lines = content.splitlines()
    total_lines = len(lines)
    s = max(1, min(start_line, total_lines))
    e = max(s, min(end_line, total_lines))

    extracted = lines[s - 1 : e]
    return "\n".join(extracted)
