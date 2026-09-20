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
from provider.bug_report.server import BugReportServer


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
