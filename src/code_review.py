"""Interactive Quake-styled Code Review Tool and Markdown Exporter.

Launches a local browser-based review workstation with a Quake retro console UI,
allowing line-by-line diff inspection, inline review feedback, terminal CLI commands,
and automated export to GitHub-flavored Markdown (build/CR.md).

Usage:
    python src/code_review.py [commit1] [commit2] ...
    python src/code_review.py --port 8765 --output build/CR.md
"""

import argparse
from pathlib import Path
import sys
import threading
import time
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model.code_review import CommentModel, ReviewSeverity, ReviewStatus
from provider.code_review.git_utils import GitReviewEngine, extract_line_snippet, get_git_root
from provider.code_review.server import ReviewServer


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for code review launcher.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="GLQuake Code Review Terminal & Markdown Exporter",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "commits",
        nargs="*",
        help="Optional commits, revision hashes, or ranges to inspect (e.g. HEAD~1, 542007d, commit1..commit2).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Local port number for the review web dashboard.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface address to bind.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("build/CR.md"),
        help="Destination markdown file for review findings.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("build/cr_feedback.json"),
        help="Persistent JSON file storing review comments and status.",
    )
    parser.add_argument(
        "--db-file",
        "--sqlite-file",
        dest="db_file",
        type=Path,
        default=Path("build/code_review.sqlite"),
        help="Persistent SQLite database file storing code review session and comments.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Start a fresh review session, discarding previously concluded feedback.",
    )
    parser.add_argument(
        "--browser",
        choices=["vscode", "system", "none"],
        default="vscode",
        help="Target browser environment to display review dashboard (default: vscode).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Disable automatic browser opening on server launch (alias for --browser none).",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Immediately export build/CR.md from existing review state without launching web server.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all active code review comments and file statuses in the terminal.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="When used with --list, only show unresolved comments.",
    )
    parser.add_argument(
        "--add-comment",
        type=str,
        help="Quickly add a review comment with the specified body text.",
    )
    parser.add_argument(
        "--file",
        dest="comment_file",
        type=str,
        default="",
        help="Target file path for quick-added comment.",
    )
    parser.add_argument(
        "--line",
        dest="comment_line",
        type=int,
        default=1,
        help="Line number for quick-added comment.",
    )
    parser.add_argument(
        "--severity",
        choices=[s.value for s in ReviewSeverity],
        default=ReviewSeverity.MUST_FIX.value,
        help="Severity rating for quick-added comment.",
    )
    parser.add_argument(
        "--resolve-comment",
        type=str,
        help="Mark a comment ID as resolved (e.g. --resolve-comment abc123).",
    )
    parser.add_argument(
        "--verdict",
        choices=[s.value for s in ReviewStatus],
        help="Set overall review verdict from CLI.",
    )
    return parser.parse_args()


def launch_browser(url: str, target: str = "vscode") -> None:
    """Open review dashboard URL defaulting to VS Code integrated editor or system browser.

    Args:
        url: The web URL of the review dashboard.
        target: Target browser environment ('vscode', 'system', 'none').
    """
    match target:
        case "none":
            return
        case "vscode":
            # In VS Code, the integrated terminal intercepts localhost links with
            # workbench.externalUriOpeners configured for simpleBrowser.open.
            # We avoid spawning the system browser or the 'code' binary (which treats
            # web URLs as filenames and opens an empty text buffer).
            return
        case "system":
            webbrowser.open(url)
        case _:
            webbrowser.open(url)


def main() -> None:
    """Run code review server or perform direct CLI actions."""
    args = parse_arguments()
    repo_root = get_git_root()

    output_path = args.output if args.output.is_absolute() else (repo_root / args.output)
    state_path = args.state_file if args.state_file.is_absolute() else (repo_root / args.state_file)
    db_path = args.db_file if args.db_file.is_absolute() else (repo_root / args.db_file)

    git_engine = GitReviewEngine(repo_root=repo_root)
    if not args.commits:
        if git_engine.has_working_tree_changes():
            revisions = ["working"]
        else:
            revisions = ["HEAD"]
    else:
        try:
            revisions = git_engine.resolve_revisions(args.commits)
        except ValueError as err:
            print(f"Error resolving revisions: {err}", file=sys.stderr)
            sys.exit(1)

    is_cli_only = bool(args.list or args.add_comment or args.resolve_comment or args.verdict or args.export_only)

    server = ReviewServer(
        host=args.host,
        port=args.port,
        repo_root=repo_root,
        markdown_output=output_path,
        state_file=state_path,
        sqlite_file=db_path,
        revisions=revisions,
        fresh=args.fresh,
        bind_and_activate=not is_cli_only,
    )

    if args.add_comment:
        if not args.comment_file:
            print("Error: --file is required when adding a comment.", file=sys.stderr)
            sys.exit(1)
        import uuid
        from datetime import datetime, timezone

        snippet = extract_line_snippet(
            file_path=args.comment_file,
            start_line=args.comment_line,
            end_line=args.comment_line,
            commit=revisions[0] if revisions else "working",
            repo_root=repo_root,
        )
        comment = CommentModel(
            id=uuid.uuid4().hex[:12],
            file_path=args.comment_file,
            start_line=args.comment_line,
            end_line=args.comment_line,
            severity=ReviewSeverity(args.severity),
            body=args.add_comment,
            author="Reviewer",
            code_snippet=snippet,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        server.session.comments.append(comment)
        server.session.auto_update_status_on_comment()
        server.save_and_sync()
        print(f"Added comment [{comment.id}] on {comment.file_path}:{comment.start_line} [{comment.severity.value}]")
        return

    if args.resolve_comment:
        target_c = None
        for c in server.session.comments:
            if c.id == args.resolve_comment:
                c.resolved = True
                target_c = c
                break
        if not target_c:
            print(f"Comment '{args.resolve_comment}' not found.", file=sys.stderr)
            sys.exit(1)
        server.save_and_sync()
        print(f"Resolved comment [{target_c.id}] on {target_c.file_path}:{target_c.start_line}")
        return

    if args.verdict:
        server.session.verdict = ReviewStatus(args.verdict)
        server.save_and_sync()
        print(f"Updated review verdict to: {server.session.verdict.value}")
        return

    if args.list:
        print("\n=== Code Review Session ===")
        print(f"  Title:   {server.session.title}")
        print(f"  Verdict: {server.session.verdict.value}")
        counts = server.session.count_by_severity()
        print(
            f"  Findings: {len(server.session.comments)} total "
            f"({counts.get('MUST_FIX', 0)} MUST_FIX, {counts.get('PROPOSAL', 0)} PROPOSAL, {counts.get('NIT', 0)} NIT)"
        )
        if not server.session.comments:
            print("  No comments registered.")
        else:
            comments = [c for c in server.session.comments if not args.open or not c.resolved]
            for c in comments:
                chk = "[X]" if c.resolved else "[ ]"
                summary_line = c.body.splitlines()[0] if c.body else ""
                print(f"  {chk} [{c.id}] [{c.severity.value}] {c.file_path}:{c.start_line} -> {summary_line}")
            total_open = sum(1 for c in server.session.comments if not c.resolved)
            print(
                f"\nShowing {len(comments)} comments ({total_open} unresolved, {len(server.session.comments)} total)."
            )
        print()
        return

    if args.export_only:
        saved_md = server.save_and_sync()
        print(f"Exported code review markdown report to: {saved_md}")
        return

    # Initial sync to ensure build/CR.md exists immediately
    server.save_and_sync()
    url = server.get_url()

    if args.commits:
        if len(args.commits) == 1 and ".." in args.commits[0]:
            rev_desc = f"{args.commits[0]} ({len(revisions)} commits)"
        else:
            rev_desc = ", ".join(args.commits)
    else:
        rev_desc = "Working Tree / Recent Commits"

    banner = r"""
======================================================================
  GLQUAKE CODE REVIEW TERMINAL // HUD v1.09
======================================================================
  * Dashboard URL  : {url}
  * Markdown Target: {output}
  * Revisions      : {revs}
  * Target Browser : {browser}
  * Press [Ctrl+C] to conclude session and shut down server.
======================================================================
  ➜ In VS Code: [Cmd+Click] the Dashboard URL above to open inside
    the integrated Simple Browser (or press [F5] / run Task).
======================================================================
""".format(
        url=url,
        output=output_path,
        revs=rev_desc,
        browser="VS Code (Integrated Simple Browser)" if args.browser == "vscode" else args.browser.upper(),
    )
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
        print("\nConcluding code review session via interrupt...")
    finally:
        final_md = server.save_and_sync()
        server.server_close()
        verdict_str = server.session.verdict.value if server.session else "IN_REVIEW"
        print(f"\n[REVIEW CONCLUDED] Overall Verdict: [{verdict_str}]")
        print(f"Final review findings exported to: {final_md}")
        print("Review server shut down. Terminal released.\n")


if __name__ == "__main__":
    main()
