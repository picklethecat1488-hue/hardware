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
import uuid
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model.bug_report import BugCategory, BugReportModel, BugSeverity, BugStatus
from model.code_review import CommentModel, ReviewSeverity, ReviewStatus
from provider.dashboard.server import DashboardServer
from provider.vcs.git_engine import GitEngine, extract_line_snippet, get_git_root


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for dashboard launcher."""
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
        "--verdict",
        choices=[s.value for s in ReviewStatus],
        help="Set overall review verdict from CLI.",
    )
    return parser.parse_args()


def launch_browser(url: str, target: str = "vscode") -> None:
    """Open the review or diff workstation dashboard in the specified browser environment."""
    match target:
        case "vscode":
            try:
                import subprocess

                subprocess.run(
                    ["code", "--open-url", url],
                    check=False,
                    capture_output=True,
                )
            except Exception:
                webbrowser.open(url)
        case "system":
            webbrowser.open(url)
        case "none":
            pass
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


def print_cli_bugs(server: DashboardServer, open_only: bool = False) -> None:
    """Print bug tracker status to terminal console."""
    bugs = server.bug_server.database.bugs
    print("\n=== Hardware Bug Tracker ===")
    if not bugs:
        print("No bugs registered.")
    else:
        filtered = [b for b in bugs if not open_only or b.status not in (BugStatus.RESOLVED, BugStatus.CLOSED)]
        for b in filtered:
            chk = "[X]" if b.status in (BugStatus.RESOLVED, BugStatus.CLOSED) else "[ ]"
            comp = f" ({b.component})" if b.component else ""
            print(f"  {chk} [{b.id}] [{b.severity.value}] [{b.category.value}] {b.title}{comp} -> {b.status.value}")
        total_open = sum(1 for b in bugs if b.status not in (BugStatus.RESOLVED, BugStatus.CLOSED))
        total_all = len(bugs)
        print(f"\nShowing {len(filtered)} issues ({total_open} open, {total_all} total).")
    print()


def print_cli_reviews(server: DashboardServer, open_only: bool = False) -> None:
    """Print code review comments to terminal console."""
    session = server.review_server.session
    print("\n=== Code Review Session ===")
    print(f"  Title:   {session.title}")
    print(f"  Verdict: {session.verdict.value}")
    counts = session.count_by_severity()
    unresolved_count = sum(1 for c in session.comments if not c.resolved)
    total_count = len(session.comments)
    print(
        f"  Findings: {total_count} total "
        f"({counts.get('MUST_FIX', 0)} MUST_FIX, {counts.get('PROPOSAL', 0)} PROPOSAL, {counts.get('NIT', 0)} NIT) - {unresolved_count} unresolved"
    )
    if not session.comments:
        print("  No comments registered.")
    else:
        comments = [c for c in session.comments if not open_only or not c.resolved]
        for c in comments:
            chk = "[X]" if c.resolved else "[ ]"
            summary_line = c.body.splitlines()[0] if c.body else ""
            print(f"  {chk} [{c.id}] [{c.severity.value}] {c.file_path}:{c.start_line} -> {summary_line}")
        print(f"\nShowing {len(comments)} comments ({unresolved_count} unresolved, {total_count} total).")
    print()


def main() -> None:
    """Launch the Quake dashboard CLI or workstation server."""
    args = parse_arguments()
    repo_root = get_git_root()
    engine = GitEngine(repo_root=repo_root)

    # Check if this invocation is CLI-only (no server socket needed)
    is_cli_only = bool(
        args.bugs
        or args.add_bug
        or args.resolve_bug
        or args.reviews
        or args.add_comment
        or args.resolve_comment
        or args.verdict
        or (args.list and args.db_file)
    )

    is_review_cmd = bool(args.reviews or args.add_comment or args.resolve_comment or args.verdict or args.commits)
    is_bug_cmd = bool(args.bugs or args.add_bug or args.resolve_bug)
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
        revisions=args.commits if args.commits else None,
        fresh=args.fresh,
        bind_and_activate=not is_cli_only,
    )

    # Direct CLI smartlog (when no specific db_file target is requested)
    if args.list and not args.db_file:
        print_cli_smartlog(engine)
        return

    if args.list and args.db_file:
        if server.review_server.session.comments or is_review_cmd:
            print_cli_reviews(server, open_only=args.open)
            return
        if server.bug_server.database.bugs or is_bug_cmd:
            print_cli_bugs(server, open_only=args.open)
            return
        print_cli_reviews(server, open_only=args.open)
        return

    # Direct CLI git sync
    if args.sync:
        print(f"\n[Quake VCS] Syncing repository {repo_root.name} from remote...")
        res = engine.fetch_or_pull()
        print(f"Status : {res.get('status')}")
        print(f"Message: {res.get('message')}\n")
        return

    # Handle Bug Tracker CLI
    if args.add_bug:
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

    if args.resolve_bug:
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

    if args.bugs or (args.list and args.db_file and "bug" in str(args.db_file)):
        print_cli_bugs(server, open_only=args.open)
        return

    # Handle Code Review CLI
    if args.add_comment:
        if not args.comment_file:
            print("Error: --file is required when adding a comment.", file=sys.stderr)
            sys.exit(1)
        cid = uuid.uuid4().hex[:12]
        commit = args.commits[0] if args.commits else "working"
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

    if args.resolve_comment:
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

    if args.verdict:
        server.review_server.session.verdict = ReviewStatus(args.verdict)
        server.review_server.save_and_sync()
        print(f"Updated review verdict to: {server.review_server.session.verdict.value}")
        return

    if args.reviews or (args.list and args.db_file and "review" in str(args.db_file)):
        print_cli_reviews(server, open_only=args.open)
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
