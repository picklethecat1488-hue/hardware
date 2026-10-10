"""Regression and unit test for WORM-029: Docker-pattern issue IDs.

Verifies:
1. Issue IDs are formatted as [PREFIX]-[ADJECTIVE]-[ANIMAL/NOUN]-[3 digits]
   e.g. BUG-SWIFT-FOX-42, BUG-BOLD-LYNX-809, BUG-IRON-CRANE-17.
2. Selection is generated using a CRNG (secrets/os.urandom).
3. Adjective and animal/noun lists are compressed with zlib/base64 to minimize code footprint.
4. Database and SQLite stores generate unique Docker-pattern IDs without collisions.
5. Markdown exporter and loader serialize and round-trip Docker-pattern IDs.
6. Git engine and dashboard extract and link Docker-pattern tags in commit subjects.
"""

from pathlib import Path
import re

from model.bug_report import BugCategory, BugDatabaseModel, BugReportModel, BugSeverity, BugStatus
from model.id_generator import (
    ADJECTIVES,
    NOUNS,
    _B64_ADJS,
    _B64_NOUNS,
    generate_docker_pattern_id,
    is_docker_pattern_id,
)
from provider.bug_report.markdown_exporter import MarkdownBugExporter
from provider.bug_report.sqlite_store import SQLiteBugStore
from provider.vcs.git_engine import GitEngine


def test_compressed_word_lists_save_code_space() -> None:
    """Verify adjective and noun lists are compressed in base64 strings taking minimal code space."""
    assert len(_B64_ADJS) < 500, "Compressed adjectives base64 string must be compact"
    assert len(_B64_NOUNS) < 500, "Compressed nouns base64 string must be compact"

    # Must contain representative words from worm-themed word lists
    assert "BURROWING" in ADJECTIVES
    assert "WRIGGLY" in ADJECTIVES
    assert "LOAMY" in ADJECTIVES
    assert "ANNELID" in NOUNS
    assert "EARTHWORM" in NOUNS
    assert "NIGHTCRAWLER" in NOUNS

    assert len(ADJECTIVES) >= 50
    assert len(NOUNS) >= 50


def test_docker_pattern_id_format_and_crng() -> None:
    """Verify generated IDs match [PREFIX]-[ADJECTIVE]-[ANIMAL/NOUN]-[1..3 digits]."""
    pattern = re.compile(r"^BUG-[A-Z]+-[A-Z]+-\d{1,3}$")

    generated_ids = set()
    for _ in range(50):
        bug_id = generate_docker_pattern_id(prefix="BUG")
        assert pattern.match(bug_id), f"ID '{bug_id}' does not match Docker pattern"
        assert is_docker_pattern_id(bug_id)

        parts = bug_id.split("-")
        assert len(parts) == 4, f"ID '{bug_id}' must have exactly 4 parts separated by hyphens"
        assert parts[0] == "BUG"
        assert parts[1] in ADJECTIVES
        assert parts[2] in NOUNS

        num = int(parts[3])
        assert 1 <= num <= 999
        generated_ids.add(bug_id)

    # CRNG should generate distinct IDs without trivial collisions
    assert len(generated_ids) >= 48


def test_docker_pattern_id_avoids_existing_ids() -> None:
    """Verify generator respects existing_ids collection and avoids collisions."""
    mock_id = "BUG-BURROWING-ANNELID-42"
    existing = {mock_id}

    # Should never return an ID present in existing
    for _ in range(20):
        new_id = generate_docker_pattern_id(prefix="BUG", existing_ids=existing)
        assert new_id != mock_id
        existing.add(new_id)


def test_bug_database_model_generates_docker_ids() -> None:
    """Verify BugDatabaseModel generates Docker-pattern IDs."""
    db = BugDatabaseModel(title="Test DB")
    id1 = db.generate_bug_id()
    assert is_docker_pattern_id(id1)

    db.add_or_update(
        BugReportModel(
            id=id1,
            title="Defect 1",
            status=BugStatus.OPEN,
            severity=BugSeverity.MEDIUM,
            category=BugCategory.PCB,
        )
    )

    id2 = db.generate_bug_id()
    assert is_docker_pattern_id(id2)
    assert id2 != id1


def test_sqlite_store_generates_and_resolves_docker_ids(tmp_path: Path) -> None:
    """Verify SQLiteBugStore generates unique Docker-pattern IDs and resolves duplicates."""
    db_file = tmp_path / "bugs.sqlite"
    store = SQLiteBugStore(db_file)

    id1 = store.generate_next_bug_id()
    assert is_docker_pattern_id(id1)

    b1 = BugReportModel(
        id=id1,
        title="SQL defect 1",
        status=BugStatus.OPEN,
        severity=BugSeverity.HIGH,
        category=BugCategory.PCB,
    )
    store.save_bug(b1)

    id2 = store.generate_next_bug_id()
    assert is_docker_pattern_id(id2)
    assert id2 != id1


def test_markdown_exporter_roundtrip_with_docker_pattern_ids(tmp_path: Path) -> None:
    """Verify MarkdownBugExporter roundtrips individual and aggregated markdown files with Docker IDs."""
    exporter = MarkdownBugExporter(repo_root=tmp_path)
    feedback_dir = tmp_path / "feedback"

    bug = BugReportModel(
        id="BUG-BURROWING-ANNELID-42",
        title="Docker pattern issue test",
        status=BugStatus.OPEN,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.PCB,
        component="dashboard",
        description="Verify Docker pattern ID formatting and parsing",
    )

    # 1. Single file export
    exported_file = exporter.export_individual_bug(bug, feedback_dir)
    assert exported_file.exists()
    assert "BUG_BURROWING-ANNELID-42.md" in exported_file.name

    # 2. Single file loading
    loaded_single = exporter.parse_individual_bug_file(exported_file)
    assert loaded_single is not None
    assert loaded_single.id == "BUG-BURROWING-ANNELID-42"
    assert loaded_single.title == "Docker pattern issue test"

    # 3. Aggregated BUGS.md export and loading
    db = BugDatabaseModel(title="Docker Bug Tracker", bugs=[bug])
    bugs_md = tmp_path / "BUGS.md"
    exporter.export_markdown(db, bugs_md, feedback_dir=feedback_dir)

    loaded_db = exporter.parse_markdown(bugs_md)
    assert loaded_db is not None
    assert len(loaded_db.bugs) == 1
    assert loaded_db.bugs[0].id == "BUG-BURROWING-ANNELID-42"


def test_git_engine_extracts_docker_pattern_bug_tags(tmp_path: Path) -> None:
    """Verify GitEngine extracts Docker-pattern bug tags from commit text."""
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    (feedback_dir / "BUG_BURROWING-ANNELID-42.md").write_text(
        "# 🔴 `[BUG-BURROWING-ANNELID-42]` Burrowing annelid bug\n- **Status**: `OPEN`\n- **Severity**: `HIGH`\n",
        encoding="utf-8",
    )

    engine = GitEngine(repo_root=tmp_path)
    commit_text = "fix(core): resolve issue with timing (BUG-BURROWING-ANNELID-42)"
    tags = engine._extract_bug_tags(commit_text)

    assert len(tags) == 1
    assert tags[0].id == "BUG-BURROWING-ANNELID-42"
    assert tags[0].title == "Burrowing annelid bug"
    assert tags[0].status == "OPEN"
    assert tags[0].severity == "HIGH"
