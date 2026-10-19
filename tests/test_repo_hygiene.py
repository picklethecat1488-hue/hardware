"""Repository hygiene and tracked file invariant tests."""

from pathlib import Path
import subprocess

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


def test_regression_bug_humic_centipede_711_clean_up_repo() -> None:
    """Verify repo hygiene: cat_fountain_wiring_diagram.svg and urdf_template.yaml are not tracked at root (BUG-HUMIC-CENTIPEDE-711)."""
    # 1. cat_fountain_wiring_diagram.svg at root must not be tracked by git
    res = subprocess.run(
        ["git", "ls-files", "cat_fountain_wiring_diagram.svg"],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.stdout.strip() == "", "cat_fountain_wiring_diagram.svg at repo root should not be tracked in git"

    # 2. urdf_template.yaml must not exist directly in repo root or src/
    urdf_path = WORKSPACE_ROOT / "urdf_template.yaml"
    assert not urdf_path.exists(), "urdf_template.yaml should be in provider/templates/urdf_template.yaml"

    # 3. Canonical URDF template in provider/templates/urdf_template.yaml must exist
    canonical_urdf_template = WORKSPACE_ROOT / "provider" / "templates" / "urdf_template.yaml"
    assert canonical_urdf_template.exists(), "Canonical urdf_template.yaml must exist under provider/templates/"


def test_gemini_functional_behavioral_testing_mandate() -> None:
    """Verify GEMINI.md codifies the Functional Behavioral Testing Mandate (CR-824ffd23)."""
    gemini_path = WORKSPACE_ROOT / "GEMINI.md"
    assert gemini_path.exists(), "GEMINI.md must exist at workspace root"
    content = gemini_path.read_text(encoding="utf-8")
    assert "Functional Behavioral Testing Mandate" in content, (
        "GEMINI.md must codify the Functional Behavioral Testing Mandate"
    )
