"""Regression unit test for WORM-016: Privacy, relative paths, and Windows support in hardware repo.

Guards against:
1. Leaking personal information (usernames, local user home directories, personal emails) in git-tracked files.
2. Embedding absolute file URLs or hardcoded local paths in documentation and configs.
3. Leaking personal information in bug and code report feedback and tracebacks across Unix and Windows.
4. Hardcoding personal identifiers in test suites or production code.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from unittest import mock

from model.code_review import CommentModel, ReviewSessionModel, ReviewSeverity, ReviewStatus
from model.bug_report import BugCategory, BugDatabaseModel, BugReportModel, BugSeverity, BugStatus
from provider.code_review.markdown_exporter import MarkdownReviewExporter
from provider.sanitizer import (
    elide_commit_author,
    elide_commit_email,
    elide_personal_info,
    get_author_blacklist,
    get_email_blacklist,
    get_personal_identifiers,
    get_usernames_to_redact,
)
from provider.bug_report.markdown_exporter import MarkdownBugExporter
from provider.vcs.git_engine import GitEngine


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


def test_dynamic_personal_identifiers_discovered() -> None:
    """Verify get_personal_identifiers dynamically derives identifiers without hardcoded data."""
    names, emails, handles = get_personal_identifiers()
    assert isinstance(names, set)
    assert isinstance(emails, set)
    assert isinstance(handles, set)
    # The active user's environment must yield discovered usernames/handles on developer workstations
    usernames = get_usernames_to_redact()
    if not (os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")):
        assert len(usernames) > 0, "Expected at least one discovered username candidate"
        blacklist = get_author_blacklist()
        assert len(blacklist) > 0, "Expected non-empty author blacklist"

    # Verify dynamic derivation successfully derives candidate when a non-reserved user is present
    with mock.patch.dict(os.environ, {"USER": "testdeveloper"}):
        get_personal_identifiers.cache_clear()
        discovered = get_usernames_to_redact()
        assert "testdeveloper" in discovered
        get_personal_identifiers.cache_clear()


def test_no_personal_username_or_email_in_tracked_files() -> None:
    """Verify git tracked files do not contain personal usernames, real names, or personal emails."""
    terms: set[str] = set(get_usernames_to_redact())
    _, emails, _ = get_personal_identifiers()
    for e in emails:
        terms.add(e)

    for term in sorted(terms):
        if len(term) < 4:
            continue
        cmd = ["git", "grep", "-i", "-I", term]
        proc = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True)
        if proc.returncode == 0:
            violations = [
                line
                for line in proc.stdout.splitlines()
                if not any(
                    part in line
                    for part in (
                        "feedback/CR_",
                        "provider/sanitizer.py",
                        "tests/test_privacy_and_relative_paths.py",
                        "attachments/",
                    )
                )
            ]
            assert not violations, f"Found unredacted personal term '{term}' in tracked files:\n" + "\n".join(
                violations
            )


def test_elide_personal_info_tracebacks_and_paths() -> None:
    """Verify elide_personal_info redacts usernames and local home directories on POSIX systems."""
    usernames = sorted([u for u in get_usernames_to_redact() if " " not in u])
    test_user = usernames[0] if usernames else "testuser"
    traceback_sample = f"""
Traceback (most recent call last):
  File "/Users/{test_user}/gh/hardware/src/daemon.py", line 403, in run
    return subprocess.run(cmd, check=True)
  File "/Users/{test_user}/miniforge3/envs/cq/lib/python3.13/site-packages/ocp_vscode/comms.py", line 161, in _send
    stdout, stderr = process.communicate(input, timeout=timeout)
FileNotFoundError: [Errno 2] No such file or directory: 'pytest-of-{test_user}/pytest-473'
"""
    cleaned = elide_personal_info(traceback_sample)
    assert test_user not in cleaned
    assert "/Users/<username>/gh/hardware/src/daemon.py" in cleaned
    assert "pytest-of-<username>/pytest-473" in cleaned

    # Also verify synthetic generic POSIX path
    synthetic_sample = "/Users/synthetic_dev/hardware/src/daemon.py"
    cleaned_syn = elide_personal_info(synthetic_sample)
    assert "/Users/<username>/hardware/src/daemon.py" in cleaned_syn


def test_elide_personal_info_windows_paths() -> None:
    """Verify elide_personal_info redacts Windows paths, backslashes, drive letters, and URLs."""
    usernames = sorted([u for u in get_usernames_to_redact() if " " not in u])
    test_user = usernames[0] if usernames else "winuser"
    win_sample = f"""
Traceback (most recent call last):
  File "C:\\Users\\{test_user}\\gh\\hardware\\src\\main.py", line 12, in <module>
    main()
  File "C:/Users/{test_user}/gh/hardware/src/view.py", line 45, in main
    render()
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\{test_user}\\AppData\\Local\\Temp\\pytest-of-{test_user}\\test1'
Link: file:///C:/Users/{test_user}/gh/hardware/build/board.kicad_pcb
Legacy: D:\\Documents and Settings\\{test_user}\\Desktop\\notes.txt
"""
    cleaned = elide_personal_info(win_sample)
    assert test_user not in cleaned
    assert r"C:\Users\<username>\gh\hardware\src\main.py" in cleaned
    assert "C:/Users/<username>/gh/hardware/src/view.py" in cleaned
    assert r"C:\Users\<username>\AppData\Local\Temp\pytest-of-<username>\test1" in cleaned
    assert "file:///C:/Users/<username>/gh/hardware/build/board.kicad_pcb" in cleaned
    assert r"D:\Documents and Settings\<username>\Desktop\notes.txt" in cleaned


def test_documentation_uses_relative_paths() -> None:
    """Verify documentation files do not contain absolute file:///Users/ links or unredacted names."""
    gemini_file = WORKSPACE_ROOT / "GEMINI.md"
    assert gemini_file.exists(), "GEMINI.md must exist"
    gemini_text = gemini_file.read_text(encoding="utf-8")
    assert "file:///Users/" not in gemini_text
    for term in get_author_blacklist():
        if len(term) >= 4:
            assert term.lower() not in gemini_text.lower(), f"Found personal identifier '{term}' in GEMINI.md"


def test_bug_exporter_automatically_elides_personal_info(tmp_path: Path) -> None:
    """Verify MarkdownBugExporter automatically sanitizes personal info when rendering and exporting."""
    exporter = MarkdownBugExporter(repo_root=tmp_path)
    usernames = list(get_usernames_to_redact())
    test_user = usernames[0] if usernames else "testdev"

    bug = BugReportModel(
        id="BUG-999",
        uuid="99999999-9999-9999-9999-999999999999",
        title="Test Bug with Personal Info",
        status=BugStatus.OPEN,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.PCB,
        description=f"Encountered failure under /Users/{test_user}/gh/hardware/build/board.kicad_pcb",
        reproduction_steps=[f"Run pytest under /private/var/folders/pytest-of-{test_user}/test_1"],
        expected_behavior=f"Expected clean execution without leaking /Users/{test_user} paths",
        actual_behavior=f"Leaked /Users/{test_user}/miniforge3/env",
        logs=f'File "/Users/{test_user}/gh/hardware/src/view.py", line 10',
        resolution_notes=f"Fixed by {test_user}",
    )
    database = BugDatabaseModel(
        title="Privacy Test Database",
        summary=f"Summary mentioning /Users/{test_user}",
        bugs=[bug],
    )

    rendered_bug = exporter.render_bug_markdown(bug)
    assert test_user not in rendered_bug
    assert "<username>" in rendered_bug

    rendered_db = exporter.render_markdown(database)
    assert test_user not in rendered_db
    assert "<username>" in rendered_db

    exported_file = tmp_path / "BUGS.md"
    exporter.export_markdown(database, exported_file, feedback_dir=tmp_path / "feedback")
    content = exported_file.read_text(encoding="utf-8")
    assert test_user not in content
    assert "<username>" in content

    exported_bug_file = tmp_path / "feedback" / "BUG_999.md"
    assert exported_bug_file.exists()
    bug_content = exported_bug_file.read_text(encoding="utf-8")
    assert test_user not in bug_content
    assert "<username>" in bug_content


def test_code_review_exporter_automatically_elides_personal_info(tmp_path: Path) -> None:
    """Verify MarkdownReviewExporter automatically sanitizes personal info when exporting."""
    exporter = MarkdownReviewExporter(repo_root=tmp_path)
    usernames = list(get_usernames_to_redact())
    test_user = usernames[0] if usernames else "testdev"

    session = ReviewSessionModel(
        title="Privacy Review",
        verdict=ReviewStatus.CHANGES_REQUESTED,
        summary=f"Review by {test_user} for /Users/{test_user}/gh/hardware",
        comments=[
            CommentModel(
                id="c99",
                uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                file_path="src/main.py",
                start_line=1,
                end_line=5,
                severity=ReviewSeverity.MUST_FIX,
                body=f"Please check /Users/{test_user}/gh/hardware/src/main.py",
                code_snippet=f"# Author: {test_user}\npath = '/Users/{test_user}'",
                created_at=datetime.now(timezone.utc).isoformat(),
                commit="12345678",
            )
        ],
    )

    rendered_cr = exporter.render_markdown(session)
    assert test_user not in rendered_cr
    assert "<username>" in rendered_cr

    out_file = tmp_path / "CR.md"
    exporter.export_markdown(session, out_file)
    content = out_file.read_text(encoding="utf-8")
    assert test_user not in content
    assert "<username>" in content

    commit_out = exporter.export_commit_markdown(session, "12345678", tmp_path / "feedback")
    assert commit_out is not None and commit_out.exists()
    commit_content = commit_out.read_text(encoding="utf-8")
    assert test_user not in commit_content
    assert "<username>" in commit_content


def test_elide_personal_info_redacts_discovered_names() -> None:
    """Verify elide_personal_info redacts discovered user names and handles."""
    names, _, _ = get_personal_identifiers()
    for name in names:
        if len(name) >= 3:
            sample = f"Customer Name: {name}\nReviewed by {name}."
            cleaned = elide_personal_info(sample)
            assert name not in cleaned
            assert "<username>" in cleaned


def test_elide_commit_author() -> None:
    """Verify elide_commit_author elides personal names and aliases to 'User'."""
    for author in get_author_blacklist():
        assert elide_commit_author(author) == "User"
    assert elide_commit_author("FLINT HEARTH-BINDER") == "FLINT HEARTH-BINDER"
    assert elide_commit_author("Local Working Tree") == "Local Working Tree"
    assert elide_commit_author("") == ""
    assert elide_commit_author(None) == ""


def test_elide_commit_email() -> None:
    """Verify elide_commit_email elides personal email addresses."""
    for email in get_email_blacklist():
        assert elide_commit_email(email) == "user@workspace"
    assert elide_commit_email("randomdeveloper@gmail.com") == "user@workspace"
    assert elide_commit_email("alternate@me.com") == "user@workspace"
    assert elide_commit_email("user@icloud.com") == "user@workspace"
    assert elide_commit_email("local@workspace") == "local@workspace"
    assert elide_commit_email("") == ""
    assert elide_commit_email(None) == ""


def test_git_engine_commits_and_smartlog_elide_personal_identity() -> None:
    """Verify GitEngine.get_commits and get_smartlog_dag elide personal author/email data."""
    engine = GitEngine(repo_root=WORKSPACE_ROOT)
    author_blacklist = {x.lower() for x in get_author_blacklist()}
    email_blacklist = {x.lower() for x in get_email_blacklist()}

    commits = engine.get_commits(limit=50)
    for c in commits:
        assert c.author.lower() not in author_blacklist, (
            f"Found unredacted author '{c.author}' in commit {c.short_hash}"
        )
        assert c.email.lower() not in email_blacklist, f"Found unredacted email '{c.email}' in commit {c.short_hash}"

    nodes = engine.get_smartlog_dag(limit=50)
    for n in nodes:
        assert n.author.lower() not in author_blacklist, (
            f"Found unredacted author '{n.author}' in smartlog node {n.short_hash}"
        )
        assert n.email.lower() not in email_blacklist, (
            f"Found unredacted email '{n.email}' in smartlog node {n.short_hash}"
        )


def test_consignment_guides_elided() -> None:
    """Verify consignment sourcing and shipping guides do not contain unredacted personal names or supplier addresses."""
    guide1 = WORKSPACE_ROOT / "docs" / "consignment_sourcing_and_shipping_guide.md"
    guide2 = WORKSPACE_ROOT / "projects" / "carrier_board" / "docs" / "consignment_sourcing_and_shipping_guide.md"
    for guide in (guide1, guide2):
        assert guide.exists(), f"Guide file {guide} must exist"
        text = guide.read_text(encoding="utf-8")
        assert "[Customer Name]" in text
        assert "[Supplier Delivery Facility Address]" in text
        for term in get_author_blacklist():
            if len(term) >= 4:
                assert term.lower() not in text.lower(), f"Found personal term '{term}' in {guide}"


def test_regression_bug_loamy_bristle_455_elide_address_and_email() -> None:
    """Verify BUG-LOAMY-BRISTLE-455: Privacy sanitizer elides physical addresses and personal emails.

    Guards against:
    1. Leaking user email addresses and consumer domains (@gmail.com, @me.com, etc.).
    2. Leaking physical street addresses, suite/apt numbers, and P.O. Box locations.
    3. Eliding supplier and third-party delivery facility addresses without whitelist.
    4. Mapping user commit handles to 'User' and commit emails to 'user@workspace'.
    """
    # 1. Commit author & email redaction for user handle
    for h in get_author_blacklist():
        assert elide_commit_author(h) == "User"
    for e in get_email_blacklist():
        assert elide_commit_email(e) == "user@workspace"

    # 2. Email redaction in general text / feedback / logs
    sample_text = "Customer email: testuser@gmail.com\nAlternate: developer@me.com\nCompany contact: info@example.com\n"
    sanitized_text = elide_personal_info(sample_text)
    assert "testuser@gmail.com" not in sanitized_text
    assert "developer@me.com" not in sanitized_text
    assert "<email>" in sanitized_text

    # 3. Physical street address & P.O. Box redaction
    addr_samples = [
        "Please send RMA to 123 Main Street, Suite 400, San Francisco, CA 94105.",
        "Shipment returned to P.O. Box 789.",
        "Residential address: 456 Elm Ave, Apt 2B, Springfield, IL 62701.",
        "Office at 742 Evergreen Terrace, Unit 12.",
        "Address: 999 Oak Ridge Blvd, Austin, TX 78701.",
    ]
    for sample in addr_samples:
        cleaned = elide_personal_info(sample)
        assert "<address>" in cleaned, f"Expected '<address>' in: {cleaned} (from: {sample})"

    # 4. Supplier delivery facility address is also elided per review feedback
    factory_addr = (
        "Consignee: PCBWay SMT Assembly Team\n"
        "Address: Building 2, No. 1, Baolong 6th Road, Baolong Community,\n"
        "         Shenzhen, Guangdong, China\n"
        "Postal Code: 518116\n"
    )
    cleaned_factory = elide_personal_info(factory_addr)
    assert "<address>" in cleaned_factory
    assert "<zip>" in cleaned_factory

    # 5. File extensions like .zip should not be mangled as postal/ZIP codes
    file_list_sample = (
        "-gerbers.zip: contains .pcb .pcbdoc .cam .brd and gerber files\n"
        "-bom_templates.zip: contains BOM list for each PCB\n"
        "ZIP Code: 94043\n"
    )
    cleaned_file_list = elide_personal_info(file_list_sample)
    assert "-gerbers.zip: contains .pcb" in cleaned_file_list
    assert "-bom_templates.zip: contains BOM list" in cleaned_file_list
    assert "ZIP Code: <zip>" in cleaned_file_list
