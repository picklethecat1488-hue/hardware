"""Behavioral unit tests for the Oxlint-backed JavaScript and Jinja2 validator."""

from __future__ import annotations

from pathlib import Path

from tools import validate_js


def test_repository_javascript_and_templates_compile_cleanly() -> None:
    """Verify all first-party .js assets and .html.j2 templates pass compilation and linting."""
    exit_code, errors = validate_js.validate_js()
    assert exit_code == 0, f"Expected 0 JS errors, got: {errors}"
    assert errors == []


def test_valid_module_classic_jinja_and_inline_handlers_pass(tmp_path: Path) -> None:
    """Verify valid ES modules, classic scripts, Jinja2 JSON values, and inline handlers exit 0."""
    helper_js = tmp_path / "helper.js"
    helper_js.write_text(
        "function formatCount(n) {\n  return String(n);\n}\nwindow.formatCount = formatCount;\n",
        encoding="utf-8",
    )

    tpl_path = tmp_path / "valid_widget.html.j2"
    tpl_path.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <button id="act-btn" onclick="handleToolbarAction(event)">Run</button>
  <script type="module">
    const initialMode = {{ mode | tojson }};
    function handleToolbarAction(ev) {
      if (ev && initialMode) {
        console.log(initialMode);
      }
    }
    window.handleToolbarAction = handleToolbarAction;
  </script>
  <script>
    const activeItems = {{ items | tojson }};
    if (activeItems.length > 0) {
      console.log(activeItems[0]);
    }
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )

    exit_code, errors = validate_js.validate_js(
        paths=[helper_js, tpl_path],
        template_context={"mode": "PCB", "items": ["U1", "C1"]},
    )
    assert exit_code == 0, f"Unexpected validation errors: {errors}"
    assert errors == []


def test_module_syntax_error_reports_exact_template_line(tmp_path: Path) -> None:
    """Verify a SyntaxError inside <script type='module'> fails with exact .html.j2 line number."""
    tpl_path = tmp_path / "broken_module.html.j2"
    tpl_path.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <div id="viewport"></div>
  <script type="module">
    const scale = 1.0;
    console.log("missing paren" scale);
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )

    exit_code, errors = validate_js.validate_js(paths=[tpl_path])
    assert exit_code == 1
    assert len(errors) >= 1
    assert any("broken_module.html.j2:7:" in err for err in errors), f"Expected line 7 in {errors}"


def test_unquoted_jinja_python_boolean_and_undefined_inline_handler_fail(tmp_path: Path) -> None:
    """Verify unquoted Python True/None or module-private inline onchange handlers fail no-undef."""
    tpl_unquoted = tmp_path / "unquoted_bool.html.j2"
    tpl_unquoted.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <script>
    const enabled = {{ flag }};
    console.log(enabled);
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )

    rc_bool, errs_bool = validate_js.validate_js(
        paths=[tpl_unquoted],
        template_context={"flag": True},
    )
    assert rc_bool == 1
    assert any("unquoted_bool.html.j2:5:" in err and "True" in err for err in errs_bool)

    tpl_inline = tmp_path / "private_module_inline.html.j2"
    tpl_inline.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <select onchange="onPrivateScaleChange(this.value)"></select>
  <script type="module">
    function onPrivateScaleChange(val) {
      console.log(val);
    }
    onPrivateScaleChange("1.0");
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )

    rc_inline, errs_inline = validate_js.validate_js(paths=[tpl_inline])
    assert rc_inline == 1
    assert any("private_module_inline.html.j2:4:" in err and "onPrivateScaleChange" in err for err in errs_inline)


def test_static_lint_rules_and_broken_inline_attribute_syntax_fail(tmp_path: Path) -> None:
    """Verify duplicate object keys, const reassignment, and broken onclick syntax fail."""
    bad_js = tmp_path / "bad_rules.js"
    bad_js.write_text(
        """const palette = { primary: "#0f0", primary: "#f00" };
const fixedLimit = 10;
fixedLimit = 20;
console.log(palette, fixedLimit);
""",
        encoding="utf-8",
    )

    rc_js, errs_js = validate_js.validate_js(paths=[bad_js])
    assert rc_js == 1
    assert any("no-dupe-keys" in err for err in errs_js)
    assert any("no-const-assign" in err for err in errs_js)

    bad_onclick = tmp_path / "bad_onclick.html.j2"
    bad_onclick.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <button onclick="window.alert('unterminated"></button>
</body>
</html>
""",
        encoding="utf-8",
    )

    rc_html, errs_html = validate_js.validate_js(paths=[bad_onclick])
    assert rc_html == 1
    assert any("bad_onclick.html.j2:4:" in err for err in errs_html)
