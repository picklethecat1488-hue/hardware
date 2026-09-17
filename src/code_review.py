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

from provider.code_review.git_utils import GitReviewEngine, get_git_root
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
    """Run code review server or perform direct markdown export."""
    args = parse_arguments()
    repo_root = get_git_root()

    output_path = args.output if args.output.is_absolute() else (repo_root / args.output)
    state_path = args.state_file if args.state_file.is_absolute() else (repo_root / args.state_file)

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

    server = ReviewServer(
        host=args.host,
        port=args.port,
        repo_root=repo_root,
        markdown_output=output_path,
        state_file=state_path,
        revisions=revisions,
        fresh=args.fresh,
    )

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
