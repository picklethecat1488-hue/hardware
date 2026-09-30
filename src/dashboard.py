"""Interactive Quake VCS Dashboard, Code Review, and Bug Report Workstation CLI.

Launches a unified local browser-based workstation with a Quake retro console theme,
providing Smartlog ancestor DAG tree navigation, staged/unstaged/untracked file management,
commit split/combine, merge conflict resolution, interactive line-by-line Code Review,
and integrated Bug Tracker, all served under a single endpoint.

Usage:
    python src/dashboard.py
    python src/dashboard.py --port 8767
    python src/dashboard.py --list
    python src/dashboard.py --branch main
    python src/dashboard.py --goto 75d5f92
    python src/dashboard.py --bugs
    python src/dashboard.py --add-bug "Antenna on Q2" --severity HIGH --category PCB
    python src/dashboard.py --resolve-bug BUG-014 --notes "Fixed trace routing"
    python src/dashboard.py --reviews
    python src/dashboard.py --add-comment "Check crystal routing" --file src/provider/pcb/router.py --line 10
    python src/dashboard.py --resolve-comment abc123
    python src/dashboard.py --verdict APPROVED
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import uuid
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model.bug_report import BugCategory, BugReportModel, BugSeverity, BugStatus
from model.code_review import CommentModel, ReviewSeverity, ReviewStatus
from provider.dashboard.server import DashboardServer
from provider.vcs.git_engine import GitEngine, extract_line_snippet, get_git_root


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments for dashboard launcher."""
    raw_args = sys.argv[1:] if args is None else args
    subcommand_names = {
        "list-reviews",
        "list-bugs",
        "list-commits",
        "sync",
        "add-bug",
        "resolve-bug",
        "add-comment",
        "resolve-comment",
        "set-verdict",
    }
    has_subcommand = any(a in subcommand_names for a in raw_args)
    parser = argparse.ArgumentParser(
        description="Unified Quake VCS Dashboard, Code Review & Bug Tracker Workstation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Server / Interface configuration
    parser.add_argument(
        "--port",
        type=int,
        default=8767,
        help="Local port number for the unified dashboard web workstation.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface address to bind.",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Open dashboard on a specific git branch.",
    )
    parser.add_argument(
        "--goto",
        type=str,
        default=None,
        help="Jump directly to a specific commit hash or reference.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print smartlog DAG tree and working tree summary to terminal console and exit.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Download latest changes from remote repository and exit.",
    )
    parser.add_argument(
        "--browser",
        choices=["vscode", "system", "none"],
        default="vscode",
        help="Target browser environment to display dashboard (default: vscode).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Disable automatic browser opening on server launch.",
    )

    # Database & Session Configuration
    parser.add_argument(
        "--db-file",
        dest="db_file",
        type=Path,
        default=None,
        help="Custom SQLite database file for review or bugs.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Start a fresh tracking or review session.",
    )

    # Bug Tracker CLI Commands
    parser.add_argument(
        "--bugs",
        "--list-bugs",
        action="store_true",
        help="List all active bugs directly in the terminal and exit.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="When listing bugs or reviews, only show open / unresolved issues.",
    )
    parser.add_argument(
        "--add-bug",
        "--add",
        dest="add_bug",
        type=str,
        help="Quickly register a new bug with the specified title.",
    )
    severity_choices = [s.value for s in BugSeverity] + [s.value for s in ReviewSeverity]
    parser.add_argument(
        "--severity",
        choices=severity_choices,
        default=BugSeverity.MEDIUM.value,
        help="Severity level when registering a new bug or review comment.",
    )
    parser.add_argument(
        "--category",
        choices=[c.value for c in BugCategory],
        default=BugCategory.PCB.value,
        help="Subsystem category when registering a new bug.",
    )
    parser.add_argument(
        "--component",
        type=str,
        default="",
        help="Component or file name affected by the bug.",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Detailed description for quick-added bug.",
    )
    parser.add_argument(
        "--resolve-bug",
        "--resolve",
        dest="resolve_bug",
        type=str,
        help="Mark a bug ID as RESOLVED (e.g. --resolve-bug BUG-001).",
    )
    parser.add_argument(
        "--notes",
        type=str,
        default="",
        help="Resolution notes when resolving a bug.",
    )

    # Code Review CLI Commands
    if not has_subcommand:
        parser.add_argument(
            "commits",
            nargs="*",
            help="Optional commits or revision ranges to inspect in code review (e.g. HEAD~1, 542007d).",
        )
    parser.add_argument(
        "--reviews",
        action="store_true",
        help="List all active code review comments in the terminal and exit.",
    )
    parser.add_argument(
        "--add-comment",
        type=str,
        help="Quickly add a review comment with the specified body text.",
    )
    parser.add_argument(
        "--file",
        "--comment-file",
        dest="comment_file",
        type=str,
        default="",
        help="Target file path for quick-added review comment.",
    )
    parser.add_argument(
        "--line",
        "--comment-line",
        dest="comment_line",
        type=int,
        default=1,
        help="Line number for quick-added review comment.",
    )
    parser.add_argument(
        "--resolve-comment",
        type=str,
        help="Mark a review comment ID as resolved (e.g. --resolve-comment abc123).",
    )
    parser.add_argument(
        "--all-users",
        "--all",
        dest="all_users",
        action="store_true",
        help="Show reviews and bugs from all users instead of filtering to current user.",
    )
    parser.add_argument(
        "--user",
        type=str,
        default="",
        help="Filter reviews and bugs to a specific author user name or email.",
    )
    parser.add_argument(
        "--verdict",
        choices=[s.value for s in ReviewStatus],
        help="Set overall review verdict from CLI.",
    )

    # Subcommands (BUG-240)
    subparsers = parser.add_subparsers(dest="subcommand", help="Workstation subcommands")

    # list-reviews
    p_reviews = subparsers.add_parser("list-reviews", help="List active code review comments and exit.")
    p_reviews.add_argument("--open", action="store_true", help="Only show unresolved review findings.")
    p_reviews.add_argument(
        "--all-users", "--all", dest="all_users", action="store_true", help="Show reviews from all users."
    )
    p_reviews.add_argument("--user", type=str, default="", help="Filter comments to specific author.")
    p_reviews.add_argument("commits", nargs="*", help="Optional commits or revision ranges to inspect.")

    # list-bugs
    p_bugs = subparsers.add_parser("list-bugs", help="List all active bugs directly in terminal and exit.")
    p_bugs.add_argument("--open", action="store_true", help="Only show open / unresolved issues.")
    p_bugs.add_argument(
        "--severity",
        choices=[s.value for s in BugSeverity],
        default=None,
        help="Filter by severity.",
    )
    p_bugs.add_argument(
        "--category",
        choices=[c.value for c in BugCategory],
        default=None,
        help="Filter by category.",
    )
    p_bugs.add_argument("--all-users", "--all", dest="all_users", action="store_true", help="Show bugs from all users.")
    p_bugs.add_argument("--user", type=str, default="", help="Filter bugs to specific author.")

    # list-commits
    subparsers.add_parser("list-commits", help="Print smartlog DAG tree and working tree summary to console.")

    # sync
    subparsers.add_parser("sync", help="Download latest changes from remote repository and exit.")

    # add-bug
    p_add_b = subparsers.add_parser("add-bug", help="Quickly register a new bug report.")
    p_add_b.add_argument("title", nargs="?", default="", help="Bug title.")
    p_add_b.add_argument("--title", dest="bug_title", default="", help="Bug title.")
    p_add_b.add_argument("--severity", choices=[s.value for s in BugSeverity], default=BugSeverity.MEDIUM.value)
    p_add_b.add_argument("--category", choices=[c.value for c in BugCategory], default=BugCategory.PCB.value)
    p_add_b.add_argument("--component", default="")
    p_add_b.add_argument("--description", default="")

    # resolve-bug
    p_res_b = subparsers.add_parser("resolve-bug", help="Mark a bug ID as RESOLVED.")
    p_res_b.add_argument("id", nargs="?", default="", help="Bug ID (e.g. BUG-001).")
    p_res_b.add_argument("--id", dest="bug_id", default="", help="Bug ID.")
    p_res_b.add_argument("--notes", default="", help="Resolution notes.")

    # add-comment
    p_add_c = subparsers.add_parser("add-comment", help="Quickly add a review comment.")
    p_add_c.add_argument("body", nargs="?", default="", help="Comment body.")
    p_add_c.add_argument("--body", dest="comment_body", default="")
    p_add_c.add_argument("--file", dest="comment_file", required=True, help="Target file path.")
    p_add_c.add_argument("--line", dest="comment_line", type=int, default=1, help="Line number.")
    p_add_c.add_argument("--severity", choices=[s.value for s in ReviewSeverity], default="MUST_FIX")
    p_add_c.add_argument("--commit", default="working")

    # resolve-comment
    p_res_c = subparsers.add_parser("resolve-comment", help="Mark a review comment ID as resolved.")
    p_res_c.add_argument("id", nargs="?", default="", help="Comment ID.")
    p_res_c.add_argument("--id", dest="comment_id", default="")

    # set-verdict
    p_verd = subparsers.add_parser("set-verdict", help="Set overall review verdict from CLI.")
    p_verd.add_argument("verdict", choices=[s.value for s in ReviewStatus])

    parsed = parser.parse_args(args)
    if not hasattr(parsed, "commits"):
        parsed.commits = []
    return parsed


def launch_browser(url: str, target: str = "vscode") -> None:
    """Open the review or diff workstation dashboard in the specified browser environment.

    Args:
        url: The web URL of the workstation dashboard.
        target: Target browser environment ('vscode', 'system', 'none').
    """
    match target:
        case "none":
            return
        case "vscode":
            # In VS Code, the integrated terminal intercepts localhost links with
            # workbench.externalUriOpeners configured for simpleBrowser.open.
            # We avoid spawning the system browser or the 'code' binary.
            return
        case "system":
            webbrowser.open(url)
        case _:
            webbrowser.open(url)


def print_cli_smartlog(engine: GitEngine) -> None:
    """Print formatted Smartlog ancestor DAG tree and working tree status to console."""
    repo_name = engine.repo_root.name
    branch = engine.get_current_branch()
    head = engine.get_head_commit()
    nodes = engine.get_smartlog_dag(limit=30)
    working_files = engine.get_working_tree_files()
    conflicts = engine.get_merge_conflicts()

    print("\n" + "=" * 70)
    print(f"  QUAKE VCS // SMARTLOG DAG TREE : {repo_name} (branch: {branch})")
    print("=" * 70)

    staged = [f for f in working_files if f.is_staged and not f.is_feedback]
    unstaged = [f for f in working_files if not f.is_staged and not f.is_untracked and not f.is_conflicted]
    untracked = [f for f in working_files if f.is_untracked]
    feedback = [f for f in working_files if f.is_feedback]

    print(
        f"  @  WORKING TREE : {len(staged)} staged, {len(unstaged)} unstaged, {len(untracked)} untracked, {len(conflicts)} conflicts"
    )
    if conflicts:
        for c in conflicts:
            print(f"     ⚠ CONFLICT : {c.path} ({c.conflict_markers_count} markers)")
    if staged:
        for f in staged:
            print(f"     ✓ STAGED   : {f.path} (+{f.additions} -{f.deletions})")
    if feedback:
        print(f"     🤖 FEEDBACK : {len(feedback)} agent feedback files (feedback/)")

    print("  |")

    for node in nodes:
        marker = node.graph_art or node.graph_symbol
        branch_str = f" ({', '.join(node.branches)})" if node.branches else ""
        pr_str = f" [{node.pr_status}]" if node.pr_status else ""
        head_mark = " (HEAD)" if node.commit_hash == head else ""
        print(
            f"  {marker}  {node.short_hash}{head_mark}{branch_str}{pr_str} - {node.subject} ({node.relative_date or node.date}) <{node.author}>"
        )
        for bug in node.bug_tags:
            print(f"     🏷  {bug.id}: [{bug.status}] {bug.title}")
    print("=" * 70 + "\n")


def print_cli_bugs(
    server: DashboardServer,
    open_only: bool = False,
    all_users: bool = False,
    filter_user: str = "",
    engine: Optional[GitEngine] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
) -> None:
    """Print bug tracker status to terminal console with optional filtering."""
    bugs = server.bug_server.database.bugs
    print("\n=== Hardware Bug Tracker ===")
    if not bugs:
        print("No bugs registered.\n")
        return

    curr_user = engine.get_current_user() if engine else {"name": "", "email": ""}
    filtered = []
    for b in bugs:
        if open_only and b.status in (BugStatus.RESOLVED, BugStatus.CLOSED):
            continue
        if severity and b.severity.value != severity:
            continue
        if category and b.category.value != category:
            continue

        # Per-user filtering (BUG-239)
        if not all_users and engine:
            bug_file = server.repo_root / "feedback" / f"{b.id}.md"
            b_author = engine.get_file_author(bug_file)
            if filter_user:
                if (
                    filter_user.lower() not in b_author["name"].lower()
                    and filter_user.lower() not in b_author["email"].lower()
                ):
                    continue
            elif curr_user["name"]:
                if b_author["name"] != curr_user["name"] and b_author["email"] != curr_user["email"]:
                    continue
        filtered.append(b)

    for b in filtered:
        chk = "[X]" if b.status in (BugStatus.RESOLVED, BugStatus.CLOSED) else "[ ]"
        comp = f" ({b.component})" if b.component else ""
        print(f"  {chk} [{b.id}] [{b.severity.value}] [{b.category.value}] {b.title}{comp} -> {b.status.value}")

    total_open = sum(1 for b in filtered if b.status not in (BugStatus.RESOLVED, BugStatus.CLOSED))
    total_all = len(filtered)
    print(f"\nShowing {len(filtered)} issues ({total_open} open, {total_all} total).\n")


def print_cli_reviews(
    server: DashboardServer,
    open_only: bool = False,
    all_users: bool = False,
    filter_user: str = "",
    engine: Optional[GitEngine] = None,
) -> None:
    """Print code review comments to terminal console with optional per-user filtering."""
    session = server.review_server.session
    print("\n=== Code Review Session ===")
    print(f"  Title:   {session.title}")
    print(f"  Verdict: {session.verdict.value}")

    curr_user = engine.get_current_user() if engine else {"name": "", "email": ""}
    comments = []
    for c in session.comments:
        if open_only and c.resolved:
            continue
        # Per-user filtering (BUG-239)
        if not all_users and engine:
            if filter_user:
                if filter_user.lower() not in (c.author or "").lower():
                    continue
            elif curr_user["name"]:
                c_author = c.author or ""
                if c_author not in ("Reviewer", "", curr_user["name"], curr_user["email"]):
                    continue
                if c.commit and c.commit != "working":
                    commit_author = engine.get_commit_author(c.commit)
                    if commit_author["name"] != curr_user["name"] and commit_author["email"] != curr_user["email"]:
                        continue
        comments.append(c)

    counts = {}
    for c in comments:
        sev = c.severity.value if hasattr(c.severity, "value") else str(c.severity)
        counts[sev] = counts.get(sev, 0) + 1
    unresolved_count = sum(1 for c in comments if not c.resolved)
    total_count = len(comments)
    print(
        f"  Findings: {total_count} total "
        f"({counts.get('MUST_FIX', 0)} MUST_FIX, {counts.get('PROPOSAL', 0)} PROPOSAL, {counts.get('NIT', 0)} NIT) - {unresolved_count} unresolved"
    )
    if not comments:
        print("  No comments registered.\n")
    else:
        for c in comments:
            chk = "[X]" if c.resolved else "[ ]"
            summary_line = c.body.splitlines()[0] if c.body else ""
            print(f"  {chk} [{c.id}] [{c.severity.value}] {c.file_path}:{c.start_line} -> {summary_line}")
        print(f"\nShowing {len(comments)} comments ({unresolved_count} unresolved, {total_count} total).\n")


def main() -> None:
    """Launch the Quake dashboard CLI or workstation server."""
    args = parse_arguments()
    repo_root = get_git_root()
    engine = GitEngine(repo_root=repo_root)

    subcmd = getattr(args, "subcommand", None)

    # Check if this invocation is CLI-only (no server socket needed)
    is_cli_only = bool(
        subcmd
        or getattr(args, "bugs", False)
        or getattr(args, "add_bug", None)
        or getattr(args, "resolve_bug", None)
        or getattr(args, "reviews", False)
        or getattr(args, "add_comment", None)
        or getattr(args, "resolve_comment", None)
        or getattr(args, "verdict", None)
        or (getattr(args, "list", False) and getattr(args, "db_file", None))
    )

    commits_arg = getattr(args, "commits", None)
    is_review_cmd = bool(
        subcmd in ("list-reviews", "add-comment", "resolve-comment", "set-verdict")
        or getattr(args, "reviews", False)
        or getattr(args, "add_comment", None)
        or getattr(args, "resolve_comment", None)
        or getattr(args, "verdict", None)
        or commits_arg
    )
    is_bug_cmd = bool(
        subcmd in ("list-bugs", "add-bug", "resolve-bug")
        or getattr(args, "bugs", False)
        or getattr(args, "add_bug", None)
        or getattr(args, "resolve_bug", None)
    )
    review_db = args.db_file if (args.db_file and not is_bug_cmd) else None
    bug_db = args.db_file if (args.db_file and not is_review_cmd) else None

    server = DashboardServer(
        host=args.host,
        port=args.port,
        repo_root=repo_root,
        initial_branch=args.branch,
        initial_commit=args.goto,
        sqlite_bug_file=bug_db,
        sqlite_review_file=review_db,
        revisions=commits_arg if commits_arg else None,
        fresh=args.fresh,
        bind_and_activate=not is_cli_only,
    )

    all_users = getattr(args, "all_users", False)
    filter_user = getattr(args, "user", "") or ""

    # Route Subcommands (BUG-240)
    match subcmd:
        case "list-reviews":
            print_cli_reviews(
                server,
                open_only=getattr(args, "open", False),
                all_users=all_users,
                filter_user=filter_user,
                engine=engine,
            )
            return
        case "list-bugs":
            print_cli_bugs(
                server,
                open_only=getattr(args, "open", False),
                all_users=all_users,
                filter_user=filter_user,
                engine=engine,
                severity=getattr(args, "severity", None),
                category=getattr(args, "category", None),
            )
            return
        case "list-commits":
            print_cli_smartlog(engine)
            return
        case "sync":
            print(f"\n[Quake VCS] Syncing repository {repo_root.name} from remote...")
            res = engine.sync_repo()
            print(f"Status : {res.get('status')}")
            print(f"Message: {res.get('message')}\n")
            return
        case "add-bug":
            title = getattr(args, "bug_title", "") or getattr(args, "title", "")
            if not title:
                print("Error: Bug title is required.", file=sys.stderr)
                sys.exit(1)
            bug_id = server.bug_server.database.generate_bug_id()
            bug = BugReportModel(
                id=bug_id,
                title=title,
                status=BugStatus.OPEN,
                severity=BugSeverity(args.severity),
                category=BugCategory(args.category),
                component=args.component,
                description=args.description,
            )
            server.bug_server.database.add_or_update(bug)
            server.bug_server.save_and_sync()
            print(f"Registered bug [{bug.id}]: {bug.title} ({bug.severity.value})")
            return
        case "resolve-bug":
            bug_id = getattr(args, "bug_id", "") or getattr(args, "id", "")
            if not bug_id:
                print("Error: Bug ID is required.", file=sys.stderr)
                sys.exit(1)
            bug = server.bug_server.database.get_bug(bug_id)
            if not bug:
                print(f"Bug '{bug_id}' not found in database.", file=sys.stderr)
                sys.exit(1)
            bug.status = BugStatus.RESOLVED
            bug.resolved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            if getattr(args, "notes", ""):
                bug.resolution_notes = args.notes
            server.bug_server.save_and_sync()
            print(f"Resolved bug [{bug.id}]: {bug.title}")
            return
        case "add-comment":
            body = getattr(args, "comment_body", "") or getattr(args, "body", "")
            if not body:
                print("Error: Comment body is required.", file=sys.stderr)
                sys.exit(1)
            cid = uuid.uuid4().hex[:12]
            commit = getattr(args, "commit", "working") or "working"
            snippet = extract_line_snippet(
                file_path=args.comment_file,
                start_line=args.comment_line,
                end_line=args.comment_line,
                commit=commit,
                repo_root=repo_root,
            )
            comment = CommentModel(
                id=cid,
                file_path=args.comment_file,
                start_line=args.comment_line,
                end_line=args.comment_line,
                severity=ReviewSeverity(
                    args.severity if args.severity in [s.value for s in ReviewSeverity] else "MUST_FIX"
                ),
                body=body,
                author="Reviewer",
                code_snippet=snippet,
                created_at=datetime.now(timezone.utc).isoformat(),
                commit=commit,
            )
            server.review_server.session.comments.append(comment)
            server.review_server.session.auto_update_status_on_comment()
            server.review_server.save_and_sync()
            print(
                f"Added comment [{comment.id}] on {comment.file_path}:{comment.start_line} [{comment.severity.value}]"
            )
            return
        case "resolve-comment":
            comment_id = getattr(args, "comment_id", "") or getattr(args, "id", "")
            if not comment_id:
                print("Error: Comment ID is required.", file=sys.stderr)
                sys.exit(1)
            target_c = None
            for c in server.review_server.session.comments:
                if c.id == comment_id:
                    c.resolved = True
                    target_c = c
                    break
            if not target_c:
                print(f"Comment '{comment_id}' not found.", file=sys.stderr)
                sys.exit(1)
            server.review_server.save_and_sync()
            print(f"Resolved comment [{target_c.id}] on {target_c.file_path}:{target_c.start_line}")
            return
        case "set-verdict":
            server.review_server.session.verdict = ReviewStatus(args.verdict)
            server.review_server.save_and_sync()
            print(f"Updated review verdict to: {server.review_server.session.verdict.value}")
            return
        case _:
            pass

    # Direct CLI smartlog (when no specific db_file target is requested)
    if getattr(args, "list", False) and not args.db_file:
        print_cli_smartlog(engine)
        return

    if getattr(args, "list", False) and args.db_file:
        if server.review_server.session.comments or is_review_cmd:
            print_cli_reviews(
                server,
                open_only=getattr(args, "open", False),
                all_users=all_users,
                filter_user=filter_user,
                engine=engine,
            )
            return
        if server.bug_server.database.bugs or is_bug_cmd:
            print_cli_bugs(
                server,
                open_only=getattr(args, "open", False),
                all_users=all_users,
                filter_user=filter_user,
                engine=engine,
            )
            return
        print_cli_reviews(
            server,
            open_only=getattr(args, "open", False),
            all_users=all_users,
            filter_user=filter_user,
            engine=engine,
        )
        return

    # Direct CLI git sync
    if getattr(args, "sync", False):
        print(f"\n[Quake VCS] Syncing repository {repo_root.name} from remote...")
        res = engine.sync_repo()
        print(f"Status : {res.get('status')}")
        print(f"Message: {res.get('message')}\n")
        return

    # Handle Bug Tracker CLI
    if getattr(args, "add_bug", None):
        bug_id = server.bug_server.database.generate_bug_id()
        bug = BugReportModel(
            id=bug_id,
            title=args.add_bug,
            status=BugStatus.OPEN,
            severity=BugSeverity(args.severity),
            category=BugCategory(args.category),
            component=args.component,
            description=args.description,
        )
        server.bug_server.database.add_or_update(bug)
        server.bug_server.save_and_sync()
        print(f"Registered bug [{bug.id}]: {bug.title} ({bug.severity.value})")
        return

    if getattr(args, "resolve_bug", None):
        bug = server.bug_server.database.get_bug(args.resolve_bug)
        if not bug:
            print(f"Bug '{args.resolve_bug}' not found in database.", file=sys.stderr)
            sys.exit(1)
        bug.status = BugStatus.RESOLVED
        bug.resolved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if args.notes:
            bug.resolution_notes = args.notes
        server.bug_server.save_and_sync()
        print(f"Resolved bug [{bug.id}]: {bug.title}")
        return

    if getattr(args, "bugs", False) or (getattr(args, "list", False) and args.db_file and "bug" in str(args.db_file)):
        print_cli_bugs(
            server,
            open_only=getattr(args, "open", False),
            all_users=all_users,
            filter_user=filter_user,
            engine=engine,
        )
        return

    # Handle Code Review CLI
    if getattr(args, "add_comment", None):
        if not args.comment_file:
            print("Error: --file is required when adding a comment.", file=sys.stderr)
            sys.exit(1)
        cid = uuid.uuid4().hex[:12]
        commit = args.commits[0] if getattr(args, "commits", None) else "working"
        snippet = extract_line_snippet(
            file_path=args.comment_file,
            start_line=args.comment_line,
            end_line=args.comment_line,
            commit=commit,
            repo_root=repo_root,
        )
        comment = CommentModel(
            id=cid,
            file_path=args.comment_file,
            start_line=args.comment_line,
            end_line=args.comment_line,
            severity=ReviewSeverity(
                args.severity if args.severity in [s.value for s in ReviewSeverity] else "MUST_FIX"
            ),
            body=args.add_comment,
            author="Reviewer",
            code_snippet=snippet,
            created_at=datetime.now(timezone.utc).isoformat(),
            commit=commit,
        )
        server.review_server.session.comments.append(comment)
        server.review_server.session.auto_update_status_on_comment()
        server.review_server.save_and_sync()
        print(f"Added comment [{comment.id}] on {comment.file_path}:{comment.start_line} [{comment.severity.value}]")
        return

    if getattr(args, "resolve_comment", None):
        target_c = None
        for c in server.review_server.session.comments:
            if c.id == args.resolve_comment:
                c.resolved = True
                target_c = c
                break
        if not target_c:
            print(f"Comment '{args.resolve_comment}' not found.", file=sys.stderr)
            sys.exit(1)
        server.review_server.save_and_sync()
        print(f"Resolved comment [{target_c.id}] on {target_c.file_path}:{target_c.start_line}")
        return

    if getattr(args, "verdict", None):
        server.review_server.session.verdict = ReviewStatus(args.verdict)
        server.review_server.save_and_sync()
        print(f"Updated review verdict to: {server.review_server.session.verdict.value}")
        return

    if getattr(args, "reviews", False) or (
        getattr(args, "list", False) and args.db_file and "review" in str(args.db_file)
    ):
        print_cli_reviews(
            server,
            open_only=getattr(args, "open", False),
            all_users=all_users,
            filter_user=filter_user,
            engine=engine,
        )
        return
        return

    # Interactive Server Mode
    url = server.get_url()
    curr_branch = engine.get_current_branch()

    banner = rf"""
======================================================================
  QUAKE VCS // UNIFIED DASHBOARD WORKSTATION v1.0
======================================================================
  * Dashboard URL  : {url}
  * Repository     : {repo_root.name}
  * Active Branch  : {curr_branch}
  * Sub-Stations   :
      - VCS / Diff View : {url}/
      - Code Review     : {url}/review
      - Bug Tracker     : {url}/bugs
  * Browser Target : {args.browser.upper()}
  * Press [Ctrl+C] to shut down server.
======================================================================
  ➜ In VS Code: [Cmd+Click] the Dashboard URL above to open inside
    the integrated Simple Browser (or press [F5] / run Task).
======================================================================
"""
    print(banner)

    browser_mode = "none" if args.no_browser else args.browser
    if browser_mode != "none":

        def _open() -> None:
            time.sleep(0.3)
            launch_browser(url, target=browser_mode)

        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Dashboard server via interrupt...")
    finally:
        server.server_close()
        print("Dashboard server shut down. Terminal released.\n")


if __name__ == "__main__":
    main()
