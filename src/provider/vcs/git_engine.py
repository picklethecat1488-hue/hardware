"""Git interaction, diff analysis, and Smartlog DAG engine.

Provides routines to query commits, list changed files, parse unified diffs,
generate side-by-side split lines, retrieve code line snippets, manage working
tree states (staging, unstaging, discarding, committing), split and combine commits,
resolve merge conflicts, and build topological ancestor DAG trees.
"""

from datetime import datetime, timezone
import difflib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from model.vcs import (
    BranchInfoModel,
    CommitBugTagModel,
    CommitInfoModel,
    CommitNodeModel,
    DiffHunk,
    DiffLine,
    DiffLineType,
    DiffSideBySideRow,
    FileDiffModel,
    MergeConflictFileModel,
    WorkingTreeFileModel,
)

MAX_DIFF_LINE_LENGTH: int = 1000
IGNORED_REVIEW_FILES: frozenset[str] = frozenset({"BUGS.md", "BUGS.txt", "CR.md"})


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
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
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


def is_file_ignored(file_path: str) -> bool:
    """Check if file should be hidden from code review inspection.

    Args:
        file_path: Relative or absolute file path or filename.

    Returns:
        True if file is in IGNORED_REVIEW_FILES, in feedback/ directory, or matches ignored patterns.
    """
    clean = file_path.replace("\\", "/").strip().lstrip("./")
    p = Path(clean)
    if "feedback" in p.parts:
        return True
    if p.name in IGNORED_REVIEW_FILES or clean in IGNORED_REVIEW_FILES:
        return True
    if p.name.startswith("BUG_") or p.name.startswith("CR_"):
        return True
    return False


def extract_line_snippet(
    file_path: str,
    start_line: int,
    end_line: int,
    commit: str = "working",
    repo_root: Optional[Path] = None,
    context_padding: int = 0,
) -> str:
    """Extract code lines for a given line range from a revision or working directory.

    Args:
        file_path: Relative repository path to file.
        start_line: 1-indexed starting line.
        end_line: 1-indexed ending line.
        commit: Git revision hash or "working".
        repo_root: Path to git repository root.
        context_padding: Additional surrounding context lines to include.

    Returns:
        Extracted source lines joined by newlines.
    """
    root = repo_root or get_git_root()
    content = ""
    if commit == "working":
        full_path = root / file_path
        if full_path.exists() and full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""
    else:
        try:
            content = run_git_command(["show", f"{commit}:{file_path}"], cwd=root)
        except RuntimeError:
            return ""

    if not content:
        return ""

    lines = content.splitlines()
    first = max(1, start_line - context_padding)
    last = min(len(lines), end_line + context_padding)
    return "\n".join(lines[first - 1 : last])


class GitEngine:
    """Unified VCS and Git inspection engine for reviews, diffs, and smartlog DAGs."""

    @staticmethod
    def is_file_ignored(file_path: str) -> bool:
        """Check if file should be hidden from standard code review inspection."""
        return is_file_ignored(file_path)

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        """Initialize GitEngine with repository root.

        Args:
            repo_root: Root path of git repository.
        """
        self.repo_root = repo_root or get_git_root()

    def get_head_commit(self) -> str:
        """Retrieve the commit hash of HEAD in the repository.

        Returns:
            Full commit hash string, or empty string if repository has no commits or fails.
        """
        try:
            return run_git_command(["rev-parse", "HEAD"], cwd=self.repo_root).strip()
        except RuntimeError:
            return ""

    def get_current_branch(self) -> str:
        """Retrieve the current active branch name or detached HEAD indicator."""
        try:
            branch = run_git_command(["branch", "--show-current"], cwd=self.repo_root).strip()
            if branch:
                return branch
            # Detached HEAD, return short hash
            short_head = run_git_command(["rev-parse", "--short", "HEAD"], cwd=self.repo_root).strip()
            return f"(detached at {short_head})"
        except RuntimeError:
            return "unknown"

    def get_branches(self) -> List[BranchInfoModel]:
        """Fetch list of local and remote branches with upstream tracking info."""
        branches: List[BranchInfoModel] = []
        current_branch = self.get_current_branch()

        try:
            fmt = "%(refname)%09%(refname:short)%09%(upstream:short)%09%(upstream:track)"
            out = run_git_command(
                ["for-each-ref", f"--format={fmt}", "refs/heads/", "refs/remotes/"], cwd=self.repo_root
            )
            local_names = set()
            remote_entries = []

            for line in out.splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                refname = parts[0].strip()
                short_name = parts[1].strip() if len(parts) > 1 else ""
                upstream = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
                track = parts[3].strip() if len(parts) > 3 else ""

                if refname.endswith("/HEAD") or short_name.endswith("/HEAD"):
                    continue

                ahead = 0
                behind = 0
                if "ahead " in track:
                    m = re.search(r"ahead (\d+)", track)
                    if m:
                        ahead = int(m.group(1))
                if "behind " in track:
                    m = re.search(r"behind (\d+)", track)
                    if m:
                        behind = int(m.group(1))

                if refname.startswith("refs/heads/"):
                    clean_name = refname[len("refs/heads/") :]
                    local_names.add(clean_name)
                    branches.append(
                        BranchInfoModel(
                            name=clean_name,
                            is_current=(clean_name == current_branch or short_name == current_branch),
                            is_remote=False,
                            upstream=upstream,
                            ahead=ahead,
                            behind=behind,
                        )
                    )
                elif refname.startswith("refs/remotes/"):
                    remote_name = refname[len("refs/remotes/") :]
                    remote_entries.append((remote_name, upstream, ahead, behind))

            # Add remote branches that do not have a local branch with the same name
            for remote_name, upstream, ahead, behind in remote_entries:
                short_remote = remote_name.split("/", 1)[1] if "/" in remote_name else remote_name
                if short_remote in local_names:
                    continue
                branches.append(
                    BranchInfoModel(
                        name=remote_name,
                        is_current=False,
                        is_remote=True,
                        upstream=upstream,
                        ahead=ahead,
                        behind=behind,
                    )
                )
        except RuntimeError:
            pass

        return branches

    def checkout_branch(self, branch_name: str) -> bool:
        """Switch repository to specified branch.

        Args:
            branch_name: Name of branch to checkout.

        Returns:
            True if checkout succeeded.
        """
        try:
            if branch_name.startswith("origin/"):
                try:
                    run_git_command(["checkout", "--track", branch_name], cwd=self.repo_root)
                    return True
                except RuntimeError:
                    pass
            run_git_command(["checkout", branch_name], cwd=self.repo_root)
            return True
        except RuntimeError:
            return False

    def sync_repo(self) -> Dict[str, Any]:
        """Synchronize repository with remotes by running git fetch.

        Returns:
            Dictionary with status, message, and updated refs count.
        """
        try:
            out = run_git_command(["fetch", "--all", "--prune"], cwd=self.repo_root)
            curr_branch = self.get_current_branch()
            if curr_branch not in ("main", "refs/heads/main"):
                for cand_ref in ["refs/remotes/origin/main", "origin/main"]:
                    try:
                        run_git_command(["branch", "-f", "main", cand_ref], cwd=self.repo_root)
                        break
                    except RuntimeError:
                        pass
            return {
                "status": "ok",
                "message": out.strip() or "Repository successfully fetched and synchronized.",
            }
        except RuntimeError as err:
            return {
                "status": "error",
                "message": f"Fetch failed: {err}",
            }

    def rebase_branch(self, upstream: Optional[str] = None) -> Dict[str, Any]:
        """Rebase current branch onto upstream ancestor (e.g., origin/main or main).

        Args:
            upstream: Ref to rebase onto. Defaults to upstream tracking ref or origin/main / main.

        Returns:
            Dictionary with status, message, and target ref.
        """
        target = upstream
        if not target:
            try:
                target = run_git_command(
                    ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd=self.repo_root
                ).strip()
            except RuntimeError:
                pass
        if not target:
            for candidate in [
                "refs/remotes/origin/main",
                "refs/heads/main",
                "refs/remotes/origin/master",
                "refs/heads/master",
            ]:
                try:
                    run_git_command(["rev-parse", "--verify", candidate], cwd=self.repo_root)
                    target = candidate
                    break
                except RuntimeError:
                    continue
        if not target:
            return {
                "status": "error",
                "message": "No suitable upstream ancestor branch found to rebase onto.",
                "target": None,
            }

        try:
            out = run_git_command(["rebase", target], cwd=self.repo_root)
            if "origin/main" in target:
                try:
                    run_git_command(["branch", "-f", "main", "refs/remotes/origin/main"], cwd=self.repo_root)
                except RuntimeError:
                    pass
            clean_target = target.replace("refs/remotes/origin/", "").replace("refs/heads/", "")
            return {
                "status": "ok",
                "message": out.strip() or f"Successfully rebased onto {clean_target}.",
                "target": clean_target,
            }
        except RuntimeError as err:
            try:
                run_git_command(["rebase", "--abort"], cwd=self.repo_root)
            except RuntimeError:
                pass
            return {
                "status": "error",
                "message": f"Rebase onto {target} failed: {err}",
                "target": target,
            }

    def resolve_revisions(self, rev_args: Optional[Sequence[str]] = None) -> List[str]:
        """Resolve revision arguments (hashes, references, or ranges) into concrete identifiers.

        Args:
            rev_args: Sequence of revision strings or ranges from CLI or configuration.

        Returns:
            List of concrete commit hashes (and/or "working"), ordered newest to oldest, without duplicates.

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
        """Fetch list of commits or requested revisions in ascending chronological order."""
        commits: List[CommitInfoModel] = []
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

        fmt = "%H%x1f%h%x1f%an%x1f%ae%x1f%ad%x1f%s%x1f%b%x1e"
        cmd = ["log", f"-n{limit}", f"--format={fmt}", "--date=iso-strict", "--reverse"]
        try:
            output = run_git_command(cmd, cwd=self.repo_root)
        except RuntimeError:
            output = ""

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

                additions, deletions, file_count, ignored_files = self._get_commit_stat_summary(c_hash)
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
                        ignored_files_count=len(ignored_files),
                        ignored_files=ignored_files,
                    )
                )

        if working_info is not None:
            commits.append(working_info)

        return commits

    def get_smartlog_dag(self, limit: int = 50, branch: Optional[str] = None) -> List[CommitNodeModel]:
        """Build topological smartlog DAG tree with ancestor columns, branch glyphs, and bug tags.

        Args:
            limit: Maximum commits to include in smartlog.
            branch: Optional branch ref to start traversal from.

        Returns:
            List of CommitNodeModel items ordered newest to oldest with computed DAG graph_art.
        """
        head_hash = self.get_head_commit()
        target_ref = branch or "HEAD"

        # Determine ancestor branch (e.g. main/master) and merge-base (BUG-213)
        ancestor_name: Optional[str] = None
        ancestor_merge_base: Optional[str] = None
        for candidate_ref, cand_name in [
            ("refs/remotes/origin/main", "main"),
            ("refs/heads/main", "main"),
            ("refs/remotes/origin/master", "master"),
            ("refs/heads/master", "master"),
        ]:
            try:
                run_git_command(["rev-parse", "--verify", candidate_ref], cwd=self.repo_root)
                mb = run_git_command(["merge-base", target_ref, candidate_ref], cwd=self.repo_root).strip()
                if mb:
                    ancestor_merge_base = mb
                    ancestor_name = cand_name
                    break
            except RuntimeError:
                continue

        # Resolve upstream tracking reference to identify merged commits (BUG-218)
        tracking_candidates = []
        try:
            upstream = run_git_command(
                ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd=self.repo_root
            ).strip()
            if upstream:
                tracking_candidates.append(upstream)
        except RuntimeError:
            pass

        current_local_ref = f"refs/heads/{self.get_current_branch()}" if self.get_current_branch() else None
        for c_cand in [
            "refs/remotes/origin/main",
            "refs/heads/main",
            "refs/remotes/origin/master",
            "refs/heads/master",
        ]:
            if c_cand != current_local_ref and c_cand not in tracking_candidates:
                tracking_candidates.append(c_cand)

        active_tracking_ref = None
        for t_ref in tracking_candidates:
            try:
                run_git_command(["rev-parse", "--verify", t_ref], cwd=self.repo_root)
                active_tracking_ref = t_ref
                break
            except RuntimeError:
                continue

        # Check if target is a topic branch diverging from ancestor
        target_hash = head_hash if target_ref == "HEAD" else None
        if not target_hash:
            try:
                target_hash = run_git_command(["rev-parse", target_ref], cwd=self.repo_root).strip()
            except RuntimeError:
                target_hash = ""

        is_topic_branch = bool(ancestor_merge_base and target_hash != ancestor_merge_base)

        merged_commit_hashes: set[str] = set()
        if active_tracking_ref:
            try:
                out = run_git_command(["rev-list", f"-n{max(limit * 2, 200)}", active_tracking_ref], cwd=self.repo_root)
                merged_commit_hashes = set(out.splitlines())
            except RuntimeError:
                pass
        if ancestor_merge_base and is_topic_branch:
            merged_commit_hashes.add(ancestor_merge_base)

        fmt = "%H%x1f%h%x1f%P%x1f%an%x1f%ae%x1f%ad%x1f%ar%x1f%s%x1f%D%x1f%b%x1e"
        cmd = ["log", f"-n{limit}", f"--format={fmt}", "--date=iso-strict", target_ref]
        try:
            output = run_git_command(cmd, cwd=self.repo_root)
        except RuntimeError:
            return []

        raw_records = output.strip().split("\x1e")
        parsed_commits: List[Dict[str, Any]] = []

        for rec in raw_records:
            if not rec.strip():
                continue
            parts = rec.strip().split("\x1f")
            if len(parts) >= 8:
                c_hash = parts[0].strip()
                s_hash = parts[1].strip()
                parents = parts[2].strip().split() if parts[2].strip() else []
                author = parts[3].strip()
                email = parts[4].strip()
                date_str = parts[5].strip()
                rel_date = parts[6].strip()
                subject = parts[7].strip()
                decorations_str = parts[8].strip() if len(parts) > 8 else ""
                body = parts[9].strip() if len(parts) > 9 else ""

                # Parse branches and tags from decorations
                branches: List[str] = []
                tags: List[str] = []
                if decorations_str:
                    for item in decorations_str.split(","):
                        dec = item.strip()
                        if dec.startswith("tag: "):
                            tags.append(dec[5:].strip())
                        elif "->" in dec:
                            branches.append(dec.split("->")[1].strip())
                        elif dec and dec != "HEAD":
                            branches.append(dec)

                is_ancestor_top = c_hash == ancestor_merge_base

                is_merged = bool(c_hash in merged_commit_hashes)
                if is_ancestor_top and ancestor_name and ancestor_name not in branches:
                    branches.append(ancestor_name)

                parsed_commits.append(
                    {
                        "hash": c_hash,
                        "short_hash": s_hash,
                        "parents": parents,
                        "author": author,
                        "email": email,
                        "date": date_str,
                        "relative_date": rel_date,
                        "subject": subject,
                        "body": body,
                        "branches": branches,
                        "tags": tags,
                        "is_head": (c_hash == head_hash),
                        "is_ancestor_top": is_ancestor_top,
                        "is_merged": is_merged,
                        "is_merged_into_tracking": is_merged,
                        "ancestor_name": ancestor_name if is_ancestor_top else None,
                    }
                )

                # Prune older commits already merged into ancestor branch (BUG-213)
                if is_topic_branch and is_ancestor_top:
                    break

        # Build DAG lanes / column positions
        columns: List[Optional[str]] = []
        nodes: List[CommitNodeModel] = []

        for commit in parsed_commits:
            c_hash = commit["hash"]
            parents = commit["parents"]

            if c_hash in columns:
                col_idx = columns.index(c_hash)
            else:
                if None in columns:
                    col_idx = columns.index(None)
                    columns[col_idx] = c_hash
                else:
                    col_idx = len(columns)
                    columns.append(c_hash)

            symbol = "@" if commit["is_head"] else "o"
            line_parts = []
            for i, c in enumerate(columns):
                if i == col_idx:
                    line_parts.append(symbol)
                elif c is not None:
                    line_parts.append("|")
                else:
                    line_parts.append(" ")
            graph_art = " ".join(line_parts)

            # Update column occupancy for parent commits
            if parents:
                columns[col_idx] = parents[0]
                for p in parents[1:]:
                    if p not in columns:
                        if None in columns:
                            columns[columns.index(None)] = p
                        else:
                            columns.append(p)
            else:
                columns[col_idx] = None

            while columns and columns[-1] is None:
                columns.pop()

            # Inspect bug tags from subject, body, and feedback files
            bug_tags = self._extract_bug_tags(f"{commit['subject']}\n{commit['body']}")

            # Inspect PR info
            pr_status, pr_number, pr_url = self._extract_pr_info(
                commit["subject"], commit["body"], commit["branches"], commit["tags"]
            )

            # Check stats and feedback-only status
            adds, dels, f_count, is_feedback_only = self._get_commit_diff_summary(c_hash)

            nodes.append(
                CommitNodeModel(
                    commit_hash=c_hash,
                    short_hash=commit["short_hash"],
                    parents=parents,
                    author=commit["author"],
                    email=commit["email"],
                    date=commit["date"],
                    time=extract_time_str(commit["date"]),
                    relative_date=commit["relative_date"],
                    subject=commit["subject"],
                    body=commit["body"],
                    branches=commit["branches"],
                    tags=commit["tags"],
                    is_head=commit["is_head"],
                    is_ancestor_top=commit.get("is_ancestor_top", False),
                    is_merged=commit.get("is_merged", False),
                    is_merged_into_tracking=commit.get("is_merged_into_tracking", False),
                    ancestor_name=commit.get("ancestor_name"),
                    graph_symbol=symbol,
                    graph_art=graph_art,
                    bug_tags=bug_tags,
                    pr_status=pr_status,
                    pr_number=pr_number,
                    pr_url=pr_url,
                    additions=adds,
                    deletions=dels,
                    files_count=f_count,
                    is_feedback_only=is_feedback_only,
                )
            )

        return nodes

    def _extract_bug_tags(self, text: str) -> List[CommitBugTagModel]:
        """Extract bug IDs from commit text and resolve current status via SQLite/Markdown."""
        bug_ids = sorted(list(set(re.findall(r"\b(BUG[_-]\d+)\b", text, re.IGNORECASE))))
        if not bug_ids:
            return []

        tags: List[CommitBugTagModel] = []
        db_map: Dict[str, Dict[str, str]] = {}
        sqlite_path = self.repo_root / "build" / "bugs.sqlite"
        if sqlite_path.exists():
            try:
                conn = sqlite3.connect(str(sqlite_path))
                try:
                    cur = conn.cursor()
                    for bid in bug_ids:
                        norm_id = bid.replace("_", "-").upper()
                        cur.execute(
                            "SELECT id, title, status, severity FROM bugs WHERE id = ? OR id = ?", (norm_id, bid)
                        )
                        row = cur.fetchone()
                        if row:
                            db_map[norm_id] = {
                                "title": str(row[1]),
                                "status": str(row[2]),
                                "severity": str(row[3]),
                            }
                finally:
                    conn.close()
            except Exception:
                pass

        for bid in bug_ids:
            norm_id = bid.replace("_", "-").upper()
            if norm_id in db_map:
                tags.append(
                    CommitBugTagModel(
                        id=norm_id,
                        title=db_map[norm_id]["title"],
                        status=db_map[norm_id]["status"],
                        severity=db_map[norm_id]["severity"],
                    )
                )
            else:
                num = norm_id.replace("BUG-", "").replace("BUG_", "")
                md_path = self.repo_root / "feedback" / f"BUG_{num}.md"
                status = "OPEN"
                title = ""
                if md_path.exists():
                    try:
                        content = md_path.read_text(encoding="utf-8", errors="replace")
                        for line in content.splitlines():
                            if line.startswith("# ") and "BUG-" in line:
                                title = line.split("]", 1)[-1].strip()
                            if line.startswith("- **Status**:"):
                                parts = line.split("`")
                                if len(parts) >= 2:
                                    status = parts[1].strip()
                    except Exception:
                        pass
                tags.append(
                    CommitBugTagModel(
                        id=norm_id,
                        title=title,
                        status=status,
                        severity="LOW",
                    )
                )
        return tags

    def get_repo_web_url(self) -> Optional[str]:
        """Derive web URL (e.g. https://github.com/owner/repo) from git remote origin."""
        try:
            url = run_git_command(["config", "--get", "remote.origin.url"], cwd=self.repo_root).strip()
        except RuntimeError:
            return None
        if not url:
            return None
        if url.startswith("git@"):
            parts = url.split(":", 1)
            if len(parts) == 2:
                host = parts[0].replace("git@", "")
                path = parts[1].removesuffix(".git")
                return f"https://{host}/{path}"
        if url.startswith("http://") or url.startswith("https://"):
            return url.removesuffix(".git")
        return None

    def get_pr_url(self, pr_number: int | str) -> str:
        """Return the web URL for a GitHub Pull Request number."""
        base = self.get_repo_web_url()
        if base:
            return f"{base}/pull/{pr_number}"
        return f"https://github.com/picklethecat1488-hue/hardware/pull/{pr_number}"

    def get_remote_pr_numbers(self) -> Set[int]:
        """Fetch set of valid pull request numbers existing on remote GitHub repository.

        Cached on the instance to avoid repeatedly invoking ls-remote.
        """
        if hasattr(self, "_remote_pr_cache") and self._remote_pr_cache is not None:
            return self._remote_pr_cache

        prs: Set[int] = set()
        web_url = self.get_repo_web_url()
        if web_url:
            try:
                output = run_git_command(["ls-remote", "origin", "refs/pull/*/head"], cwd=self.repo_root)
                for line in output.splitlines():
                    m = re.search(r"refs/pull/(\d+)/head", line)
                    if m:
                        prs.add(int(m.group(1)))
            except RuntimeError:
                pass

        self._remote_pr_cache = prs
        return prs

    def get_branch_url(self, branch_name: str) -> str:
        """Return the GitHub web URL for a branch or PR branch name."""
        base = self.get_repo_web_url() or "https://github.com/picklethecat1488-hue/hardware"
        m = re.search(r"(?:^|/)(?:pr|pull)[/-]?(\d+)\b", branch_name, re.IGNORECASE)
        if m:
            pr_num = int(m.group(1))
            remote_prs = self.get_remote_pr_numbers()
            if not remote_prs or pr_num in remote_prs:
                return f"{base}/pull/{pr_num}"
        cleaned = re.sub(r"^(?:remotes/)?origin/", "", branch_name)
        return f"{base}/tree/{cleaned}"

    def _extract_pr_info(
        self, subject: str, body: str, branches: List[str], tags: List[str]
    ) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """Detect pull request status indicator, PR number, and PR URL.

        Returns:
            Tuple of (pr_status, pr_number, pr_url).
        """
        pr_num: Optional[int] = None

        # 1. Check branches (e.g. origin/pr520, pr/520, remotes/origin/pr123, pr494)
        for b in branches:
            m = re.search(r"(?:^|/)(?:pr|pull)[/-]?(\d+)\b", b, re.IGNORECASE)
            if m:
                pr_num = int(m.group(1))
                break

        # 2. Check tags (e.g. pr/520, pr520)
        if pr_num is None:
            for t in tags:
                m = re.search(r"(?:^|/)(?:pr|pull)[/-]?(\d+)\b", t, re.IGNORECASE)
                if m:
                    pr_num = int(m.group(1))
                    break

        # 3. Check commit subject or body (e.g. "PR #520", "PR 520", "Merge pull request #520")
        if pr_num is None:
            combined = f"{subject}\n{body}"
            m = re.search(r"\b(?:PR|pull\s*request)\s*#?(\d+)\b", combined, re.IGNORECASE)
            if m:
                pr_num = int(m.group(1))

        if pr_num is not None:
            remote_prs = self.get_remote_pr_numbers()
            if remote_prs and pr_num not in remote_prs:
                pr_status = f"Local PR #{pr_num}"
                pr_url = None
            else:
                pr_status = f"PR #{pr_num}"
                pr_url = self.get_pr_url(pr_num)
            return pr_status, pr_num, pr_url

        # Check for any other PR branch marker without explicit number
        for b in branches:
            if b.startswith("pr/") or "pull/" in b:
                return b, None, None

        return None, None, None

    def get_next_pr_number(self) -> int:
        """Determine next available PR number based on existing local and remote PR branches and tags."""
        existing: List[int] = []
        try:
            output = run_git_command(["branch", "-a"], cwd=self.repo_root)
            for line in output.splitlines():
                m = re.search(r"(?:^|/)(?:pr|pull)[/-]?(\d+)\b", line.strip(), re.IGNORECASE)
                if m:
                    existing.append(int(m.group(1)))
            tag_out = run_git_command(["tag", "-l"], cwd=self.repo_root)
            for line in tag_out.splitlines():
                m = re.search(r"(?:^|/)(?:pr|pull)[/-]?(\d+)\b", line.strip(), re.IGNORECASE)
                if m:
                    existing.append(int(m.group(1)))
        except RuntimeError:
            pass
        return max(existing, default=534) + 1

    def create_prs_for_commits(self, commit_hashes: List[str]) -> List[Dict[str, Any]]:
        """Create a PR for each selected commit and preserve commit ancestors information.

        Validates that none of the selected commits already have an associated PR.
        Topologically sorts commits so ancestors are created before descendants,
        setting each commit's PR base to its parent's PR branch (or repository default).
        """
        if not commit_hashes:
            raise ValueError("No commits provided for PR creation")

        # 1. Fetch current smartlog / commit info to validate existing PR associations
        nodes = self.get_smartlog_dag(limit=100)
        node_map = {n.commit_hash: n for n in nodes}

        curr_branch = self.get_current_branch() or "main"

        # Validate that no selected commit is already merged or already has an associated PR
        for c in commit_hashes:
            node = node_map.get(c)
            if node and (node.is_merged_into_tracking or node.is_merged):
                raise ValueError(f"Commit {c[:8]} is already merged into the tracking branch ({curr_branch})")
            if node and node.pr_number:
                raise ValueError(f"Commit {c[:8]} already has an associated PR (#{node.pr_number})")

            try:
                branches_out = run_git_command(["branch", "-a", "--points-at", c], cwd=self.repo_root)
                for b in branches_out.splitlines():
                    clean_b = b.replace("*", "").strip()
                    m = re.search(r"(?:^|/)(?:pr|pull)[/-]?(\d+)\b", clean_b, re.IGNORECASE)
                    if m:
                        raise ValueError(f"Commit {c[:8]} already has an associated PR (#{m.group(1)})")
            except RuntimeError:
                pass

        # 2. Sort selected commits in topological order (ancestor before descendant)
        try:
            topo_order = run_git_command(
                ["rev-list", "--topo-order", "--reverse"] + commit_hashes,
                cwd=self.repo_root,
            ).splitlines()
            sorted_commits = [c for c in topo_order if c in commit_hashes]
        except RuntimeError:
            sorted_commits = list(commit_hashes)

        for c in commit_hashes:
            if c not in sorted_commits:
                sorted_commits.append(c)

        created_prs: List[Dict[str, Any]] = []
        commit_to_pr_branch: Dict[str, str] = {}
        curr_branch = self.get_current_branch() or "main"

        for c in sorted_commits:
            try:
                parents = run_git_command(["log", "-1", "--format=%P", c], cwd=self.repo_root).split()
            except RuntimeError:
                parents = []

            base_branch = curr_branch
            if parents:
                parent_sha = parents[0]
                if parent_sha in commit_to_pr_branch:
                    base_branch = commit_to_pr_branch[parent_sha]
                else:
                    parent_node = node_map.get(parent_sha)
                    if parent_node and parent_node.pr_number:
                        base_branch = f"pr{parent_node.pr_number}"

            pr_num = self.get_next_pr_number()
            branch_name = f"pr{pr_num}"

            run_git_command(["branch", branch_name, c], cwd=self.repo_root)
            commit_to_pr_branch[c] = branch_name

            pr_url = self.get_pr_url(pr_num)
            created_prs.append(
                {
                    "commit": c,
                    "pr_number": pr_num,
                    "branch": branch_name,
                    "base_branch": base_branch,
                    "pr_url": pr_url,
                }
            )

        return created_prs

    def unlink_prs_for_commits(self, commit_hashes: List[str]) -> List[Dict[str, Any]]:
        """Unlink PRs from selected commits by removing their associated PR branches.

        Validates that selected commits actually have associated PRs.
        """
        if not commit_hashes:
            raise ValueError("No commits provided to unlink PR")

        unlinked: List[Dict[str, Any]] = []

        for c in commit_hashes:
            try:
                branches_out = run_git_command(["branch", "--points-at", c], cwd=self.repo_root)
            except RuntimeError:
                branches_out = ""

            pr_branches = []
            for b in branches_out.splitlines():
                clean_b = b.replace("*", "").strip()
                if re.match(r"^pr\d+$", clean_b, re.IGNORECASE) or re.match(r"^pr/\d+$", clean_b, re.IGNORECASE):
                    pr_branches.append(clean_b)

            if not pr_branches:
                try:
                    tags_out = run_git_command(["tag", "--points-at", c], cwd=self.repo_root)
                except RuntimeError:
                    tags_out = ""
                for t in tags_out.splitlines():
                    clean_t = t.strip()
                    if re.match(r"^pr\d+$", clean_t, re.IGNORECASE) or re.match(r"^pr/\d+$", clean_t, re.IGNORECASE):
                        pr_branches.append(clean_t)

            if not pr_branches:
                raise ValueError(f"Commit {c[:8]} does not have an associated PR to unlink")

            for br in pr_branches:
                try:
                    run_git_command(["branch", "-D", br], cwd=self.repo_root)
                except RuntimeError:
                    pass
                try:
                    run_git_command(["tag", "-d", br], cwd=self.repo_root)
                except RuntimeError:
                    pass

                m = re.search(r"\d+", br)
                pr_num = int(m.group(0)) if m else None
                unlinked.append({"commit": c, "unlinked_branch": br, "pr_number": pr_num})

        return unlinked

    def _get_commit_diff_summary(self, commit_hash: str) -> Tuple[int, int, int, bool]:
        """Compute additions, deletions, file count, and whether commit strictly touches feedback."""
        cmd = ["diff-tree", "--no-commit-id", "--numstat", "-r", commit_hash]
        try:
            output = run_git_command(cmd, cwd=self.repo_root)
        except RuntimeError:
            return 0, 0, 0, False

        additions = 0
        deletions = 0
        file_count = 0
        non_feedback_count = 0

        for line in output.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                file_path = cols[2].strip()
                file_count += 1
                clean = file_path.replace("\\", "/").strip().lstrip("./")
                if not (clean.startswith("feedback/") or clean.startswith("build/bugs") or clean == "TODO.md"):
                    non_feedback_count += 1
                if cols[0].isdigit():
                    additions += int(cols[0])
                if cols[1].isdigit():
                    deletions += int(cols[1])

        is_feedback_only = file_count > 0 and non_feedback_count == 0
        return additions, deletions, file_count, is_feedback_only

    def has_working_tree_changes(self) -> bool:
        """Check whether repository contains any uncommitted or untracked changes."""
        status_output = run_git_command(["status", "--porcelain", "--untracked-files=all"], cwd=self.repo_root).strip()
        if not status_output:
            return False
        for line in status_output.splitlines():
            if len(line) >= 4:
                file_path = line[3:].strip()
                if " -> " in file_path:
                    file_path = file_path.split(" -> ")[1].strip()
                if not self.is_file_ignored(file_path):
                    return True
        return False

    def check_lfs_paths(self, file_paths: List[str]) -> Set[str]:
        """Return set of file paths that are tracked by Git LFS."""
        lfs_set: Set[str] = set()
        if not file_paths:
            return lfs_set
        try:
            attr_out = run_git_command(["check-attr", "filter", "--"] + file_paths, cwd=self.repo_root)
            for line in attr_out.splitlines():
                if ": filter: lfs" in line:
                    p = line.split(": filter: lfs")[0].strip()
                    lfs_set.add(p)
        except RuntimeError:
            pass
        for fp in file_paths:
            clean = fp.replace("\\", "/").strip().lstrip("./")
            if clean.startswith("attachments/"):
                lfs_set.add(fp)
        return lfs_set

    def get_working_tree_files(self) -> List[WorkingTreeFileModel]:
        """List all modified, staged, untracked, and conflicted files in working directory."""
        status_out = run_git_command(["status", "--porcelain=v1", "--untracked-files=all"], cwd=self.repo_root)
        staged_numstat = run_git_command(["diff", "--cached", "--numstat"], cwd=self.repo_root)
        unstaged_numstat = run_git_command(["diff", "--numstat"], cwd=self.repo_root)

        stats_map: Dict[str, Tuple[int, int]] = {}
        for line in f"{staged_numstat}\n{unstaged_numstat}".splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                p = cols[2].strip()
                adds = int(cols[0]) if cols[0].isdigit() else 0
                dels = int(cols[1]) if cols[1].isdigit() else 0
                prev_adds, prev_dels = stats_map.get(p, (0, 0))
                stats_map[p] = (prev_adds + adds, prev_dels + dels)

        files: List[WorkingTreeFileModel] = []
        for line in status_out.splitlines():
            if len(line) < 4:
                continue
            idx_status = line[0]
            work_status = line[1]
            file_path = line[3:].strip()
            if " -> " in file_path:
                file_path = file_path.split(" -> ")[1].strip()

            clean_path = file_path.replace("\\", "/").strip().lstrip("./")
            is_feedback = clean_path.startswith("feedback/") or clean_path in IGNORED_REVIEW_FILES
            is_untracked = idx_status == "?" and work_status == "?"
            is_conflicted = (idx_status, work_status) in [
                ("U", "U"),
                ("A", "A"),
                ("D", "D"),
                ("U", "D"),
                ("D", "U"),
                ("A", "U"),
                ("U", "A"),
            ]
            is_staged = idx_status in ["M", "A", "D", "R", "C"]

            adds, dels = stats_map.get(file_path, (0, 0))
            if is_untracked and adds == 0 and dels == 0:
                full_path = self.repo_root / file_path
                if full_path.is_file():
                    try:
                        adds = len(full_path.read_text(encoding="utf-8", errors="replace").splitlines())
                    except OSError:
                        pass

            files.append(
                WorkingTreeFileModel(
                    path=file_path,
                    status=(idx_status + work_status).strip(),
                    index_status=idx_status,
                    worktree_status=work_status,
                    is_staged=is_staged,
                    is_untracked=is_untracked,
                    is_conflicted=is_conflicted,
                    is_feedback=is_feedback,
                    is_lfs=False,
                    additions=adds,
                    deletions=dels,
                )
            )

        lfs_set = self.check_lfs_paths([f.path for f in files])
        for f in files:
            clean = f.path.replace("\\", "/").strip().lstrip("./")
            if f.path in lfs_set or clean in lfs_set or clean.startswith("attachments/"):
                f.is_lfs = True

        return files

    def _get_working_tree_info(self) -> Optional[CommitInfoModel]:
        """Check if working tree has unstaged, staged, or untracked modifications."""
        status_output = run_git_command(["status", "--porcelain", "--untracked-files=all"], cwd=self.repo_root).strip()
        if not status_output:
            return None

        diff_stat = run_git_command(["diff", "HEAD", "--numstat"], cwd=self.repo_root).strip()
        additions = 0
        deletions = 0
        file_count = 0
        ignored_files: List[str] = []
        for line in diff_stat.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                file_path = cols[2].strip()
                if self.is_file_ignored(file_path):
                    if Path(file_path).name not in ignored_files:
                        ignored_files.append(Path(file_path).name)
                    continue
                file_count += 1
                if cols[0].isdigit():
                    additions += int(cols[0])
                if cols[1].isdigit():
                    deletions += int(cols[1])

        status_lines = []
        for line in status_output.splitlines():
            if len(line) >= 4:
                file_path = line[3:].strip()
                if " -> " in file_path:
                    file_path = file_path.split(" -> ")[1].strip()
                if self.is_file_ignored(file_path):
                    if Path(file_path).name not in ignored_files:
                        ignored_files.append(Path(file_path).name)
                    continue
                status_lines.append(line)
                if line.startswith("?? "):
                    file_count += 1
                    full_path = self.repo_root / file_path
                    if full_path.is_file():
                        try:
                            additions += len(full_path.read_text(encoding="utf-8", errors="replace").splitlines())
                        except OSError:
                            pass

        if file_count == 0 and not status_lines and not ignored_files:
            return None

        now = datetime.now(timezone.utc)
        return CommitInfoModel(
            commit_hash="working",
            short_hash="WORKING",
            author="Local Working Tree",
            email="local@workspace",
            date=f"Now ({now.strftime('%Y-%m-%d')})",
            time=now.strftime("%H:%M:%S"),
            subject=f"Uncommitted Changes ({file_count} modified files)",
            body="\n".join(status_lines),
            additions=additions,
            deletions=deletions,
            files_count=file_count,
            ignored_files_count=len(ignored_files),
            ignored_files=ignored_files,
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

            additions, deletions, file_count, ignored_files = self._get_commit_stat_summary(c_hash)
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
                ignored_files_count=len(ignored_files),
                ignored_files=ignored_files,
            )
        return None

    def search_code(self, query: str, commit: str = "working", max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for symbol, identifier, or text occurrences across files in revision or repository."""
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
                        file_path = parts[0].strip()
                        if self.is_file_ignored(file_path):
                            continue
                        results.append(
                            {
                                "file_path": file_path,
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
                        file_path = parts[1].strip()
                        if self.is_file_ignored(file_path):
                            continue
                        results.append(
                            {
                                "file_path": file_path,
                                "line_number": int(parts[2]),
                                "line_content": parts[3].strip(),
                            }
                        )
            except RuntimeError:
                pass

        return results

    def _get_commit_stat_summary(self, commit_hash: str) -> Tuple[int, int, int, List[str]]:
        """Calculate additions, deletions, file count, and ignored files list for a commit."""
        cmd = ["diff-tree", "--no-commit-id", "--numstat", "-r", commit_hash]
        try:
            output = run_git_command(cmd, cwd=self.repo_root)
        except RuntimeError:
            return 0, 0, 0, []

        additions = 0
        deletions = 0
        file_count = 0
        ignored_files: List[str] = []
        for line in output.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                file_path = cols[2].strip()
                if self.is_file_ignored(file_path):
                    name = Path(file_path).name
                    if name not in ignored_files:
                        ignored_files.append(name)
                    continue
                file_count += 1
                if cols[0].isdigit():
                    additions += int(cols[0])
                if cols[1].isdigit():
                    deletions += int(cols[1])
        return additions, deletions, file_count, ignored_files

    def get_changed_files(self, commit: str, include_feedback: bool = False) -> List[Dict[str, Any]]:
        """List changed files with status and stats for a revision."""
        if commit == "working":
            return self._get_working_tree_files_simple(include_feedback=include_feedback)

        cmd_status = ["diff-tree", "--no-commit-id", "--name-status", "-r", commit]
        try:
            status_out = run_git_command(cmd_status, cwd=self.repo_root)
        except RuntimeError:
            return []

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
                if not include_feedback and self.is_file_ignored(path):
                    continue
                adds = int(cols[0]) if cols[0].isdigit() else 0
                dels = int(cols[1]) if cols[1].isdigit() else 0
                stats_map[path] = (adds, dels)

        files: List[Dict[str, Any]] = []
        for line in status_out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                status_code = parts[0].strip()
                file_path = parts[-1].strip()
                clean = file_path.replace("\\", "/").strip().lstrip("./")
                is_feedback = clean.startswith("feedback/") or clean in IGNORED_REVIEW_FILES
                if not include_feedback and self.is_file_ignored(file_path):
                    continue
                adds, dels = stats_map.get(file_path, (0, 0))
                files.append(
                    {
                        "path": file_path,
                        "status": status_code,
                        "additions": str(adds),
                        "deletions": str(dels),
                        "is_feedback": is_feedback,
                        "is_lfs": False,
                    }
                )
        lfs_set = self.check_lfs_paths([f["path"] for f in files])
        for f in files:
            clean = f["path"].replace("\\", "/").strip().lstrip("./")
            f["is_lfs"] = f["path"] in lfs_set or clean in lfs_set or clean.startswith("attachments/")
        return files

    def _get_working_tree_files_simple(self, include_feedback: bool = False) -> List[Dict[str, Any]]:
        """List modified and untracked files in local working directory for code review or diff view."""
        status_out = run_git_command(["status", "--porcelain", "--untracked-files=all"], cwd=self.repo_root)
        numstat_out = run_git_command(["diff", "HEAD", "--numstat"], cwd=self.repo_root)

        stats_map: Dict[str, Tuple[int, int]] = {}
        for line in numstat_out.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                path = cols[2].strip()
                if not include_feedback and self.is_file_ignored(path):
                    continue
                adds = int(cols[0]) if cols[0].isdigit() else 0
                dels = int(cols[1]) if cols[1].isdigit() else 0
                stats_map[path] = (adds, dels)

        files: List[Dict[str, Any]] = []
        for line in status_out.splitlines():
            if len(line) < 4:
                continue
            status_code = line[:2].strip()
            file_path = line[3:].strip()
            if " -> " in file_path:
                file_path = file_path.split(" -> ")[1].strip()
            clean = file_path.replace("\\", "/").strip().lstrip("./")
            is_feedback = clean.startswith("feedback/") or clean in IGNORED_REVIEW_FILES
            if not include_feedback and self.is_file_ignored(file_path):
                continue
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
                    "is_feedback": is_feedback,
                    "is_lfs": False,
                }
            )
        lfs_set = self.check_lfs_paths([f["path"] for f in files])
        for f in files:
            clean = f["path"].replace("\\", "/").strip().lstrip("./")
            f["is_lfs"] = f["path"] in lfs_set or clean in lfs_set or clean.startswith("attachments/")
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

    def get_file_bytes(self, commit: str, file_path: str, parent: bool = False) -> bytes:
        """Retrieve raw byte content of a file at a commit or parent."""
        if commit == "working":
            if parent:
                try:
                    res = subprocess.run(
                        ["git", "show", f"HEAD:{file_path}"],
                        cwd=self.repo_root,
                        capture_output=True,
                        check=True,
                    )
                    return res.stdout
                except (subprocess.CalledProcessError, FileNotFoundError):
                    return b""
            full_path = self.repo_root / file_path
            if full_path.exists() and full_path.is_file():
                try:
                    return full_path.read_bytes()
                except OSError:
                    return b""
            return b""

        rev_spec = f"{commit}^:{file_path}" if parent else f"{commit}:{file_path}"
        try:
            res = subprocess.run(
                ["git", "show", rev_spec],
                cwd=self.repo_root,
                capture_output=True,
                check=True,
            )
            return res.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return b""

    def get_file_diff(self, commit: str, file_path: str, staged_only: bool = False) -> FileDiffModel:
        """Construct comprehensive diff model including hunks and side-by-side rows."""
        binary_exts = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".ico",
            ".bmp",
            ".tiff",
            ".pdf",
            ".stl",
            ".step",
            ".stp",
            ".obj",
            ".glb",
            ".gltf",
            ".zip",
            ".tar",
            ".gz",
            ".bz2",
            ".7z",
            ".bin",
            ".dat",
            ".sqlite",
            ".db",
            ".so",
            ".dylib",
            ".dll",
        }
        is_binary = Path(file_path).suffix.lower() in binary_exts

        clean_path = file_path.replace("\\", "/").strip().lstrip("./")
        lfs_set = self.check_lfs_paths([file_path, clean_path])
        is_lfs = (
            file_path in lfs_set
            or clean_path in lfs_set
            or clean_path.startswith("attachments/")
            or clean_path.startswith("build/attachments/")
            or clean_path.startswith("feedback/attachments/")
        )

        old_content = ""
        new_content = ""

        if is_binary:
            return FileDiffModel(
                file_path=file_path,
                old_path=file_path,
                new_path=file_path,
                status="M",
                is_binary=True,
                is_lfs=is_lfs,
                additions=0,
                deletions=0,
                hunks=[],
                side_by_side=[],
                full_content="Binary file differ.",
                old_content="",
                new_content="",
                raw_diff=f"Binary files a/{file_path} and b/{file_path} differ",
            )

        if commit == "working":
            old_content = self.get_file_content("working", file_path, parent=True)
            new_content = self.get_file_content("working", file_path, parent=False)
            if staged_only:
                try:
                    raw_diff = run_git_command(["diff", "--cached", "--", file_path], cwd=self.repo_root)
                except RuntimeError:
                    raw_diff = ""
            else:
                try:
                    raw_diff = run_git_command(["diff", "HEAD", "--", file_path], cwd=self.repo_root)
                except RuntimeError:
                    raw_diff = ""
            if not raw_diff and not old_content and new_content:
                lines = new_content.splitlines()
                raw_diff = f"--- /dev/null\n+++ b/{file_path}\n@@ -0,0 +1,{len(lines)} @@\n" + "\n".join(
                    f"+{l}" for l in lines
                )
        else:
            old_content = self.get_file_content(commit, file_path, parent=True)
            new_content = self.get_file_content(commit, file_path, parent=False)
            try:
                raw_diff = run_git_command(
                    ["diff-tree", "-p", "--no-commit-id", commit, "--", file_path], cwd=self.repo_root
                )
            except RuntimeError:
                raw_diff = ""

        hunks = self._parse_diff_hunks(raw_diff)
        side_by_side = self._generate_side_by_side(old_content, new_content)

        additions = sum(1 for line in raw_diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in raw_diff.splitlines() if line.startswith("-") and not line.startswith("---"))

        status = "M"
        if not old_content and new_content:
            status = "A"
        elif old_content and not new_content:
            status = "D"

        return FileDiffModel(
            file_path=file_path,
            old_path=file_path,
            new_path=file_path,
            status=status,
            is_binary=False,
            is_lfs=is_lfs,
            additions=additions,
            deletions=deletions,
            hunks=hunks,
            side_by_side=side_by_side,
            full_content=new_content,
            old_content=old_content,
            new_content=new_content,
            raw_diff=raw_diff,
        )

    def _parse_diff_hunks(self, raw_diff: str) -> List[DiffHunk]:
        """Parse raw unified diff text into structured DiffHunk instances."""
        hunks: List[DiffHunk] = []
        if not raw_diff:
            return hunks

        hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)")
        current_hunk: Optional[DiffHunk] = None
        old_no = 0
        new_no = 0

        def _trim(s: str) -> str:
            if len(s) > MAX_DIFF_LINE_LENGTH:
                return s[:MAX_DIFF_LINE_LENGTH] + "…"
            return s

        for line in raw_diff.splitlines():
            m = hunk_header_re.match(line)
            if m:
                if current_hunk:
                    hunks.append(current_hunk)
                old_start = int(m.group(1))
                old_count = int(m.group(2)) if m.group(2) else 1
                new_start = int(m.group(3))
                new_count = int(m.group(4)) if m.group(4) else 1

                current_hunk = DiffHunk(
                    header=line,
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=[],
                )
                old_no = old_start
                new_no = new_start
            elif current_hunk:
                if line.startswith("+"):
                    content = _trim(line[1:])
                    current_hunk.lines.append(
                        DiffLine(
                            type=DiffLineType.ADD,
                            old_line_no=None,
                            new_line_no=new_no,
                            content=content,
                        )
                    )
                    new_no += 1
                elif line.startswith("-"):
                    content = _trim(line[1:])
                    current_hunk.lines.append(
                        DiffLine(
                            type=DiffLineType.DELETE,
                            old_line_no=old_no,
                            new_line_no=None,
                            content=content,
                        )
                    )
                    old_no += 1
                elif line.startswith(" ") or not line:
                    content = _trim(line[1:]) if line.startswith(" ") else ""
                    current_hunk.lines.append(
                        DiffLine(
                            type=DiffLineType.CONTEXT,
                            old_line_no=old_no,
                            new_line_no=new_no,
                            content=content,
                        )
                    )
                    old_no += 1
                    new_no += 1

        if current_hunk:
            hunks.append(current_hunk)

        return hunks

    def _generate_side_by_side(self, old_text: str, new_text: str) -> List[DiffSideBySideRow]:
        """Align old and new text into paired side-by-side rows using difflib SequenceMatcher."""
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        rows: List[DiffSideBySideRow] = []

        def _trim(s: str) -> str:
            if len(s) > MAX_DIFF_LINE_LENGTH:
                return s[:MAX_DIFF_LINE_LENGTH] + "…"
            return s

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            match tag:
                case "equal":
                    for offset in range(i2 - i1):
                        rows.append(
                            DiffSideBySideRow(
                                old_no=i1 + offset + 1,
                                old_text=_trim(old_lines[i1 + offset]),
                                new_no=j1 + offset + 1,
                                new_text=_trim(new_lines[j1 + offset]),
                                row_type="equal",
                            )
                        )
                case "replace":
                    count = max(i2 - i1, j2 - j1)
                    for offset in range(count):
                        has_old = offset < (i2 - i1)
                        has_new = offset < (j2 - j1)
                        rows.append(
                            DiffSideBySideRow(
                                old_no=i1 + offset + 1 if has_old else None,
                                old_text=_trim(old_lines[i1 + offset]) if has_old else "",
                                new_no=j1 + offset + 1 if has_new else None,
                                new_text=_trim(new_lines[j1 + offset]) if has_new else "",
                                row_type="replace",
                            )
                        )
                case "delete":
                    for offset in range(i2 - i1):
                        rows.append(
                            DiffSideBySideRow(
                                old_no=i1 + offset + 1,
                                old_text=_trim(old_lines[i1 + offset]),
                                new_no=None,
                                new_text="",
                                row_type="delete",
                            )
                        )
                case "insert":
                    for offset in range(j2 - j1):
                        rows.append(
                            DiffSideBySideRow(
                                old_no=None,
                                old_text="",
                                new_no=j1 + offset + 1,
                                new_text=_trim(new_lines[j1 + offset]),
                                row_type="insert",
                            )
                        )

        return rows

    # Working tree staging, discarding, and committing operations

    def stage_file(self, file_path: str) -> None:
        """Stage file modifications or untracked file into git index."""
        run_git_command(["add", "--", file_path], cwd=self.repo_root)

    def unstage_file(self, file_path: str) -> None:
        """Remove file changes from git index while preserving working tree changes."""
        run_git_command(["reset", "HEAD", "--", file_path], cwd=self.repo_root)

    def get_head_commit_message(self) -> str:
        """Retrieve full commit message (subject and body) of HEAD commit.

        Returns:
            Commit message string, or empty string if no HEAD commit.
        """
        try:
            return run_git_command(["log", "-1", "--format=%B"], cwd=self.repo_root).strip()
        except RuntimeError:
            return ""

    def discard_file(self, file_path: str) -> None:
        """Discard working tree changes or remove untracked/added file.

        Handles untracked files, staged additions, deletions, and tracked modifications.

        Args:
            file_path: Relative repository path of file to discard.
        """
        full_path = self.repo_root / file_path
        status_out = run_git_command(["status", "--porcelain", "--", file_path], cwd=self.repo_root).strip()

        if not status_out:
            return

        # Untracked file
        if status_out.startswith("??"):
            if full_path.is_file():
                full_path.unlink()
            elif full_path.is_dir():
                shutil.rmtree(full_path)
            return

        # Staged new file (A)
        if status_out.startswith("A"):
            try:
                run_git_command(["reset", "HEAD", "--", file_path], cwd=self.repo_root)
            except RuntimeError:
                pass
            if full_path.is_file():
                full_path.unlink()
            elif full_path.is_dir():
                shutil.rmtree(full_path)
            return

        # Tracked modification or deletion
        try:
            run_git_command(["reset", "HEAD", "--", file_path], cwd=self.repo_root)
        except RuntimeError:
            pass
        try:
            run_git_command(["checkout", "HEAD", "--", file_path], cwd=self.repo_root)
        except RuntimeError:
            try:
                run_git_command(["checkout", "--", file_path], cwd=self.repo_root)
            except RuntimeError:
                pass

    def discard_files(self, file_paths: List[str]) -> None:
        """Discard uncommitted changes across multiple files.

        Args:
            file_paths: List of relative repository paths to discard.
        """
        for fp in file_paths:
            self.discard_file(fp)

    def commit_staged(self, message: str) -> str:
        """Commit currently staged changes with specified message.

        Args:
            message: Commit message string.

        Returns:
            New commit hash string.
        """
        return self.commit_files(message=message)

    def _ensure_lfs_tracking_for_attachments(self, file_paths: Optional[List[str]] = None) -> bool:
        """Ensure git LFS tracking is configured for attachments/ and stage .gitattributes if needed."""
        has_attachment = False
        if file_paths is not None:
            has_attachment = any(
                p.replace("\\", "/").strip().lstrip("./").startswith("attachments/") for p in file_paths
            )
        else:
            try:
                status_out = run_git_command(["status", "--porcelain"], cwd=self.repo_root)
                has_attachment = any("attachments/" in line for line in status_out.splitlines())
            except RuntimeError:
                has_attachment = False

        if not has_attachment:
            return False

        gitattributes_path = self.repo_root / ".gitattributes"
        content = gitattributes_path.read_text(encoding="utf-8") if gitattributes_path.exists() else ""
        lfs_patterns = [
            "attachments/* filter=lfs diff=lfs merge=lfs -text",
            "attachments/** filter=lfs diff=lfs merge=lfs -text",
        ]
        new_lines = [pat for pat in lfs_patterns if pat not in content]
        if new_lines:
            if content and not content.endswith("\n"):
                content += "\n"
            content += "\n".join(new_lines) + "\n"
            gitattributes_path.write_text(content, encoding="utf-8")

        # Run git lfs track if supported
        try:
            run_git_command(["lfs", "track", "attachments/*", "attachments/**"], cwd=self.repo_root)
        except Exception:
            pass

        # Stage .gitattributes
        try:
            run_git_command(["add", "--", ".gitattributes"], cwd=self.repo_root)
        except RuntimeError:
            pass

        return True

    def commit_files(
        self,
        message: str,
        file_paths: Optional[List[str]] = None,
        amend: bool = False,
    ) -> str:
        """Commit selected files (or currently staged files) with message, optionally amending HEAD.

        Args:
            message: Commit message string.
            file_paths: Specific files to commit. If provided, stages only these files.
            amend: If True, amends HEAD commit.

        Returns:
            New commit hash string.
        """
        if not message.strip():
            raise ValueError("Commit message cannot be empty.")

        if file_paths is not None:
            if not file_paths and not amend:
                raise ValueError("No files selected to commit.")
            # Reset index to HEAD so only explicitly selected files are staged
            try:
                run_git_command(["reset"], cwd=self.repo_root)
            except RuntimeError:
                pass
            self._ensure_lfs_tracking_for_attachments(file_paths)
            for fp in file_paths:
                run_git_command(["add", "--", fp], cwd=self.repo_root)
        else:
            self._ensure_lfs_tracking_for_attachments(None)

        cmd = ["commit"]
        if amend:
            cmd.append("--amend")
        cmd.extend(["-m", message])
        run_git_command(cmd, cwd=self.repo_root)
        return self.get_head_commit()

    # Commit manipulation: split and combine

    def split_commit(self, commit_hash: str) -> Dict[str, Any]:
        """Split a commit by soft-resetting it so its changes return to the working tree.

        Args:
            commit_hash: Commit hash to split.

        Returns:
            Dictionary with status and message.
        """
        head = self.get_head_commit()
        if commit_hash in [head, "HEAD"] or head.startswith(commit_hash):
            run_git_command(["reset", "HEAD~1"], cwd=self.repo_root)
            return {
                "status": "ok",
                "message": "Commit reset to working tree. You can now selectively stage and commit parts.",
            }
        # If not HEAD, create branch or perform mixed reset
        run_git_command(["reset", "--mixed", f"{commit_hash}~1"], cwd=self.repo_root)
        return {
            "status": "ok",
            "message": f"Reset to parent of {commit_hash[:8]}. Changes are now in working tree.",
        }

    def combine_commits(self, commit_hashes: List[str], message: str) -> str:
        """Combine/squash contiguous commits starting from HEAD into a single commit.

        Args:
            commit_hashes: List of commit hashes to combine (must include HEAD and be contiguous).
            message: Combined commit message.

        Returns:
            New combined commit hash.
        """
        if not commit_hashes:
            raise ValueError("No commits specified to combine.")

        count = len(commit_hashes)
        run_git_command(["reset", "--soft", f"HEAD~{count}"], cwd=self.repo_root)
        run_git_command(["commit", "-m", message], cwd=self.repo_root)
        return self.get_head_commit()

    # Merge conflict inspection and resolution

    def get_merge_conflicts(self) -> List[MergeConflictFileModel]:
        """Detect and list unmerged conflicted files in working directory."""
        status_out = run_git_command(["status", "--porcelain=v1"], cwd=self.repo_root)
        conflicts: List[MergeConflictFileModel] = []

        unmerged_codes = {"UU", "AA", "UD", "DU", "DD", "AU", "UA"}
        for line in status_out.splitlines():
            if len(line) < 4:
                continue
            code = line[:2]
            file_path = line[3:].strip()
            if code in unmerged_codes:
                # Count conflict markers
                full_path = self.repo_root / file_path
                marker_count = 0
                if full_path.is_file():
                    try:
                        content = full_path.read_text(encoding="utf-8", errors="replace")
                        marker_count = len(re.findall(r"^<<<<<<< ", content, re.MULTILINE))
                    except OSError:
                        pass
                conflicts.append(
                    MergeConflictFileModel(
                        path=file_path,
                        conflict_type=code,
                        conflict_markers_count=marker_count,
                    )
                )

        return conflicts

    def resolve_conflict(self, file_path: str, resolution: str) -> Dict[str, Any]:
        """Resolve a conflicted file using ours, theirs, or marking as resolved.

        Args:
            file_path: Relative path to conflicted file.
            resolution: Strategy: 'ours', 'theirs', or 'mark_resolved'.

        Returns:
            Dictionary with result status.
        """
        match resolution:
            case "ours":
                run_git_command(["checkout", "--ours", "--", file_path], cwd=self.repo_root)
                run_git_command(["add", "--", file_path], cwd=self.repo_root)
            case "theirs":
                run_git_command(["checkout", "--theirs", "--", file_path], cwd=self.repo_root)
                run_git_command(["add", "--", file_path], cwd=self.repo_root)
            case "mark_resolved":
                run_git_command(["add", "--", file_path], cwd=self.repo_root)
            case _:
                raise ValueError(f"Unknown conflict resolution strategy '{resolution}'.")

        return {"status": "ok", "file": file_path, "resolution": resolution}
