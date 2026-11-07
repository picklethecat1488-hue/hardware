"""Detached branch storage engine for repository bug tracking.

Decouples the bug database and markdown reviews from code feature branches
by committing directly to a detached git reference (refs/heads/bugs) via headless
git plumbing without modifying the active working tree, index, or HEAD.
"""

from __future__ import annotations

from collections.abc import Collection
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Dict, List, Optional
import zlib

from model.bug_report import BugDatabaseModel
from provider.bug_report.markdown_exporter import MarkdownBugExporter
from provider.bug_report.sqlite_store import SQLiteBugStore
from provider.sanitizer import elide_personal_info

DEFAULT_BRANCH_NAME: str = "bugs"
FILE_MODE_STANDARD: str = "100644"


class DetachedBranchBugStore:
    """Manages bug tracking records stored on a dedicated, detached Git branch.

    Uses Git plumbing commands (hash-object, update-index, write-tree, commit-tree,
    update-ref) with an isolated temporary index file to read, write, and synchronize
    bug records completely out-of-tree without dirtying the user's working directory.
    """

    def __init__(self, repo_root: Path, branch_name: str = DEFAULT_BRANCH_NAME) -> None:
        """Initialize store for the specified repository and branch name.

        Args:
            repo_root: Root path of git repository.
            branch_name: Name of detached bug branch (defaults to 'bugs').
        """
        self.repo_root = Path(repo_root).resolve()
        self.branch_name = branch_name
        self.ref_name = f"refs/heads/{branch_name}"
        self.remote_ref_name = f"refs/remotes/origin/{branch_name}"
        self.exporter = MarkdownBugExporter(self.repo_root)

    def _hash_object(self, data: bytes, rel_path: Optional[str] = None) -> str:
        """Create a git blob object directly in the git object database with optional path filtering.

        Args:
            data: Raw byte content to hash and store.
            rel_path: Optional relative path to apply git attributes and filter processes (e.g. Git LFS).

        Returns:
            The SHA-1 object hash string.
        """
        cmd = ["git", "hash-object", "-w", "--stdin"]
        if rel_path:
            cmd.append(f"--path={rel_path}")
        proc = subprocess.run(
            cmd,
            input=data,
            cwd=str(self.repo_root),
            capture_output=True,
            check=True,
            text=True,
        )
        return proc.stdout.strip()

    def _hash_file(self, file_path: Path, rel_path: str) -> str:
        """Hash a file on disk using git hash-object with path filtering (e.g. Git LFS).

        Args:
            file_path: Absolute or relative Path to file on disk.
            rel_path: Relative path within git repository used for filter evaluation.

        Returns:
            The SHA-1 object hash string.
        """
        proc = subprocess.run(
            ["git", "hash-object", "-w", f"--path={rel_path}", str(file_path)],
            cwd=str(self.repo_root),
            capture_output=True,
            check=True,
            text=True,
        )
        return proc.stdout.strip()

    def _git_blob_sha(self, data: bytes) -> str:
        """Calculate Git blob SHA-1 hash for bytes in memory."""
        return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()

    def _ensure_blob_written(self, data: bytes, sha: str, objects_dir: Optional[Path] = None) -> None:
        """Write git blob directly to objects dir if missing, falling back to git hash-object."""
        if objects_dir:
            obj_dir = objects_dir / sha[:2]
            obj_file = obj_dir / sha[2:]
            if obj_file.exists():
                return
            try:
                obj_dir.mkdir(parents=True, exist_ok=True)
                tmp_file = obj_dir / f".tmp_{sha[2:]}_{os.getpid()}"
                tmp_file.write_bytes(zlib.compress(f"blob {len(data)}\0".encode("ascii") + data))
                tmp_file.replace(obj_file)
                return
            except OSError:
                pass
        self._hash_object(data)

    def ref_exists(self) -> bool:
        """Check if the local detached branch reference exists.

        Returns:
            True if the branch ref exists locally, False otherwise.
        """
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", self.ref_name],
            cwd=str(self.repo_root),
            capture_output=True,
            check=False,
        )
        return proc.returncode == 0

    def get_ref_commit(self) -> Optional[str]:
        """Get the commit SHA of the local branch ref if it exists.

        Returns:
            Commit SHA string or None if reference does not exist.
        """
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", self.ref_name],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
        return None

    def get_remote_ref_commit(self) -> Optional[str]:
        """Get the commit SHA of the remote tracking branch ref if it exists.

        Returns:
            Commit SHA string or None if reference does not exist.
        """
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", self.remote_ref_name],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
        return None

    def load_database(self) -> Optional[BugDatabaseModel]:
        """Load BugDatabaseModel from the individual BUG_*.md files on the detached branch.

        Attempts to read individual feedback/ markdown files from the local detached ref,
        then falls back to the remote tracking ref.

        Returns:
            BugDatabaseModel if successfully read, else None.
        """
        prefix = "BUG" if self.branch_name == "bugs" else "WORM"
        for target_ref in [self.ref_name, self.remote_ref_name]:
            try:
                proc = subprocess.run(
                    ["git", "ls-tree", "-r", "--name-only", target_ref, "feedback/"],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    bugs: List[BugReportModel] = []
                    for line in proc.stdout.splitlines():
                        path_str = line.strip()
                        file_name = Path(path_str).name
                        if not file_name.startswith(f"{prefix}_") or not file_name.endswith(".md"):
                            continue
                        show_proc = subprocess.run(
                            ["git", "show", f"{target_ref}:{path_str}"],
                            cwd=str(self.repo_root),
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if show_proc.returncode == 0 and show_proc.stdout.strip():
                            bug = self.exporter.parse_bug_markdown_content(
                                show_proc.stdout,
                                default_filename=file_name,
                            )
                            if bug:
                                bugs.append(bug)
                    if bugs:
                        bugs.sort(key=lambda b: (b.created_at, b.id))
                        return BugDatabaseModel(bugs=bugs)
            except Exception:
                continue

            # Fallback for historical commits before state json removal
            try:
                proc = subprocess.run(
                    ["git", "show", f"{target_ref}:{self.branch_name}.json"],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    data = json.loads(proc.stdout)
                    return BugDatabaseModel.model_validate(data)
            except Exception:
                continue
        return None

    def commit_database(
        self,
        database: BugDatabaseModel,
        commit_message: str = "Update bug tracker database",
        parents: Optional[List[str]] = None,
        extra_feedback_dir: Optional[Path] = None,
        sync_local_disk: bool = False,
        dirty_bug_ids: Optional[Collection[str]] = None,
    ) -> Optional[str]:
        """Write individual BUG_*.md files to the detached branch.

        Args:
            database: Bug database model containing all bugs to store.
            commit_message: Commit log message.
            parents: Optional list of parent commit hashes. If None, uses local ref commit.
            extra_feedback_dir: Optional directory to scan for additional feedback files (e.g. CR_*.md).
            sync_local_disk: If True, also writes exported files to local feedback/ directory.
            dirty_bug_ids: Optional collection of bug IDs that were modified. If provided and
                a parent commit exists, only dirty bugs and root metadata are regenerated.

        Returns:
            New commit SHA string or None if operation failed.
        """
        if parents is None:
            curr_parent = self.get_ref_commit()
            if not curr_parent:
                curr_parent = self.get_remote_ref_commit()
            parents = [curr_parent] if curr_parent else []

        git_objects_dir: Optional[Path] = None
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--git-path", "objects"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
            p = Path(res.stdout.strip())
            git_objects_dir = p if p.is_absolute() else (self.repo_root / p)
        except Exception:
            git_objects_dir = None

        feedback_path = extra_feedback_dir or (self.repo_root / "feedback")

        git_dir = self.repo_root / ".git"
        if git_dir.is_dir():
            tmp_index_path = git_dir / f"idx_{self.branch_name}_{os.getpid()}"
            tmp_dir_obj = None
        else:
            tmp_dir_obj = tempfile.TemporaryDirectory(prefix="git_idx_dir_")
            tmp_index_path = Path(tmp_dir_obj.name) / "index"

        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(tmp_index_path)
        env["GIT_OPTIONAL_LOCKS"] = "0"
        env["GIT_AUTHOR_NAME"] = "User"
        env["GIT_AUTHOR_EMAIL"] = "user@workspace"
        env["GIT_COMMITTER_NAME"] = "User"
        env["GIT_COMMITTER_EMAIL"] = "user@workspace"

        try:
            # If a parent commit exists, initialize the isolated index from its tree
            current_index: Dict[str, str] = {}
            if parents and parents[0]:
                subprocess.run(
                    ["git", "read-tree", parents[0]],
                    cwd=str(self.repo_root),
                    env=env,
                    check=True,
                )
                ls_proc = subprocess.run(
                    ["git", "ls-files", "-s"],
                    cwd=str(self.repo_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                for line in ls_proc.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        current_index[parts[3]] = parts[1]

            target_files: Dict[str, bytes] = {}

            # Store individual BUG_<id>.md files in feedback/
            prefix = "WORM" if self.branch_name == "worms" else "BUG"
            if parents and parents[0] and dirty_bug_ids is not None:
                dirty_set = set(dirty_bug_ids)
                for bug in database.bugs:
                    if bug.id in dirty_set:
                        bug_md = self.exporter.render_bug_markdown(bug).encode("utf-8")
                        clean_id = (
                            bug.id.removeprefix("BUG-").removeprefix("BUG_").removeprefix("WORM-").removeprefix("WORM_")
                        )
                        target_files[f"feedback/{prefix}_{clean_id}.md"] = bug_md
            else:
                for bug in database.bugs:
                    bug_md = self.exporter.render_bug_markdown(bug).encode("utf-8")
                    clean_id = (
                        bug.id.removeprefix("BUG-").removeprefix("BUG_").removeprefix("WORM-").removeprefix("WORM_")
                    )
                    target_files[f"feedback/{prefix}_{clean_id}.md"] = bug_md

            # Include existing CR_*.md review files if available (excluding CR.md)
            if not (parents and parents[0] and dirty_bug_ids is not None):
                if feedback_path.exists() and feedback_path.is_dir():
                    cr_candidates = [
                        cr_file
                        for cr_file in feedback_path.glob("CR_*.md")
                        if cr_file.is_file() and cr_file.name != "CR.md"
                    ]
                    for cr_file in cr_candidates:
                        try:
                            target_files[f"feedback/{cr_file.name}"] = cr_file.read_bytes()
                        except OSError:
                            continue

            # 5. Include attachments from attachments/ and feedback/attachments/
            target_disk_files: Dict[str, Path] = {}
            if dirty_bug_ids is not None:
                for b_id in dirty_bug_ids:
                    clean_b_id = (
                        b_id.removeprefix("BUG-").removeprefix("BUG_").removeprefix("WORM-").removeprefix("WORM_")
                    )
                    for base in ("attachments", "feedback/attachments"):
                        for cand in (self.repo_root / base / b_id, self.repo_root / base / clean_b_id):
                            if cand.exists() and cand.is_dir():
                                for att_file in cand.rglob("*"):
                                    if att_file.is_file():
                                        rel_p = att_file.relative_to(self.repo_root).as_posix()
                                        target_disk_files[rel_p] = att_file
            else:
                for att_dir_name in ("attachments", "feedback/attachments"):
                    att_dir = self.repo_root / att_dir_name
                    if att_dir.exists() and att_dir.is_dir():
                        for att_file in att_dir.rglob("*"):
                            if att_file.is_file():
                                rel_p = att_file.relative_to(self.repo_root).as_posix()
                                target_disk_files[rel_p] = att_file

            # Batch update index
            index_updates: List[str] = []
            for fn, data in target_files.items():
                sha = self._git_blob_sha(data)
                if current_index.get(fn) != sha:
                    self._ensure_blob_written(data, sha, git_objects_dir)
                    index_updates.append(f"{FILE_MODE_STANDARD} {sha} 0\t{fn}\n")

            for fn, disk_path in target_disk_files.items():
                sha = self._hash_file(disk_path, fn)
                if current_index.get(fn) != sha:
                    index_updates.append(f"{FILE_MODE_STANDARD} {sha} 0\t{fn}\n")

            if current_index:
                # Explicitly untrack and prune all aggregated index and state files
                forbidden_candidates = {
                    f"{self.branch_name}.json",
                    f"{self.branch_name.upper()}.json",
                    f"{self.branch_name.upper()}.md",
                    f"{self.branch_name}.md",
                    "WORMS.md",
                    "worms.json",
                    "WORMS.json",
                    "BUGS.md",
                    "bugs.json",
                    "BUGS.json",
                    "CR.md",
                    "feedback/WORMS.md",
                    "feedback/BUGS.md",
                    "feedback/CR.md",
                }
                for forbidden in forbidden_candidates:
                    if forbidden in current_index:
                        index_updates.append(f"0 0000000000000000000000000000000000000000 0\t{forbidden}\n")

                valid_bug_paths = {
                    f"feedback/{prefix}_{b.id.removeprefix('BUG-').removeprefix('BUG_').removeprefix('WORM-').removeprefix('WORM_')}.md"
                    for b in database.bugs
                }
                for p in current_index:
                    if dirty_bug_ids is None and p.startswith(f"feedback/{prefix}_") and p not in valid_bug_paths:
                        index_updates.append(f"0 0000000000000000000000000000000000000000 0\t{p}\n")

            if index_updates:
                subprocess.run(
                    ["git", "update-index", "--index-info"],
                    input="".join(index_updates).encode("utf-8"),
                    cwd=str(self.repo_root),
                    env=env,
                    check=True,
                )

            # 5. Write index to tree object
            tree_proc = subprocess.run(
                ["git", "write-tree"],
                cwd=str(self.repo_root),
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            tree_sha = tree_proc.stdout.strip()

            # Elide redundant commit if tree is identical to parent tree
            if parents and parents[0] and len(parents) == 1:
                try:
                    p_tree = subprocess.run(
                        ["git", "rev-parse", f"{parents[0]}^{{tree}}"],
                        cwd=str(self.repo_root),
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout.strip()
                    if tree_sha == p_tree:
                        return parents[0]
                except Exception:
                    pass

            # 6. Commit tree object
            clean_message = elide_personal_info(commit_message)
            commit_cmd = ["git", "commit-tree", tree_sha, "-m", clean_message]
            for p in parents:
                if p:
                    commit_cmd.extend(["-p", p])
            commit_proc = subprocess.run(
                commit_cmd,
                cwd=str(self.repo_root),
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            commit_sha = commit_proc.stdout.strip()

            # 7. Atomically update detached branch ref
            subprocess.run(
                ["git", "update-ref", self.ref_name, commit_sha],
                cwd=str(self.repo_root),
                check=True,
            )

            # 8. Optionally sync local feedback directory for local editor convenience
            if sync_local_disk:
                self.exporter.export_all_individual_bugs(database, feedback_path)
                state_json_path = self.repo_root / "build" / f"{self.branch_name}.json"
                self.exporter.export_state_json(database, state_json_path)

            return commit_sha
        finally:
            if tmp_dir_obj is not None:
                try:
                    tmp_dir_obj.cleanup()
                except OSError:
                    pass
            else:
                if tmp_index_path.exists():
                    try:
                        tmp_index_path.unlink()
                    except OSError:
                        pass
                lock_p = tmp_index_path.with_name(tmp_index_path.name + ".lock")
                if lock_p.exists():
                    try:
                        lock_p.unlink()
                    except OSError:
                        pass

    def checkout_attachments(self) -> List[Path]:
        """Extract attachments from the detached branch tree to the local workspace.

        Returns:
            List of paths to restored attachment files on disk.
        """
        if not self.ref_exists():
            return []
        try:
            tree_proc = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", self.ref_name],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, RuntimeError):
            return []

        restored: List[Path] = []
        for line in tree_proc.stdout.splitlines():
            path_str = line.strip()
            if not (path_str.startswith("attachments/") or path_str.startswith("feedback/attachments/")):
                continue
            dest_file = self.repo_root / path_str
            if dest_file.exists():
                continue
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                raw_bytes = subprocess.run(
                    ["git", "show", f"{self.ref_name}:{path_str}"],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    check=True,
                ).stdout
                if raw_bytes.startswith(b"version https://git-lfs"):
                    try:
                        smudged = subprocess.run(
                            ["git", "lfs", "smudge"],
                            input=raw_bytes,
                            cwd=str(self.repo_root),
                            capture_output=True,
                            check=True,
                        ).stdout
                        raw_bytes = smudged
                    except Exception:
                        pass
                dest_file.write_bytes(raw_bytes)
                restored.append(dest_file)
            except (subprocess.CalledProcessError, OSError):
                pass
        return restored

    def checkout_feedback_files(self) -> List[Path]:
        """Extract feedback markdown files from detached branch tree to local workspace.

        Returns:
            List of paths to restored or updated feedback files on disk.
        """
        if not self.ref_exists():
            return []
        try:
            tree_proc = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", self.ref_name],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, RuntimeError):
            return []

        restored: List[Path] = []
        for line in tree_proc.stdout.splitlines():
            path_str = line.strip()
            # Explicitly exclude aggregated index and state files to prevent workspace conflicts
            if path_str in (
                "WORMS.md",
                "BUGS.md",
                "CR.md",
                "worms.json",
                "WORMS.json",
                "bugs.json",
                "BUGS.json",
                "feedback/WORMS.md",
                "feedback/BUGS.md",
                "feedback/CR.md",
            ):
                continue
            if not path_str.startswith("feedback/"):
                continue
            if path_str.startswith("feedback/attachments/"):
                continue
            dest_file = self.repo_root / path_str
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                raw_bytes = subprocess.run(
                    ["git", "show", f"{self.ref_name}:{path_str}"],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    check=True,
                ).stdout
                if not dest_file.exists() or dest_file.read_bytes() != raw_bytes:
                    dest_file.write_bytes(raw_bytes)
                    restored.append(dest_file)
            except (subprocess.CalledProcessError, OSError):
                pass

        # Ensure index and state files never linger on disk
        for unwanted in (
            self.repo_root / "WORMS.md",
            self.repo_root / "BUGS.md",
            self.repo_root / "CR.md",
            self.repo_root / "worms.json",
            self.repo_root / "WORMS.json",
            self.repo_root / "bugs.json",
            self.repo_root / "BUGS.json",
            self.repo_root / "feedback" / "WORMS.md",
            self.repo_root / "feedback" / "BUGS.md",
            self.repo_root / "feedback" / "CR.md",
        ):
            if unwanted.exists():
                try:
                    unwanted.unlink()
                except OSError:
                    pass

        return restored

    def seed_from_workspace(
        self,
        sqlite_store: Optional[SQLiteBugStore] = None,
        force: bool = False,
    ) -> Optional[str]:
        """Seed detached branch from existing workspace database or feedback directory.

        Args:
            sqlite_store: Optional SQLiteBugStore to read existing bugs from.
            force: If True, re-seeds even if branch reference already exists.

        Returns:
            Commit SHA string if seeded, or existing commit SHA if already present.
        """
        if self.ref_exists() and not force:
            self.checkout_attachments()
            return self.get_ref_commit()

        db: Optional[BugDatabaseModel] = None
        if sqlite_store:
            try:
                db = sqlite_store.load_database()
            except Exception:
                db = None

        feedback_dir = self.repo_root / "feedback"
        if (not db or not db.bugs) and feedback_dir.exists():
            db = BugDatabaseModel()
            self.exporter.scan_and_sync_feedback_dir(feedback_dir, db, sqlite_store)

        if db and db.bugs:
            commit_sha = self.commit_database(
                db,
                commit_message="Initialize detached bug tracking database",
                extra_feedback_dir=feedback_dir,
            )
            self.checkout_attachments()
            return commit_sha
        return None

    def sync_branch(self, push: bool = True) -> Dict[str, Any]:
        """Reconcile detached bug branch with remote tracking ref.

        Commits workspace feedback and attachments, fetches origin/bugs, fast-forwards
        or merges with collision mitigation when needed, and pushes updated commits back to origin.

        Args:
            push: If True, pushes reconciled branch commits to origin.

        Returns:
            Dictionary with synchronization status, branch, commit details, and push status.
        """
        # 1. Commit local workspace database, feedback markdown, and attachments to detached branch
        local_db = self.load_database()
        if not local_db or not local_db.bugs:
            try:
                from provider.bug_report.sqlite_store import SQLiteBugStore

                sqlite_path = self.repo_root / "target" / "bugs.sqlite"
                if not sqlite_path.exists() and (self.repo_root / "build" / "bugs.sqlite").exists():
                    sqlite_path = self.repo_root / "build" / "bugs.sqlite"
                if sqlite_path.exists():
                    local_db = SQLiteBugStore(sqlite_path).load_database()
            except Exception:
                pass

        if local_db and local_db.bugs:
            self.commit_database(
                local_db,
                commit_message="Sync local feedback and attachments to detached branch",
                extra_feedback_dir=self.repo_root / "feedback",
            )

        has_remote = False
        try:
            remotes_proc = subprocess.run(
                ["git", "remote"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            remotes = [r.strip() for r in remotes_proc.stdout.splitlines()]
            has_remote = "origin" in remotes
        except Exception:
            has_remote = False

        if has_remote:
            subprocess.run(
                ["git", "fetch", "origin", f"{self.branch_name}:{self.remote_ref_name}"],
                cwd=str(self.repo_root),
                capture_output=True,
                check=False,
            )

        local_commit = self.get_ref_commit()
        remote_commit = self.get_remote_ref_commit()

        if not local_commit and remote_commit:
            subprocess.run(
                ["git", "update-ref", self.ref_name, remote_commit],
                cwd=str(self.repo_root),
                check=True,
            )
            local_commit = remote_commit
        elif local_commit and remote_commit and local_commit != remote_commit:
            is_ancestor = (
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", local_commit, remote_commit],
                    cwd=str(self.repo_root),
                    check=False,
                ).returncode
                == 0
            )
            if is_ancestor:
                subprocess.run(
                    ["git", "update-ref", self.ref_name, remote_commit],
                    cwd=str(self.repo_root),
                    check=True,
                )
                local_commit = remote_commit
            else:
                is_remote_ancestor = (
                    subprocess.run(
                        ["git", "merge-base", "--is-ancestor", remote_commit, local_commit],
                        cwd=str(self.repo_root),
                        check=False,
                    ).returncode
                    == 0
                )
                if not is_remote_ancestor:
                    # True divergence: merge databases with collision mitigation
                    local_db = self.load_database()
                    remote_json_proc = subprocess.run(
                        ["git", "show", f"{remote_commit}:{self.branch_name}.json"],
                        cwd=str(self.repo_root),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if remote_json_proc.returncode == 0 and remote_json_proc.stdout.strip() and local_db:
                        remote_db = BugDatabaseModel.model_validate(json.loads(remote_json_proc.stdout))
                        merged_db = self.exporter.merge_databases(local_db, remote_db)
                        local_commit = self.commit_database(
                            merged_db,
                            commit_message="Merge remote bug database updates with collision mitigation",
                            parents=[local_commit, remote_commit],
                            extra_feedback_dir=self.repo_root / "feedback",
                        )

        pushed = False
        if has_remote and local_commit and push:
            push_proc = subprocess.run(
                ["git", "push", "origin", f"{self.ref_name}:{self.ref_name}"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            pushed = push_proc.returncode == 0

        if local_commit:
            self.checkout_attachments()
            self.checkout_feedback_files()

        return {
            "status": "ok",
            "branch": self.branch_name,
            "commit": local_commit,
            "remote_commit": remote_commit,
            "pushed": pushed,
        }
