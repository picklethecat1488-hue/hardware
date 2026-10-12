"""Repository hygiene and tracked file invariant tests."""

from pathlib import Path
import subprocess

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def test_regression_bug_humic_centipede_711_clean_up_repo() -> None:
    """Verify repo hygiene: cat_fountain_wiring_diagram.svg and src/urdf_template.yaml are not tracked (BUG-HUMIC-CENTIPEDE-711)."""
    # 1. cat_fountain_wiring_diagram.svg at root must not be tracked by git
    res = subprocess.run(
        ["git", "ls-files", "cat_fountain_wiring_diagram.svg"],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.stdout.strip() == "", "cat_fountain_wiring_diagram.svg at repo root should not be tracked in git"

    # 2. src/urdf_template.yaml must not exist in src/
    urdf_path = WORKSPACE_ROOT / "src" / "urdf_template.yaml"
    assert not urdf_path.exists(), (
        "src/urdf_template.yaml should be relocated to src/provider/templates/urdf_template.yaml"
    )

    # 3. Canonical URDF template in src/provider/templates/urdf_template.yaml must exist
    canonical_urdf_template = WORKSPACE_ROOT / "src" / "provider" / "templates" / "urdf_template.yaml"
    assert canonical_urdf_template.exists(), "Canonical urdf_template.yaml must exist under src/provider/templates/"
