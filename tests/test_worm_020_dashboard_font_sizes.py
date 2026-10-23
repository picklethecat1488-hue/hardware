"""Regression unit test for WORM-020: Reduce dashboard font sizes to ~80%.

Verifies that dashboard font sizes across diff_view.html.j2, diff_component.html.j2,
code_review.html.j2, and bug_report.html.j2 are reduced to approximately 80% of
their original scale.
"""

from pathlib import Path
import re

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "provider" / "templates"


def test_worm_020_body_and_root_font_size_reduced() -> None:
    """Verify that html/body font size is set to 80% or scaled down across all templates."""
    for tpl_name in ("diff_view.html.j2", "code_review.html.j2", "bug_report.html.j2"):
        tpl_path = TEMPLATES_DIR / tpl_name
        assert tpl_path.exists()
        content = tpl_path.read_text(encoding="utf-8")
        assert "font-size: 80%" in content or "font-size: 11px" in content or "font-size: 10px" in content, (
            f"{tpl_name} should specify reduced base font-size"
        )


def test_worm_020_button_and_code_font_sizes_reduced() -> None:
    """Verify key UI components (.quake-btn, code diffs, badges) have reduced font-sizes (<= 9px)."""
    diff_view = (TEMPLATES_DIR / "diff_view.html.j2").read_text(encoding="utf-8")
    diff_comp = (TEMPLATES_DIR / "diff_component.html.j2").read_text(encoding="utf-8")
    cr_view = (TEMPLATES_DIR / "code_review.html.j2").read_text(encoding="utf-8")

    # .quake-btn was previously 11px -> should now be <= 9px (80% of 11px = ~8.8px -> 9px)
    assert re.search(r"\.quake-btn\s*\{[^}]*font-size:\s*(?:8|9)px", diff_view)
    assert re.search(r"\.quake-btn\s*\{[^}]*font-size:\s*(?:8|9)px", cr_view)

    # .diff-content / code font size was 11px -> should now be <= 9px
    assert re.search(r"font-size:\s*(?:8|9)px", diff_comp)
