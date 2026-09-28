"""Interactive Quake Diff Viewer and Smartlog VCS Workstation CLI.

Launches a local browser-based workstation with a Quake retro console theme,
providing Smartlog ancestor DAG tree navigation, staged/unstaged/untracked file management,
commit split/combine, merge conflict resolution, and direct integration with
Code Review (8765) and Bug Tracker (8766).

Usage:
    python src/diff_view.py
    python src/diff_view.py --port 8767
    python src/diff_view.py --list
    python src/diff_view.py --branch main
    python src/diff_view.py --goto 75d5f92
"""

import argparse
from pathlib import Path
import sys
import threading
import time
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parent))

from provider.diff_view.server import DiffViewServer
from provider.vcs.git_engine import GitEngine, get_git_root


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for diff viewer launcher."""
    parser = argparse.ArgumentParser(
        description="Quake Diff Viewer & Smartlog VCS Workstation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8767,
        help="Local port number for the diff viewer web dashboard.",
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
        help="Open diff viewer on a specific git branch.",
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

    # Working tree status
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

    # Smartlog DAG commits
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


def main() -> None:
    """Launch the Quake diff viewer CLI or server workstation."""
    args = parse_arguments()
    repo_root = get_git_root()
    engine = GitEngine(repo_root=repo_root)

    if args.sync:
        print(f"\n[Quake VCS] Syncing repository {repo_root.name} from remote...")
        res = engine.fetch_or_pull()
        print(f"Status : {res.get('status')}")
        print(f"Message: {res.get('message')}\n")
        return

    if args.list:
        print_cli_smartlog(engine)
        return

    # Interactive Server Mode
    server = DiffViewServer(
        host=args.host,
        port=args.port,
        repo_root=repo_root,
        initial_branch=args.branch,
        initial_commit=args.goto,
    )
    url = server.get_url()
    curr_branch = engine.get_current_branch()

    banner = rf"""
======================================================================
  QUAKE VCS // DIFF VIEWER & SMARTLOG WORKSTATION v1.0
======================================================================
  * Dashboard URL  : {url}
  * Repository     : {repo_root.name}
  * Active Branch  : {curr_branch}
  * Inter-Tool Hub :
      - Code Review  : http://127.0.0.1:8765
      - Bug Tracker  : http://127.0.0.1:8766
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
        print("\nShutting down Diff Viewer server via interrupt...")
    finally:
        server.server_close()
        print("Diff Viewer server shut down. Terminal released.\n")


if __name__ == "__main__":
    main()
