"""Unit and regression tests for Bug Report CLI, models, and markdown tracker."""

import json
from pathlib import Path
import pytest

from model.bug_report import (
    BugAttachmentModel,
    BugCategory,
    BugDatabaseModel,
    BugReportModel,
    BugSeverity,
    BugStatus,
)
from provider.bug_report.markdown_exporter import MarkdownBugExporter
from provider.bug_report.server import BugReportRequestHandler, BugReportServer
from provider.bug_report.sqlite_store import SQLiteBugStore


def test_bug_report_model_lifecycle() -> None:
    """Verify bug report model instantiation, validation, and status transitions."""
    bug = BugReportModel(
        id="BUG-101",
        title="Test Bug",
        status=BugStatus.OPEN,
        severity=BugSeverity.HIGH,
        category=BugCategory.PCB,
        component="test_component",
        description="Detailed failure description",
        reproduction_steps=["step 1", "step 2"],
        expected_behavior="Expected outcome",
        actual_behavior="Actual outcome",
        logs="Sample error logs",
        attachments=[
            BugAttachmentModel(
                id="att-1",
                filename="test.png",
                file_type="screenshot",
                file_path="build/test.png",
                description="Test preview",
            )
        ],
    )
    assert bug.id == "BUG-101"
    assert bug.status == BugStatus.OPEN
    assert bug.severity == BugSeverity.HIGH
    assert len(bug.attachments) == 1
    assert bug.attachments[0].filename == "test.png"

    # Test serialization
    data = bug.model_dump(mode="json")
    assert data["id"] == "BUG-101"
    assert data["severity"] == "HIGH"

    restored = BugReportModel.model_validate(data)
    assert restored.id == bug.id
    assert restored.category == BugCategory.PCB


def test_bug_database_metrics_and_management(tmp_path: Path) -> None:
    """Verify bug collection aggregation, ID generation, and markdown export."""
    db = BugDatabaseModel(title="Unit Test Tracker")
    assert db.generate_bug_id() == "BUG-001"

    b1 = BugReportModel(
        id="BUG-001",
        title="First defect",
        status=BugStatus.OPEN,
        severity=BugSeverity.CRITICAL,
        category=BugCategory.CAD,
    )
    b2 = BugReportModel(
        id="BUG-002",
        title="Second defect",
        status=BugStatus.RESOLVED,
        severity=BugSeverity.LOW,
        category=BugCategory.PCB,
    )
    db.add_or_update(b1)
    db.add_or_update(b2)

    assert db.generate_bug_id() == "BUG-003"
    assert db.count_by_status()[BugStatus.OPEN.value] == 1
    assert db.count_by_status()[BugStatus.RESOLVED.value] == 1
    assert db.count_by_severity()[BugSeverity.CRITICAL.value] == 1
    assert db.count_by_category()[BugCategory.CAD.value] == 1
    assert db.count_by_category()[BugCategory.PCB.value] == 1

    # Export to markdown and JSON
    exporter = MarkdownBugExporter(repo_root=tmp_path)
    md_file = tmp_path / "BUGS.md"
    json_file = tmp_path / "bugs_state.json"

    saved_md = exporter.export_markdown(db, md_file)
    assert saved_md.exists()
    content = saved_md.read_text(encoding="utf-8")
    assert "# Bug Report Tracker: Unit Test Tracker" in content
    assert "[BUG-001]" in content
    assert "[BUG-002]" in content
    assert "CRITICAL" in content

    saved_json = exporter.export_state_json(db, json_file)
    assert saved_json.exists()
    loaded_db = exporter.load_state_json(saved_json)
    assert loaded_db is not None
    assert len(loaded_db.bugs) == 2


def test_bug_report_server_initialization(tmp_path: Path) -> None:
    """Verify BugReportServer initialization, state loading, and persistence."""
    md_file = tmp_path / "BUGS.md"
    json_file = tmp_path / "bugs_state.json"

    server = BugReportServer(
        host="127.0.0.1",
        port=8799,
        repo_root=tmp_path,
        markdown_output=md_file,
        state_file=json_file,
        fresh=True,
    )
    assert server.database.title == "Hardware Bug Tracker"
    assert len(server.database.bugs) == 0

    # Add bug and sync
    bug = BugReportModel(
        id="BUG-001",
        title="Server test bug",
        status=BugStatus.OPEN,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.UI,
    )
    server.database.add_or_update(bug)
    server.save_and_sync()

    assert md_file.exists()
    assert json_file.exists()
    server.server_close()

    # Re-initialize without fresh to ensure persistence reload
    reloaded_server = BugReportServer(
        host="127.0.0.1",
        port=8799,
        repo_root=tmp_path,
        markdown_output=md_file,
        state_file=json_file,
        fresh=False,
    )
    assert len(reloaded_server.database.bugs) == 1
    assert reloaded_server.database.bugs[0].id == "BUG-001"
    reloaded_server.server_close()


def test_bug_report_server_api_exit_and_document_upload(tmp_path: Path) -> None:
    """Verify BugReportServer document upload handling and exit endpoint."""
    import base64
    import threading
    import urllib.request

    md_file = tmp_path / "BUGS.md"
    json_file = tmp_path / "bugs_state.json"
    att_dir = tmp_path / "attachments"

    server = BugReportServer(
        host="127.0.0.1",
        port=8798,
        repo_root=tmp_path,
        markdown_output=md_file,
        state_file=json_file,
        attachments_dir=att_dir,
        fresh=True,
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        # Test document upload via /api/upload
        doc_content = b"%PDF-1.4 Mock PDF Content"
        b64_doc = base64.b64encode(doc_content).decode("ascii")
        req_data = json.dumps(
            {
                "filename": "test_spec.pdf",
                "file_type": "document",
                "content_base64": b64_doc,
                "description": "Pasted specification document",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{server.get_url()}/api/upload",
            data=req_data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["filename"] == "test_spec.pdf"
            assert res["file_type"] == "document"
            assert (att_dir / "test_spec.pdf").exists()

        # Test /api/exit endpoint
        exit_req = urllib.request.Request(
            f"{server.get_url()}/api/exit",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(exit_req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "saved_and_exited"

        t.join(timeout=2.0)
    finally:
        server.server_close()


def test_sqlite_bug_store_lifecycle(tmp_path: Path) -> None:
    """Verify SQLiteBugStore schema initialization, atomic upsert, query, and cascade delete."""
    db_file = tmp_path / "bugs.sqlite"
    store = SQLiteBugStore(db_file)
    assert db_file.exists()

    # 1. Test empty database load
    db = store.load_database()
    assert db.title == "Hardware Engineering Bug Tracker"
    assert len(db.bugs) == 0

    # 2. Add bug with attachment and reproduction steps
    att = BugAttachmentModel(
        id="att-001",
        filename="schematic_error.png",
        file_type="screenshot",
        file_path="build/attachments/schematic_error.png",
        size_bytes=1024,
        description="Error screenshot",
        created_at="2026-09-20 12:00:00 UTC",
    )
    bug = BugReportModel(
        id="BUG-001",
        title="Sample Defect",
        status=BugStatus.OPEN,
        severity=BugSeverity.HIGH,
        category=BugCategory.PCB,
        component="carrier_board",
        description="Trace clearance violation",
        reproduction_steps=["Open schematic", "Run DRC"],
        expected_behavior="0 errors",
        actual_behavior="1 error",
        logs="Error log output",
        attachments=[att],
        created_at="2026-09-20 12:00:00 UTC",
        updated_at="2026-09-20 12:00:00 UTC",
    )
    db.add_or_update(bug)
    store.save_database(db)

    # 3. Reload and assert all data preserved
    reloaded = store.load_database()
    assert len(reloaded.bugs) == 1
    b = reloaded.get_bug("BUG-001")
    assert b is not None
    assert b.title == "Sample Defect"
    assert b.status == BugStatus.OPEN
    assert b.severity == BugSeverity.HIGH
    assert b.reproduction_steps == ["Open schematic", "Run DRC"]
    assert len(b.attachments) == 1
    assert b.attachments[0].filename == "schematic_error.png"

    # 4. Update status and notes
    b.status = BugStatus.RESOLVED
    b.resolution_notes = "Rerouted trace on F.Cu"
    b.resolved_at = "2026-09-20 12:30:00 UTC"
    store.save_bug(b)

    reloaded2 = store.load_database()
    b2 = reloaded2.get_bug("BUG-001")
    assert b2 is not None
    assert b2.status == BugStatus.RESOLVED
    assert b2.resolution_notes == "Rerouted trace on F.Cu"

    # 5. Test JSON export and import round trip
    json_path = tmp_path / "exported.json"
    store.export_to_json(json_path)
    assert json_path.exists()

    db_file2 = tmp_path / "imported.sqlite"
    store2 = SQLiteBugStore(db_file2)
    imported = store2.import_from_json(json_path)
    assert len(imported.bugs) == 1
    assert imported.bugs[0].id == "BUG-001"

    # 6. Delete bug
    store.delete_bug("BUG-001")
    reloaded3 = store.load_database()
    assert len(reloaded3.bugs) == 0


def test_server_sqlite_integration(tmp_path: Path) -> None:
    """Verify BugReportServer seamlessly syncs between SQLite backing store, JSON, and Markdown."""
    sqlite_file = tmp_path / "bugs.sqlite"
    state_file = tmp_path / "bugs_state.json"
    md_file = tmp_path / "BUGS.md"

    server = BugReportServer(
        repo_root=tmp_path,
        sqlite_file=sqlite_file,
        state_file=state_file,
        markdown_output=md_file,
        bind_and_activate=False,
    )

    # 1. Add a bug through server database
    bug = BugReportModel(
        id="BUG-069",
        title="SQLite Backing Store Verification",
        status=BugStatus.OPEN,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.INFRASTRUCTURE,
        description="Verify SQLite database integration",
    )
    server.database.add_or_update(bug)
    server.save_and_sync()

    # 2. Verify files created and synced
    assert sqlite_file.exists()
    assert state_file.exists()
    assert md_file.exists()

    # 3. Spawn a new server instance pointing to the same SQLite store
    server2 = BugReportServer(
        repo_root=tmp_path,
        sqlite_file=sqlite_file,
        state_file=state_file,
        markdown_output=md_file,
        bind_and_activate=False,
    )
    loaded_bug = server2.database.get_bug("BUG-069")
    assert loaded_bug is not None
    assert loaded_bug.title == "SQLite Backing Store Verification"
    assert loaded_bug.status == BugStatus.OPEN


def test_regression_bug_076_feedback_tools_sqlite_only():
    """Verify BUG-076: remove references to markdown and state files from dashboard.py."""
    import subprocess
    import sys

    # Check dashboard.py --help
    res = subprocess.run([sys.executable, "src/dashboard.py", "--help"], capture_output=True, text=True, check=True)
    assert "--output" not in res.stdout, "dashboard.py should not have --output flag"
    assert "--state-file" not in res.stdout, "dashboard.py should not have --state-file flag"
    assert "BUGS.md" not in res.stdout, "dashboard.py should not reference BUGS.md"
    assert "bugs_state.json" not in res.stdout, "dashboard.py should not reference bugs_state.json"
    assert "CR.md" not in res.stdout, "dashboard.py should not reference CR.md"
    assert "cr_feedback.json" not in res.stdout, "dashboard.py should not reference cr_feedback.json"


def test_regression_bug_079_no_duplicate_bug_ids_and_generator():
    """Verify BUG-079: bug report workstation does not generate duplicate bug IDs using bugs.length."""
    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    template_file = templates_dir / "bug_report.html.j2"
    assert template_file.exists()
    content = template_file.read_text(encoding="utf-8")

    # 1. Frontend template must NOT generate bug ID using db.bugs.length + 1
    assert "db.bugs.length + 1" not in content, (
        "Frontend bug_report.html.j2 must not generate bug IDs from db.bugs.length + 1 as missing IDs cause collisions"
    )

    # 2. Frontend must define generateNextBugId using max ID index
    assert "generateNextBugId" in content, (
        "Frontend bug_report.html.j2 must define generateNextBugId calculating max bug index"
    )

    # 3. Backend BugDatabaseModel must correctly skip to max + 1 when IDs are non-contiguous
    db = BugDatabaseModel(title="Non-contiguous test")
    db.bugs = [
        BugReportModel(
            id="BUG-001", title="B1", status=BugStatus.OPEN, severity=BugSeverity.LOW, category=BugCategory.PCB
        ),
        BugReportModel(
            id="BUG-002", title="B2", status=BugStatus.OPEN, severity=BugSeverity.LOW, category=BugCategory.PCB
        ),
        BugReportModel(
            id="BUG-078", title="B78", status=BugStatus.OPEN, severity=BugSeverity.LOW, category=BugCategory.PCB
        ),
    ]
    # Length is 3, but max is 78. Next ID MUST be BUG-079, NOT BUG-004
    assert db.generate_bug_id() == "BUG-079"


def test_regression_bug_114_rmw_markdown_sync_and_file_watch(tmp_path: Path) -> None:
    """Verify BUG-114: bug report tool uses R+M+W to sync BUGS.md changes into SQLite and database."""
    sqlite_file = tmp_path / "bugs.sqlite"
    state_file = tmp_path / "bugs_state.json"
    md_file = tmp_path / "BUGS.md"

    server = BugReportServer(
        repo_root=tmp_path,
        sqlite_file=sqlite_file,
        state_file=state_file,
        markdown_output=md_file,
        bind_and_activate=False,
    )

    # 1. Add initial bug and save
    b1 = BugReportModel(
        id="BUG-001",
        title="Initial defect",
        status=BugStatus.OPEN,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.PCB,
        description="Original description",
    )
    server.database.add_or_update(b1)
    server.save_and_sync()

    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "- [ ]" in content

    # 2. Simulate external user editing BUGS.md:
    # Check off BUG-001 as resolved, add resolution notes, and add a new BUG-002
    updated_content = content.replace("- [ ]", "- [x]")
    updated_content = updated_content.replace(
        "- **Status**: `OPEN`", "- **Status**: `RESOLVED`\n- **Resolved**: `2026-09-25 02:00:00 UTC`"
    )
    updated_content += (
        '\n\n### <a id="bug-002"></a> 🔴 `[BUG-002]` New issue added via markdown\n\n'
        "- **Status**: `OPEN`\n- **Severity**: `HIGH`\n- **Category**: `CAD`\n\n"
        "#### Description\n\nAdded directly to BUGS.md\n\n---\n"
    )
    md_file.write_text(updated_content, encoding="utf-8")

    # 3. Perform R+M+W sync
    server.sync_with_markdown()

    # 4. Verify in-memory database and SQLite store picked up external BUGS.md changes
    b1_updated = server.database.get_bug("BUG-001")
    assert b1_updated is not None
    assert b1_updated.status == BugStatus.RESOLVED

    b2_added = server.database.get_bug("BUG-002")
    assert b2_added is not None
    assert b2_added.title == "New issue added via markdown"
    assert b2_added.severity == BugSeverity.HIGH

    # Verify SQLite was updated
    sqlite_db = server.sqlite_store.load_database()
    assert sqlite_db.get_bug("BUG-001").status == BugStatus.RESOLVED
    assert sqlite_db.get_bug("BUG-002") is not None


def test_regression_bug_169_git_lfs_tracking_and_policy() -> None:
    """Verify BUG-169: Git LFS tracking for bug report attachments and public attachments documentation."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    gitattributes_file = repo_root / ".gitattributes"
    assert gitattributes_file.exists(), ".gitattributes must exist"
    ga_content = gitattributes_file.read_text(encoding="utf-8")
    assert "attachments/* filter=lfs diff=lfs merge=lfs -text" in ga_content
    assert "build/attachments/* filter=lfs diff=lfs merge=lfs -text" in ga_content
    assert "feedback/attachments/* filter=lfs diff=lfs merge=lfs -text" in ga_content

    # Check CONTRIBUTING.md
    contrib_file = repo_root / "CONTRIBUTING.md"
    assert contrib_file.exists()
    contrib_text = contrib_file.read_text(encoding="utf-8")
    assert "GitHub LFS" in contrib_text or "Git LFS" in contrib_text
    assert "non-confidential" in contrib_text

    # Check GEMINI.md
    gemini_file = repo_root / "GEMINI.md"
    assert gemini_file.exists()
    gemini_text = gemini_file.read_text(encoding="utf-8")
    assert "GitHub LFS" in gemini_text or "Git LFS" in gemini_text
    assert "non-confidential" in gemini_text

    # Check bug_report template
    template_file = repo_root / "src" / "provider" / "templates" / "bug_report.html.j2"
    tpl_text = template_file.read_text(encoding="utf-8")
    assert "attachment-lfs-notice" in tpl_text
    assert "GitHub LFS" in tpl_text


def test_regression_bug_170_feedback_dir_watch_and_resolution_preservation(tmp_path: Path) -> None:
    """Verify BUG-170: Feedback directory watch detects external bug resolution and preserves resolution on Save."""
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir(parents=True)
    db_file = tmp_path / "bugs.sqlite"
    state_file = tmp_path / "bugs_state.json"
    md_file = feedback_dir / "BUGS.md"

    server = BugReportServer(
        repo_root=tmp_path,
        feedback_dir=feedback_dir,
        sqlite_file=db_file,
        state_file=state_file,
        markdown_output=md_file,
        bind_and_activate=False,
    )

    # 1. Add bug 166 as OPEN
    b166 = BugReportModel(
        id="BUG-166",
        title="Silkscreen text is mirrored",
        status=BugStatus.OPEN,
        severity=BugSeverity.HIGH,
        category=BugCategory.PCB,
        description="F.SilkS text is vertically flipped",
    )
    server.database.add_or_update(b166)
    server.save_and_sync()

    bug166_md = feedback_dir / "BUG_166.md"
    assert bug166_md.exists()
    assert "- **Status**: `OPEN`" in bug166_md.read_text(encoding="utf-8")

    # 2. Simulate external resolution of BUG-166 in feedback/BUG_166.md
    # (e.g. by agent turn, git commit, or external edit)
    import time

    time.sleep(0.05)  # Ensure distinct mtime
    resolved_md_content = (
        "# 🟢 `[BUG-166]` Silkscreen text is mirrored\n\n"
        f"- **UUID**: `{b166.uuid}`\n"
        "- **ID**: `BUG-166`\n"
        "- **Status**: `RESOLVED`\n"
        "- **Severity**: `HIGH`\n"
        "- **Category**: `PCB`\n"
        "- **Created**: `2026-09-25 10:00:00 UTC`\n"
        "- **Resolved**: `2026-09-28 01:00:00 UTC`\n\n"
        "#### Resolution\n\n"
        "Corrected UV coordinate mapping in bullet.py and removed mirror flag in KiCad exporter.\n\n"
        "#### Description\n\n"
        "F.SilkS text is vertically flipped\n"
    )
    bug166_md.write_text(resolved_md_content, encoding="utf-8")

    # 3. Trigger file watch check (called automatically on any incoming GET/POST or watcher loop)
    assert server.check_file_watch() is True

    # Verify BUG-166 is now RESOLVED in server memory and SQLite
    reloaded_b166 = server.database.get_bug("BUG-166")
    assert reloaded_b166 is not None
    assert reloaded_b166.status == BugStatus.RESOLVED
    assert "bullet.py" in reloaded_b166.resolution_notes

    # 4. User adds and saves another bug in the bug report tool (the action that previously caused BUG-166 to lose resolution)
    handler = BugReportRequestHandler.__new__(BugReportRequestHandler)
    handler.server = server
    handler._send_json = lambda *args, **kwargs: None
    handler._handle_save_bug(
        {
            "title": "New Bug 177",
            "status": "OPEN",
            "severity": "MEDIUM",
            "category": "CAD",
            "description": "Enclosure fitment feedback",
        }
    )

    # 5. Assert BUG-166 REMAINS RESOLVED across memory, markdown, and SQLite
    final_b166 = server.database.get_bug("BUG-166")
    assert final_b166.status == BugStatus.RESOLVED
    assert "- **Status**: `RESOLVED`" in bug166_md.read_text(encoding="utf-8")
    assert server.sqlite_store.load_database().get_bug("BUG-166").status == BugStatus.RESOLVED


def test_regression_bug_172_vertical_text_panel_and_cli_expansion() -> None:
    """Verify BUG-172: Allow text panels in bug report tool and CLI console in code review tool to extend vertically."""
    repo_root = Path(__file__).resolve().parent.parent.parent

    # 1. Verify code_review.html.j2 has vertical CLI console resizing
    cr_template = (repo_root / "src" / "provider" / "templates" / "code_review.html.j2").read_text(encoding="utf-8")
    assert "cli-resizer" in cr_template
    assert "cliResizer" in cr_template
    assert "setupCliResizer" in cr_template
    assert "cursor: ns-resize" in cr_template

    # 2. Verify bug_report.html.j2 has vertical text panel expansion
    br_template = (repo_root / "src" / "provider" / "templates" / "bug_report.html.j2").read_text(encoding="utf-8")
    assert "panel-expand-btn" in br_template
    assert "expanded-vertical" in br_template
    assert "toggleExpandPanel" in br_template
    assert "resize: both" in br_template or "resize: vertical" in br_template


def test_regression_bug_181_no_file_descriptor_leak_in_sqlite_and_server(tmp_path: Path) -> None:
    """Verify BUG-181: SQLite stores, markdown exporter, and server do not leak file descriptors."""
    import os
    import time

    db_file = tmp_path / "bugs.sqlite"
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir()
    md_file = tmp_path / "BUGS.md"
    state_file = tmp_path / "bugs_state.json"

    def get_open_fd_count() -> int:
        fd_dir = Path("/dev/fd") if Path("/dev/fd").exists() else Path("/proc/self/fd")
        if fd_dir.exists():
            try:
                return len(os.listdir(str(fd_dir)))
            except OSError:
                return 0
        return 0

    # 1. Test SQLiteBugStore connection closure across repeated operations
    store = SQLiteBugStore(db_file)
    initial_db = BugDatabaseModel(
        title="FD Leak Test Tracker",
        summary="Testing FD leak resistance",
        bugs=[
            BugReportModel(
                id=f"BUG-{i:03d}",
                title=f"Bug {i}",
                status=BugStatus.OPEN,
                severity=BugSeverity.MEDIUM,
                category=BugCategory.INFRASTRUCTURE,
                description=f"Description for bug {i}",
            )
            for i in range(1, 20)
        ],
    )
    store.save_database(initial_db)

    import gc

    gc.collect()
    baseline_fds = get_open_fd_count()
    if baseline_fds > 0:
        for _ in range(50):
            loaded = store.load_database()
            store.save_database(loaded)
        gc.collect()
        after_sqlite_fds = get_open_fd_count()
        assert after_sqlite_fds <= baseline_fds + 5, (
            f"SQLiteBugStore leaked file descriptors: baseline={baseline_fds}, after={after_sqlite_fds}"
        )

    # 2. Test MarkdownBugExporter does not re-write identical bug files
    exporter = MarkdownBugExporter(repo_root=tmp_path)
    test_bug = initial_db.bugs[0]
    out_file = exporter.export_individual_bug(test_bug, feedback_dir)
    assert out_file.exists()
    initial_mtime = out_file.stat().st_mtime_ns

    time.sleep(0.01)
    out_file_2 = exporter.export_individual_bug(test_bug, feedback_dir)
    assert out_file_2 == out_file
    second_mtime = out_file_2.stat().st_mtime_ns
    assert second_mtime == initial_mtime, "export_individual_bug must not rewrite identical file contents"

    # 3. Test BugReportServer save_and_sync and check_file_watch do not leak FDs
    server = BugReportServer(
        host="127.0.0.1",
        port=8766,
        repo_root=tmp_path,
        markdown_output=md_file,
        feedback_dir=feedback_dir,
        state_file=state_file,
        sqlite_file=db_file,
        bind_and_activate=False,
    )

    try:
        import gc

        gc.collect()
        baseline_server_fds = get_open_fd_count()
        if baseline_server_fds > 0:
            for _ in range(20):
                server.save_and_sync()
                server.check_file_watch()
            gc.collect()
            after_server_fds = get_open_fd_count()
            assert after_server_fds <= baseline_server_fds + 5, (
                f"BugReportServer leaked file descriptors: baseline={baseline_server_fds}, after={after_server_fds}"
            )
    finally:
        server.server_close()


def test_regression_bug_186_bug_report_server_attachments_dir(tmp_path: Path) -> None:
    """Verify BUG-186: BugReportServer defaults attachments directory to attachments/."""
    server = BugReportServer(
        host="127.0.0.1",
        port=8766,
        repo_root=tmp_path,
        markdown_output=tmp_path / "BUGS.md",
        feedback_dir=tmp_path / "feedback",
        state_file=tmp_path / "bugs_state.json",
        sqlite_file=tmp_path / "bugs.sqlite",
        bind_and_activate=False,
    )
    assert server.attachments_dir == tmp_path / "attachments"


def test_regression_bug_264_recreate_db_after_build_dir_removed(tmp_path: Path) -> None:
    """Verify BUG-264: SQLite stores seamlessly recover and recreate schema after build directory removal."""
    import shutil

    build_dir = tmp_path / "build"
    db_file = build_dir / "bugs.sqlite"
    store = SQLiteBugStore(db_file)
    store.save_bug(
        BugReportModel(
            id="BUG-001",
            title="Test Bug",
            status=BugStatus.OPEN,
            severity=BugSeverity.MEDIUM,
            category=BugCategory.INFRASTRUCTURE,
        )
    )
    assert db_file.exists()

    # Simulate rm -rf build/
    shutil.rmtree(build_dir)
    assert not build_dir.exists()

    # Saving/loading on the store must recreate directory and schema without OperationalError
    store.save_bug(
        BugReportModel(
            id="BUG-002",
            title="New Bug",
            status=BugStatus.OPEN,
            severity=BugSeverity.MEDIUM,
            category=BugCategory.INFRASTRUCTURE,
        )
    )
    assert db_file.exists()
    db = store.load_database()
    assert any(b.id == "BUG-002" for b in db.bugs)


def test_regression_bug_269_scoped_attachments_same_filename(tmp_path: Path) -> None:
    """Verify BUG-269: Encode attachments scoped by bug ID so multiple bugs can have attachments with the same name."""
    import threading
    import urllib.request

    att_dir = tmp_path / "attachments"
    md_file = tmp_path / "BUGS.md"
    fb_dir = tmp_path / "feedback"
    db_file = tmp_path / "bugs.sqlite"
    json_file = tmp_path / "bugs_state.json"

    server = BugReportServer(
        host="127.0.0.1",
        port=0,
        repo_root=tmp_path,
        feedback_dir=fb_dir,
        markdown_output=md_file,
        state_file=json_file,
        sqlite_file=db_file,
        attachments_dir=att_dir,
        fresh=True,
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        base_url = server.get_url()

        # 1. Upload daemon.log for BUG-268
        payload_268 = json.dumps(
            {
                "bug_id": "BUG-268",
                "filename": "daemon.log",
                "file_type": "document",
                "content_text": "daemon log for bug 268",
                "description": "Build log for BUG-268",
            }
        ).encode("utf-8")
        req1 = urllib.request.Request(
            f"{base_url}/api/upload",
            data=payload_268,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req1) as resp:
            assert resp.status == 200
            res1 = json.loads(resp.read().decode("utf-8"))
            assert res1["filename"] == "daemon.log"
            assert res1["file_path"] == "attachments/BUG-268/daemon.log"

        file_268 = att_dir / "BUG-268" / "daemon.log"
        assert file_268.exists()
        assert file_268.read_text(encoding="utf-8") == "daemon log for bug 268"

        # 2. Upload another attachment with the EXACT SAME filename daemon.log for BUG-269
        payload_269 = json.dumps(
            {
                "bug_id": "BUG-269",
                "filename": "daemon.log",
                "file_type": "document",
                "content_text": "daemon log for bug 269",
                "description": "Build log for BUG-269",
            }
        ).encode("utf-8")
        req2 = urllib.request.Request(
            f"{base_url}/api/upload",
            data=payload_269,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req2) as resp:
            assert resp.status == 200
            res2 = json.loads(resp.read().decode("utf-8"))
            assert res2["filename"] == "daemon.log"
            assert res2["file_path"] == "attachments/BUG-269/daemon.log"

        file_269 = att_dir / "BUG-269" / "daemon.log"
        assert file_269.exists()
        assert file_269.read_text(encoding="utf-8") == "daemon log for bug 269"

        # 3. Assert BUG-268 attachment was NOT overwritten
        assert file_268.read_text(encoding="utf-8") == "daemon log for bug 268"

        # 4. Verify HTTP serving of both attachments
        with urllib.request.urlopen(f"{base_url}/attachments/BUG-268/daemon.log") as resp:
            assert resp.status == 200
            assert resp.read() == b"daemon log for bug 268"

        with urllib.request.urlopen(f"{base_url}/attachments/BUG-269/daemon.log") as resp:
            assert resp.status == 200
            assert resp.read() == b"daemon log for bug 269"

        # 5. Verify database and markdown round trip for both bugs
        b268 = BugReportModel(
            id="BUG-268",
            title="Bug 268",
            status=BugStatus.RESOLVED,
            severity=BugSeverity.MEDIUM,
            category=BugCategory.GENERAL,
            attachments=[BugAttachmentModel.model_validate(res1)],
        )
        b269 = BugReportModel(
            id="BUG-269",
            title="Bug 269",
            status=BugStatus.OPEN,
            severity=BugSeverity.LOW,
            category=BugCategory.INFRASTRUCTURE,
            attachments=[BugAttachmentModel.model_validate(res2)],
        )
        server.database.add_or_update(b268)
        server.database.add_or_update(b269)
        server.save_and_sync()

        # Check markdown export
        md_268 = fb_dir / "BUG_268.md"
        md_269 = fb_dir / "BUG_269.md"
        assert md_268.exists()
        assert md_269.exists()
        assert "[daemon.log](attachments/BUG-268/daemon.log)" in md_268.read_text(encoding="utf-8")
        assert "[daemon.log](attachments/BUG-269/daemon.log)" in md_269.read_text(encoding="utf-8")

        # Check round-trip parsing from markdown
        parsed_268 = server.exporter.parse_individual_bug_file(md_268)
        assert parsed_268 is not None
        assert len(parsed_268.attachments) == 1
        assert parsed_268.attachments[0].filename == "daemon.log"
        assert parsed_268.attachments[0].file_path == "attachments/BUG-268/daemon.log"

        parsed_269 = server.exporter.parse_individual_bug_file(md_269)
        assert parsed_269 is not None
        assert len(parsed_269.attachments) == 1
        assert parsed_269.attachments[0].filename == "daemon.log"
        assert parsed_269.attachments[0].file_path == "attachments/BUG-269/daemon.log"
    finally:
        server.server_close()
