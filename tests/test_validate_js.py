"""Behavioral unit tests for the zero-globals Oxlint JavaScript and Jinja2 validator."""

from __future__ import annotations

from pathlib import Path

from tools import validate_js


def test_repository_javascript_and_templates_compile_cleanly() -> None:
    """Verify all repository ES modules, Three.js addons, unit tests, and .html.j2 templates pass 100%."""
    discovered = validate_js.discover_first_party_js_files(validate_js.REPO_ROOT)
    discovered_names = {p.name for p in discovered}
    assert "OrbitControls.js" in discovered_names
    assert "LineSegments2.js" in discovered_names
    assert "pcb_renderer.js" in discovered_names
    assert "scope_pcb.test.mjs" in discovered_names

    exit_code, errors = validate_js.validate_js()
    assert exit_code == 0, f"Expected 0 JS errors, got: {errors}"
    assert errors == []


def test_valid_zero_globals_module_and_json_boot_template_pass(tmp_path: Path) -> None:
    """Verify a zero-globals ES module and JSON boot-config Jinja2 template exit 0."""
    js_dir = tmp_path / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    widget_js = js_dir / "widget.js"
    widget_js.write_text(
        """export function mountWidget(ctx, label) {
  const el = ctx.document.getElementById("status");
  if (el) {
    el.textContent = String(label);
  }
  return Boolean(el);
}
""",
        encoding="utf-8",
    )

    tpl_path = tmp_path / "valid_widget.html.j2"
    tpl_path.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <div id="status"></div>
  <script id="app-boot-config" type="application/json">{{ {"mode": mode, "items": items} | tojson }}</script>
  <script type="module" src="/js/widget.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )

    exit_code, errors = validate_js.validate_js(
        paths=[widget_js, tpl_path],
        repo_root=tmp_path,
        config_path=validate_js.REPO_ROOT / ".oxlintrc.json",
        template_context={"mode": "PCB", "items": ["U1", "C1"]},
    )
    assert exit_code == 0, f"Unexpected validation errors: {errors}"
    assert errors == []


def test_direct_browser_globals_outside_runtime_context_fail(tmp_path: Path) -> None:
    """Verify direct window/document/localStorage access outside runtime_context.js is rejected."""
    bad_mod = tmp_path / "leaky_feature.js"
    bad_mod.write_text(
        """export function readScale() {
  const saved = localStorage.getItem("scale");
  window.activeScale = saved;
  return document.getElementById("root");
}
""",
        encoding="utf-8",
    )

    rc, errors = validate_js.validate_js(paths=[bad_mod])
    assert rc == 1
    assert any("no-direct-global" in err and "localStorage." in err for err in errors)
    assert any("no-direct-global" in err and "window." in err for err in errors)
    assert any("no-direct-global" in err and "document." in err for err in errors)


def test_inline_event_handlers_and_inline_executable_scripts_fail(tmp_path: Path) -> None:
    """Verify inline onclick attributes and inline executable <script> blocks fail with exact lines."""
    tpl_path = tmp_path / "legacy_inline.html.j2"
    tpl_path.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <button id="act-btn" onclick="doSomething()">Run</button>
  <script type="module">
    const scale = 1.0;
    console.log(scale);
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )

    rc, errors = validate_js.validate_js(paths=[tpl_path])
    assert rc == 1
    assert any("legacy_inline.html.j2:4:" in err and "no-inline-event-handler" in err for err in errors)
    assert any("legacy_inline.html.j2:5:" in err and "no-inline-script" in err for err in errors)


def test_invalid_json_boot_config_and_missing_script_src_fail(tmp_path: Path) -> None:
    """Verify unquoted Python True in JSON boot blocks and missing /js/ src paths fail."""
    tpl_path = tmp_path / "bad_boot.html.j2"
    tpl_path.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <script id="app-boot-config" type="application/json">{"enabled": {{ flag }}}</script>
  <script type="module" src="/js/missing_entry.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )

    rc, errors = validate_js.validate_js(
        paths=[tpl_path],
        repo_root=tmp_path,
        config_path=validate_js.REPO_ROOT / ".oxlintrc.json",
        template_context={"flag": True},
    )
    assert rc == 1
    assert any("bad_boot.html.j2:4:" in err and "invalid-json-script" in err for err in errors)
    assert any("bad_boot.html.j2:5:" in err and "missing-script-src" in err for err in errors)


def test_static_lint_rules_and_syntax_error_report_exact_line(tmp_path: Path) -> None:
    """Verify duplicate object keys, const reassignment, and JS syntax errors report exact lines."""
    bad_js = tmp_path / "bad_rules.js"
    bad_js.write_text(
        """export function brokenRules() {
  const palette = { primary: "#0f0", primary: "#f00" };
  const fixedLimit = 10;
  fixedLimit = 20;
  return [palette, fixedLimit];
}
""",
        encoding="utf-8",
    )

    rc_js, errs_js = validate_js.validate_js(paths=[bad_js])
    assert rc_js == 1
    assert any("no-dupe-keys" in err for err in errs_js)
    assert any("no-const-assign" in err for err in errs_js)

    syntax_js = tmp_path / "syntax_err.js"
    syntax_js.write_text(
        """export function brokenSyntax() {
  const scale = 1.0;
  return ("missing operator" scale);
}
""",
        encoding="utf-8",
    )
    rc_syn, errs_syn = validate_js.validate_js(paths=[syntax_js])
    assert rc_syn == 1
    assert any("syntax_err.js:3:" in err for err in errs_syn), f"Expected line 3 in {errs_syn}"
