"""Regression test for BUG-TRANSLUCENT-TERMITE-733 repository structure invariants."""

from pathlib import Path


def test_regression_bug_translucent_termite_733_repo_structure():
    """Verify directories under src/ are folded into repo root and command scripts are under tools/."""
    repo_root = Path(__file__).resolve().parent.parent

    # 1. src/ directory should not exist in the new structure
    src_dir = repo_root / "src"
    assert not src_dir.exists(), "src/ directory must be folded into repository root and removed"

    # 2. Package directories must exist directly under repository root
    expected_root_packages = [
        "model",
        "projects",
        "projects_config",
        "provider",
        "tests",
    ]
    for pkg in expected_root_packages:
        pkg_dir = repo_root / pkg
        assert pkg_dir.is_dir(), f"Expected directory '{pkg}' at repo root, but not found"

    # 3. Command scripts must exist under tools/
    tools_dir = repo_root / "tools"
    assert tools_dir.is_dir(), "tools/ directory must exist"

    expected_tools = [
        "build.py",
        "view.py",
        "dashboard.py",
        "daemon.py",
        "list.py",
        "shell.py",
        "smoke.py",
        "config.py",
        "target_parser.py",
    ]
    for tool in expected_tools:
        tool_file = tools_dir / tool
        assert tool_file.is_file(), f"Expected tool script '{tool}' under tools/, but not found"
