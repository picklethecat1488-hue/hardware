"""Interactive Bug Report Tool and SQLite Workstation CLI.

Launches a local browser-based bug reporting workstation, allowing issue triage,
reproduction step logging, and attachment uploads (screenshots, logs, CAD refs),
backed fully by an ACID SQLite database (build/bugs.sqlite).

Usage:
    python src/bug_report.py
    python src/bug_report.py --port 8766
    python src/bug_report.py --list
    python src/bug_report.py --add "Antenna on Q2" --severity HIGH --category PCB
"""

import argparse
from pathlib import Path
import sys
import threading
import time
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model.bug_report import BugCategory, BugReportModel, BugSeverity, BugStatus
from provider.bug_report.server import BugReportServer
from provider.code_review.git_utils import get_git_root


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for bug report launcher.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Hardware Bug Report Terminal & SQLite Workstation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8766,
        help="Local port number for the bug report web dashboard.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface address to bind.",
    )
    parser.add_argument(
        "--db-file",
        "--sqlite-file",
        dest="db_file",
        type=Path,
        default=Path("build/bugs.sqlite"),
        help="Persistent SQLite database file storing bug workstation records.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Start a fresh bug tracking session, ignoring previous database state.",
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
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all active bugs directly in the terminal.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="When used with --list, only show open / unresolved issues.",
    )
    parser.add_argument(
        "--add",
        type=str,
        help="Quickly register a new bug with the specified title.",
    )
    parser.add_argument(
        "--severity",
        choices=[s.value for s in BugSeverity],
        default=BugSeverity.MEDIUM.value,
        help="Severity level when registering a new bug.",
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
        "--resolve",
        type=str,
        help="Mark a bug ID as RESOLVED (e.g. --resolve BUG-001).",
    )
    parser.add_argument(
        "--notes",
        type=str,
        default="",
        help="Resolution notes when resolving a bug.",
    )
    return parser.parse_args()


def launch_browser(url: str, target: str = "vscode") -> None:
    """Open bug report dashboard URL.

    Args:
        url: The web URL of the bug report dashboard.
        target: Target browser environment ('vscode', 'system', 'none').
    """
    match target:
        case "none":
            return
        case "vscode":
            return
        case "system":
            webbrowser.open(url)
        case _:
            webbrowser.open(url)


def main() -> None:
    """Run bug report server or perform direct CLI actions."""
    args = parse_arguments()
    repo_root = get_git_root()

    db_path = args.db_file if args.db_file.is_absolute() else (repo_root / args.db_file)
    state_path = db_path.with_suffix(".json")
    markdown_path = db_path.with_suffix(".md")

    is_cli_only = bool(args.add or args.resolve or args.list)
    server = BugReportServer(
        host=args.host,
        port=args.port,
        repo_root=repo_root,
        markdown_output=markdown_path,
        state_file=state_path,
        sqlite_file=db_path,
        fresh=args.fresh,
        bind_and_activate=not is_cli_only,
    )

    # Handle quick add
    if args.add:
        bug_id = server.database.generate_bug_id()
        bug = BugReportModel(
            id=bug_id,
            title=args.add,
            status=BugStatus.OPEN,
            severity=BugSeverity(args.severity),
            category=BugCategory(args.category),
            component=args.component,
            description=args.description,
        )
        server.database.add_or_update(bug)
        server.save_and_sync()
        print(f"Registered bug [{bug.id}]: {bug.title} ({bug.severity.value})")
        return

    # Handle quick resolve
    if args.resolve:
        bug = server.database.get_bug(args.resolve)
        if not bug:
            print(f"Bug '{args.resolve}' not found in database.", file=sys.stderr)
            sys.exit(1)
        bug.status = BugStatus.RESOLVED
        from datetime import datetime, timezone

        bug.resolved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if args.notes:
            bug.resolution_notes = args.notes
        server.save_and_sync()
        print(f"Resolved bug [{bug.id}]: {bug.title}")
        return

    # Handle terminal list
    if args.list:
        print("\n=== Hardware Bug Tracker ===")
        if not server.database.bugs:
            print("No bugs registered.")
        else:
            bugs = [
                b
                for b in server.database.bugs
                if not args.open or b.status not in (BugStatus.RESOLVED, BugStatus.CLOSED)
            ]
            for b in bugs:
                chk = "[X]" if b.status in (BugStatus.RESOLVED, BugStatus.CLOSED) else "[ ]"
                comp = f" ({b.component})" if b.component else ""
                print(f"  {chk} [{b.id}] [{b.severity.value}] [{b.category.value}] {b.title}{comp} -> {b.status.value}")
            total_open = sum(1 for b in server.database.bugs if b.status not in (BugStatus.RESOLVED, BugStatus.CLOSED))
            total_all = len(server.database.bugs)
            print(f"\nShowing {len(bugs)} issues ({total_open} open, {total_all} total).")
        print()
        return

    # Initial sync to ensure SQLite database is ready
    server.save_and_sync()
    url = server.get_url()

    print("=================================================================")
    print("  HARDWARE BUG REPORT TERMINAL & WORKSTATION")
    print(f"  Dashboard URL: {url}")
    print(f"  Database:      {db_path}")
    print("  Press Ctrl+C to terminate the bug reporting session.")
    print("=================================================================")

    browser_mode = "none" if args.no_browser else args.browser
    threading.Thread(target=launch_browser, args=(url, browser_mode), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSaving bug database and shutting down server...")
        server.save_and_sync()


if __name__ == "__main__":
    main()
