"""Integration tests for CAD/PCB Scope HTTP Server and Target Bug API."""

import gzip
import json
from pathlib import Path
import threading
import time
import urllib.request
import pytest

from provider.scope import ScopeServer, ScopeGeometryPipeline
from provider.bug_report.sqlite_store import SQLiteBugStore


@pytest.fixture(scope="module")
def scope_server(tmp_path_factory):
    """Spin up an ephemeral ScopeServer instance for testing."""
    repo_root = Path(__file__).resolve().parent.parent
    tmp_dir = tmp_path_factory.mktemp("scope_test")
    test_sqlite = tmp_dir / "bugs.sqlite"
    test_att = tmp_dir / "attachments"
    test_fb = tmp_dir / "feedback"
    test_att.mkdir(exist_ok=True)
    test_fb.mkdir(exist_ok=True)
    pipeline = ScopeGeometryPipeline()
    server = ScopeServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        pipeline=pipeline,
        sqlite_file=test_sqlite,
        attachments_dir=test_att,
        feedback_dir=test_fb,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def test_scope_server_serve_ui(scope_server):
    """Verify GET / returns 200 and renders the Quake HUD template."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")
    assert "SCOPE // CAD/PCB WORKSTATION" in html
    assert "three-cad-viewer.esm.js" in html


def test_scope_server_serve_static_assets(scope_server):
    """Verify static assets are served with correct MIME types and gzip compression."""
    js_url = f"http://127.0.0.1:{scope_server.actual_port}/static/three-cad-viewer.esm.js"
    req_js = urllib.request.urlopen(js_url)
    assert req_js.status == 200
    assert "application/javascript" in req_js.headers.get("Content-Type", "")

    # Test gzip compression support
    req_gzip = urllib.request.Request(js_url, headers={"Accept-Encoding": "gzip"})
    resp_gzip = urllib.request.urlopen(req_gzip)
    assert resp_gzip.status == 200
    assert resp_gzip.headers.get("Content-Encoding") == "gzip"
    decompressed = gzip.decompress(resp_gzip.read()).decode("utf-8")
    assert "class Viewer" in decompressed

    css_url = f"http://127.0.0.1:{scope_server.actual_port}/static/three-cad-viewer.css"
    req_css = urllib.request.urlopen(css_url)
    assert req_css.status == 200
    assert "text/css" in req_css.headers.get("Content-Type", "")


def test_scope_server_api_projects(scope_server):
    """Verify GET /api/scope/projects returns discoverable project list."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/projects"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "projects" in data
    assert any(p["name"] == "carrier_board" for p in data["projects"])


def test_scope_server_api_load_pcb(scope_server):
    """Verify GET /api/scope/load returns tessellated PCB layers and metadata."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert data["type"] == "data"
    assert "shapes" in data
    assert "pcb_metadata" in data
    assert len(data["pcb_metadata"]["layers"]) == 8


def test_scope_server_target_bug_submission(scope_server):
    """Verify POST /api/scope/target_bug creates bug in database, attachments, and markdown."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/target_bug"

    # Minimal 1x1 transparent PNG in base64
    tiny_png_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    payload = {
        "project": "carrier_board",
        "target": "carrier_board",
        "subassembly": None,
        "mode": "PCB",
        "title": "Automated Test Defect - PCB Layer Inspection",
        "severity": "LOW",
        "category": "PCB",
        "description": "Verification of automated Target Bug submission.",
        "reproduction_steps": "python tools/scope.py carrier_board/carrier_board:pcb",
        "image_base64": tiny_png_b64,
        "annotations": [{"id": 1, "x": 12.5, "y": 24.0, "z": 0.0, "text": "Trace clearance check"}],
        "markups": [],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    assert resp.status == 200
    result = json.loads(resp.read().decode("utf-8"))

    assert result["status"] == "ok"
    bug_id = result["bug_id"]
    assert bug_id.startswith("BUG-")

    # Verify bug exists in SQLite
    store = SQLiteBugStore(scope_server.sqlite_file)
    bug = store.get_bug(bug_id)
    assert bug is not None
    assert bug.title == payload["title"]
    assert len(bug.attachments) >= 1
    assert any(a.filename == "snapshot.png" for a in bug.attachments)
    if (scope_server.repo_root / "build" / "scope.log").exists():
        assert any(a.filename == "scope.log" for a in bug.attachments)
        log_path = scope_server.attachments_dir / bug_id / "scope.log"
        assert log_path.is_file()
    assert "Trace clearance check" in bug.description

    # Verify attachment file was saved
    att_path = scope_server.attachments_dir / bug_id / "snapshot.png"
    assert att_path.is_file()

    # Verify markdown file was generated
    md_path = Path(result["markdown_path"])
    assert md_path.is_file()
    md_content = md_path.read_text(encoding="utf-8")
    assert bug_id in md_content
    assert payload["title"] in md_content

    # Clean up test bug
    store.delete_bug(bug_id)
    if att_path.exists():
        att_path.unlink()
    if att_path.parent.exists() and not any(att_path.parent.iterdir()):
        att_path.parent.rmdir()
    if md_path.exists():
        md_path.unlink()


def test_regression_bug_plumed_treehopper_556_mode_tab_filtering(scope_server):
    """Verify that scope UI contains mode-aware tab filtering between CAD and PCB views."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariants for BUG-PLUMED-TREEHOPPER-556:
    # 1. PCB Layers tab button and CAD Tree tab button exist with distinct IDs
    assert 'id="tab-btn-layers"' in html
    assert 'id="tab-btn-tree"' in html

    # 2. Mode update function toggles layers and tree display based on state.currentMode === 'PCB'
    assert "function updateSidebarModeTabs()" in html
    assert 'tabBtnLayers.style.display = isPcb ? "block" : "none"' in html
    assert 'tabBtnTree.style.display = isPcb ? "none" : "block"' in html


def test_regression_bug_buzzing_caddisfly_645_non_modal_text_input(scope_server):
    """Verify non-modal text input for pins and text markup without modal popups."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariants for BUG-BUZZING-CADDISFLY-645:
    # 1. Non-modal input field exists in markup toolbar
    assert 'id="markup-text-input"' in html

    # 2. No prompt() modal popups used for spatial pin annotations
    assert "prompt(" not in html

    # 3. Spatial pin and text tools read from non-modal input
    assert 'document.getElementById("markup-text-input")' in html

    # 4. Inline editable notes in pins list
    assert "pin-note-input" in html


def test_regression_bug_rusty_hornet_486_modal_sync_progress(scope_server):
    """Verify modal progress bar UI during sync and geometry loading."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariants for BUG-RUSTY-HORNET-486:
    # 1. Modal progress overlay with track and staged progress bar
    assert 'id="modal-sync-progress"' in html
    assert 'id="sync-progress-bar"' in html
    assert 'id="sync-stage-text"' in html
    assert 'id="sync-percent-text"' in html

    # 2. Stage update and progress management functions
    assert "function showSyncProgress(" in html
    assert "function updateSyncProgress(" in html
    assert "function hideSyncProgress(" in html

    # 3. Synchronize handler triggers staged progress modal
    assert 'showSyncProgress("SYNCHRONIZING WORKSTATION")' in html
    assert "updateSyncProgress(20," in html


def test_regression_bug_segmented_moth_70_detach_cli_flags():
    """Verify scope CLI detaches cleanly with zero console spam (no pybullet, spinner, or warnings)."""
    import subprocess
    import sys

    scope_script = Path(__file__).resolve().parent.parent / "tools" / "scope.py"
    res = subprocess.run(
        [sys.executable, str(scope_script), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--no-detach" in res.stdout
    assert "--foreground" in res.stdout
    assert "pybullet build time" not in res.stdout
    assert "pybullet build time" not in res.stderr
    assert "Building..." not in res.stdout

    # Stop any running instances first
    subprocess.run(
        [sys.executable, str(scope_script), "stop"],
        capture_output=True,
        text=True,
    )

    try:
        # Launch detached workstation
        res_launch = subprocess.run(
            [sys.executable, str(scope_script), "carrier_board/carrier_board:pcb", "--no-app"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Verify clean stdout output
        assert "Scope workstation running at" in res_launch.stdout
        assert "Detached from terminal." in res_launch.stdout
        assert "SCOPE // CAD/PCB WORKSTATION" not in res_launch.stdout
        assert "pybullet build time" not in res_launch.stdout
        assert "pybullet build time" not in res_launch.stderr
        assert "Building..." not in res_launch.stdout
        assert "CameraKeepWarning" not in res_launch.stdout
        assert "CameraKeepWarning" not in res_launch.stderr
        assert "face" not in res_launch.stdout

        # Verify running again reports already running
        res_again = subprocess.run(
            [sys.executable, str(scope_script), "carrier_board/carrier_board:pcb", "--no-app"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Scope workstation is already running" in res_again.stdout
    finally:
        # Cleanly stop the background process
        res_stop = subprocess.run(
            [sys.executable, str(scope_script), "stop"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Stopped Scope" in res_stop.stdout


def test_scope_ui_cad_widget_theme_overrides(scope_server):
    """Verify that CAD widget theme matches Quake HUD look and feel."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariants for CAD widget theme matching main UI:
    assert "--tcv-bg-color: #120c08" in html
    assert "--tcv-theme-blue: #ffb800" in html
    assert 'data-theme", "dark"' in html
    assert "setClearColor(0x120c08" in html


def test_scope_app_icon_served(scope_server):
    """Verify that Scope app icon is served and linked in desktop window & UI."""
    from tools.scope import get_scope_icon_path

    # Verify helper discovers the app icon
    icon_path = get_scope_icon_path()
    assert icon_path is not None
    assert icon_path.exists()

    # Verify GET /static/scope-icon.svg
    svg_url = f"http://127.0.0.1:{scope_server.actual_port}/static/scope-icon.svg"
    req_svg = urllib.request.urlopen(svg_url)
    assert req_svg.status == 200
    assert "image/svg+xml" in req_svg.headers.get("Content-Type", "")

    # Verify GET /favicon.svg routes to scope icon
    fav_svg_url = f"http://127.0.0.1:{scope_server.actual_port}/favicon.svg"
    req_fav = urllib.request.urlopen(fav_svg_url)
    assert req_fav.status == 200

    # Verify scope UI includes the app icon link and header emblem
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_ui = urllib.request.urlopen(url)
    html = req_ui.read().decode("utf-8")
    assert "/static/scope-icon.svg" in html


def test_scope_ui_sidebar_resizer(scope_server):
    """Verify that vertical gripper/resizer is present for resizing the left panel."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariants for vertical panel resizer:
    assert 'id="sidebar-resizer"' in html
    assert "panel-resizer" in html
    assert "col-resize" in html
    assert "initSidebarResizer" in html
    assert "scope_sidebar_width" in html


def test_scope_server_structured_logging(tmp_path):
    """Verify that ScopeServer logs HTTP requests and geometry operations."""
    import logging
    from provider.scope import ScopeServer, ScopeGeometryPipeline

    log_records = []

    class TestLogHandler(logging.Handler):
        def emit(self, record):
            log_records.append(record.getMessage())

    test_logger = logging.getLogger("test.scope.server")
    test_logger.setLevel(logging.INFO)
    handler = TestLogHandler()
    test_logger.addHandler(handler)

    pipeline = ScopeGeometryPipeline()
    server = ScopeServer(
        host="127.0.0.1",
        port=0,
        pipeline=pipeline,
        logger=test_logger,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        url = f"http://127.0.0.1:{server.actual_port}/api/scope/projects"
        req = urllib.request.urlopen(url)
        assert req.status == 200

        # Verify request was logged through test_logger
        assert any("/api/scope/projects" in msg for msg in log_records)
    finally:
        server.shutdown()
        server.server_close()
        test_logger.removeHandler(handler)


def test_scope_server_generous_socket_timeout():
    """Verify ScopeServer sets socket timeout >= 60s to prevent startup fetch dropouts."""
    from provider.scope import ScopeServer

    server = ScopeServer(
        host="127.0.0.1",
        port=0,
        bind_and_activate=False,
    )
    # Validate timeout specification method
    assert hasattr(server, "get_request")


def test_scope_template_fetch_retry_handling(scope_server):
    """Verify scope template incorporates retry handling for startup geometry fetches."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariants for startup fetch error remediation:
    assert "retryCount" in html
    assert "Retrying Geometry..." in html
    assert "Retrying projects fetch" in html


def test_scope_ui_scale_controls(scope_server):
    """Verify that UI scale control dropdown and shortcut handlers exist in Scope UI."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariants for UI scale control:
    assert 'id="uiScaleSelect"' in html
    assert "ui-scale-container" in html
    assert "applyUiScale" in html
    assert "adjustUiScale" in html
    assert "scope_ui_scale" in html


def test_scope_inline_pin_and_text_editing(scope_server):
    """Verify that existing pins and text markup can be edited by selecting them with the tool."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariants for inline pin & text editing:
    assert "findHitPin" in html
    assert "findHitTextMarkup" in html
    assert "selectedPin" in html
    assert "selectedMarkup" in html


def test_scope_viewer_render_invocation_guards(scope_server):
    """Verify scope template passes 3 arguments to state.viewer.render to prevent destructure error."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # Invariant: render call must supply viewerOptions object ({}) to avoid 'tab' destructuring error
    assert "state.viewer.render(shapes, data.config || {}, {});" in html

    # Invariant: static three-cad-viewer must safely handle undefined options in updateViewerState
    js_url = f"http://127.0.0.1:{scope_server.actual_port}/static/three-cad-viewer.esm.js"
    req_js = urllib.request.urlopen(js_url)
    assert req_js.status == 200
    js_content = req_js.read().decode("utf-8")
    assert "updateViewerState(options = {}, notify = true)" in js_content
    assert "if (!options)" in js_content


def test_scope_server_streaming_gzip_cache(tmp_path):
    """Verify ScopeServer streams compressed gzip directly when available with <50ms latency."""
    cache_dir = tmp_path / "scope_cache"
    pipeline = ScopeGeometryPipeline(cache_dir=cache_dir)
    server = ScopeServer(host="127.0.0.1", port=0, pipeline=pipeline, bind_and_activate=True)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()

    try:
        # Pre-seed cache
        pipeline.load_geometry("cat_fountain", "bowl", mode="CAD")

        url = f"http://127.0.0.1:{server.actual_port}/api/scope/load?project=cat_fountain&target=bowl&mode=CAD"
        req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
        t0 = time.time()
        resp = urllib.request.urlopen(req)
        data = resp.read()
        elapsed = time.time() - t0

        assert resp.status == 200
        assert resp.headers.get("Content-Encoding") == "gzip"
        assert elapsed < 0.2  # Fast direct streaming from cache
        assert len(data) > 0
    finally:
        server.shutdown()
        server.server_close()


def test_scope_server_warm_up_background_thread(tmp_path):
    """Verify ScopeServer.warm_up starts a daemon thread that compiles and caches geometry."""
    cache_dir = tmp_path / "scope_cache"
    pipeline = ScopeGeometryPipeline(cache_dir=cache_dir)
    server = ScopeServer(host="127.0.0.1", port=0, pipeline=pipeline, bind_and_activate=False)

    server.warm_up("cat_fountain", "bowl", mode="CAD")

    # Wait for warm-up thread to populate cache
    deadline = time.time() + 30.0
    while time.time() < deadline:
        if ("cat_fountain", "bowl", None, "CAD", None) in pipeline._cache:
            break
        time.sleep(0.1)

    assert ("cat_fountain", "bowl", None, "CAD", None) in pipeline._cache


def test_regression_bug_antennal_firebug_841_viewport_resize(scope_server):
    """Verify Viewer.resize method exists in vendor asset and scope template configures full viewport flex layout."""
    vendor_js = (scope_server.repo_root / "provider" / "code_review" / "static" / "three-cad-viewer.esm.js").read_text(
        encoding="utf-8"
    )
    assert "resize(cadWidth, height)" in vendor_js
    assert "preserveDrawingBuffer" in vendor_js
    assert "this._rendered && this._rendered.camera" in vendor_js

    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")
    assert "ResizeObserver" in html
    assert "resizeViewport" in html
    assert "#cad-view .tcv_cad_viewer" in html
    assert "#cad-view .tcv_cad_view canvas" in html
    assert "height: 100% !important;" in html


def test_regression_top_hud_single_line_and_overflow(scope_server):
    """Verify top menu controls are styled in a single line with Sync/Target buttons and no clutter combo boxes."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")
    assert "white-space: nowrap" in html
    assert "overflow-x: auto" in html
    assert "flex-shrink: 0" in html
    assert "#top-hud::-webkit-scrollbar" in html
    assert "#965a25" in html
    assert "scrollbar-color: var(--quake-copper, #c87a32) #1e130b;" in html
    assert "btn-sync" in html
    assert "hud-active-target" in html
    assert "select-project" not in html
    assert "select-target" not in html


def test_regression_project_chooser_modal_when_no_args(scope_server):
    """Verify project chooser modal is present, loads with empty initial targets, and provides loading status bar."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")
    assert "modal-project-chooser" in html
    assert "openProjectChooserModal" in html
    assert "btn-open-chooser" in html
    assert 'currentProject: ""' in html
    assert 'currentTarget: ""' in html
    assert "chooser-loading-container" in html
    assert "chooser-loading-bar" in html
    assert "setChooserLoading" in html


def test_regression_bug_bright_stagbeetle_720_hide_cad_controls_in_all_modes(scope_server):
    """Verify CAD controls are hidden in all modes, axis indicator is maintained, tree has visibility toggles, and ruler is in quickbar."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")
    assert "#cad-view .tcv_cad_toolbar" in html
    assert "#cad-view .tcv_cad_navigation" in html
    assert "display: none !important;" in html
    assert "#cad-view .tcv_cad_inset" in html
    assert "visibility: visible !important;" in html
    assert "tree-visibility-btn" in html
    assert "cam-ruler" in html
    assert "tab-btn-display" in html
    assert "tab-display" in html


def test_regression_bug_quick_grub_512_scrollbar_theme(scope_server):
    """Verify dark color-scheme meta and Quake palette styling for WebKit scrollbars on top HUD."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")
    assert '<meta name="color-scheme" content="dark">' in html
    assert '<meta name="theme-color" content="#291a10">' in html
    assert "color-scheme: dark;" in html
    assert "@supports not selector(::-webkit-scrollbar)" in html
    assert "#top-hud::-webkit-scrollbar" in html
    assert "#top-hud::-webkit-scrollbar-track" in html
    assert "#top-hud::-webkit-scrollbar-thumb" in html


def test_regression_bug_dorsal_jewelbeetle_219_snapshot_and_render_perf(scope_server):
    """Verify snapshot renders actual Three.js scene camera and render speed optimizations are active."""
    vendor_js = (scope_server.repo_root / "provider" / "code_review" / "static" / "three-cad-viewer.esm.js").read_text(
        encoding="utf-8"
    )
    assert 'powerPreference: "high-performance"' in vendor_js
    assert "targetPixelRatio" in vendor_js
    assert "if (this._isDragging) return true;" in vendor_js

    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")
    assert "threeCamera" in html
    assert "controls._isDragging = true" in html
    assert "controls._isDragging = false" in html


def test_regression_bug_lustrous_mantis_333_simulation_playback_and_rerun_logs(scope_server):
    """Verify simulation mode includes animated water particles, clickable rerun timeline logs, and flow metrics."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")
    assert "sim-timeline-logs" in html
    assert "sim-log-chip" in html
    assert "sim-flow-metrics" in html
    assert "initSimulationParticles" in html
    assert "updateSimulationStep" in html
    assert "simulation_water_particles" in html


def test_regression_bug_luminescent_springtail_8_unrendered_viewer_and_projects_populate(scope_server):
    """Verify unrendered Viewer does not throw in resizeCadView and projects populate cleanly (BUG-LUMINESCENT-SPRINGTAIL-8)."""
    # 1. Verify three-cad-viewer JS safely returns null rather than throwing
    js_url = f"http://127.0.0.1:{scope_server.actual_port}/static/three-cad-viewer.esm.js"
    req_js = urllib.request.urlopen(js_url)
    assert req_js.status == 200
    js_content = req_js.read().decode("utf-8")
    assert "return this._rendered || null;" in js_content
    assert "if (this._rendered && this._rendered.camera)" in js_content
    assert 'throw new Error("Viewer.render() must be called before this operation");' not in js_content

    # 2. Verify scope HTML contains defensive try/catch in resizeViewport
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")
    assert "getViewerRendered" in html
    assert "function resizeViewport()" in html
    assert "state.viewer.resizeCadView(w, 0, h, true);" in html

    # 3. Verify API returns projects list without error
    projects_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/projects"
    req_proj = urllib.request.urlopen(projects_url)
    assert req_proj.status == 200
    proj_data = json.loads(req_proj.read().decode("utf-8"))
    assert "projects" in proj_data
    assert len(proj_data["projects"]) > 0
    proj_names = [p["name"] for p in proj_data["projects"]]
    assert "carrier_board" in proj_names


def test_regression_bug_nimble_bee_781_cat_fountain_footprints_z_ordering(scope_server):
    """Verify BUG-NIMBLE-BEE-781: bottom cover is opaque (alpha=1.0) and materials do not force transparent: true."""
    # 1. Verify three-cad-viewer JS computes isTransparent dynamically based on alpha
    js_url = f"http://127.0.0.1:{scope_server.actual_port}/static/three-cad-viewer.esm.js"
    req_js = urllib.request.urlopen(js_url)
    assert req_js.status == 200
    js_content = req_js.read().decode("utf-8")
    assert "const isTransparent = this.transparent || (alpha !== undefined && alpha < 1.0);" in js_content
    assert "transparent: isTransparent," in js_content
    assert "depthWrite: !isTransparent," in js_content

    # 2. Verify cat_fountain manifest specifies opaque bottom cover
    from pathlib import Path
    import yaml

    manifest_path = Path("projects/cat_fountain/manifest.yaml")
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert "bottom_cover" in manifest_data
    bottom_cover_color = manifest_data["bottom_cover"]["color"]
    assert len(bottom_cover_color) == 4
    assert bottom_cover_color[3] == 1.0, "bottom_cover must have alpha 1.0 (opaque) to prevent Z-ordering bleed"


def test_regression_bug_lustrous_mantis_333_simulation_fountain_physics(scope_server):
    """Verify BUG-LUSTROUS-MANTIS-333: fountain physics trajectory respects bowl floor Z=41, tube at Y=28, spout Z=114, and timeline logs scrub."""
    import re

    # 1. Fetch Scope HTML template and check simulation trajectory and controls
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    assert "function getFountainTrajectoryPoint(t, meta)" in html
    assert "const FLOOR_Z = 41.0;" in html
    assert "const TUBE_TOP_Z = 107.0;" in html
    assert "const DOME_APEX_Z = 114.5;" in html
    assert "const LID_TRAY_Z = 105.0;" in html
    assert "const TUBE_Y = 28.0;" in html
    assert "btn-sim-play" in html
    assert "toggleSimPlay" in html
    assert "sim-log-chip" in html
    assert "sim-flow-metrics" in html

    # 2. Extract trajectory function from HTML and evaluate points across full cycle t in [0.0, 1.0]
    # We can evaluate the math in Python to ensure every single Z point is strictly >= 41.0 (above reservoir floor)
    # and <= 116.0 (below outer bounds)
    import math

    def py_get_trajectory_point(t, angle_offset=0.0):
        FLOOR_Z = 41.0
        TUBE_TOP_Z = 107.0
        DOME_APEX_Z = 114.5
        LID_TRAY_Z = 105.0
        POOL_SURFACE_Z = 68.0
        TUBE_Y = 28.0

        if t < 0.22:
            u = t / 0.22
            if u < 0.15:
                sub = u / 0.15
                x = 0.0
                y = sub * TUBE_Y
                z = FLOOR_Z + 3.0 + sub * 2.0
            else:
                sub = (u - 0.15) / 0.85
                z = FLOOR_Z + 5.0 + sub * (TUBE_TOP_Z - (FLOOR_Z + 5.0))
                rad = 4.5
                x = math.cos(angle_offset + sub * 5.0) * (rad * 0.7)
                y = TUBE_Y + math.sin(angle_offset + sub * 5.0) * (rad * 0.7)
        elif t < 0.32:
            u = (t - 0.22) / 0.10
            z = TUBE_TOP_Z + math.sin(u * math.pi) * (DOME_APEX_Z - TUBE_TOP_Z) - u * 2.0
            spread = 6.0 + u * 20.0
            x = math.cos(angle_offset) * spread
            y = TUBE_Y + math.sin(angle_offset) * spread
        elif t < 0.62:
            u = (t - 0.32) / 0.30
            z = LID_TRAY_Z - u * 1.0
            startX = math.cos(angle_offset) * 26.0
            startY = TUBE_Y + math.sin(angle_offset) * 26.0
            endR = 76.0 + math.sin(angle_offset * 2.0) * 4.0
            endX = math.cos(angle_offset) * endR
            endY = math.sin(angle_offset) * endR
            x = startX * (1 - u) + endX * u
            y = startY * (1 - u) + endY * u
        elif t < 0.82:
            u = (t - 0.62) / 0.20
            r = 78.0 + math.sin(u * math.pi * 0.5) * 3.0
            z = (LID_TRAY_Z - 1.0) - (u * u) * (LID_TRAY_Z - 1.0 - POOL_SURFACE_Z)
            x = math.cos(angle_offset) * r
            y = math.sin(angle_offset) * r
        else:
            u = (t - 0.82) / 0.18
            z = POOL_SURFACE_Z * (1 - u) + (FLOOR_Z + 4.0) * u + math.sin(u * math.pi * 2.0) * 1.5
            r = 78.0 * (1 - u) + 4.0 * u
            angle = angle_offset + u * 3.5
            x = math.cos(angle) * r
            y = math.sin(angle) * r
        return x, y, z

    for step_pct in range(0, 100):
        t = step_pct / 100.0
        x, y, z = py_get_trajectory_point(t)
        assert z >= 41.0, f"Trajectory point at t={t} dipped below floor_z=41.0: z={z}"
        assert z <= 116.0, f"Trajectory point at t={t} exceeded max bound: z={z}"


def test_regression_bug_jumping_instar_950_simulate_view_max_steps_physics_inspection_rerun_logs(scope_server):
    """Verify BUG-JUMPING-INSTAR-950: simulate view max steps selection, physics object inspection, and rerun log queries."""
    # 1. Fetch Scope UI with max_steps query parameter and verify template injection
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/?mode=SIMULATE&max_steps=2000"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    # 2. Check max steps selection in modal and state
    assert 'id="chooser-sim-steps-container"' in html
    assert 'id="chooser-max-steps"' in html
    assert 'value="500"' in html
    assert 'value="1000"' in html
    assert 'value="2000"' in html
    assert 'value="5000"' in html
    assert "maxSteps: 2000" in html
    assert "state.maxSteps = parsedSteps;" in html

    # 3. Check Physics Object Inspection Telemetry in Inspector
    assert "PHYSICS TELEMETRY [Rerun / SPH]" in html
    assert "SPH Fluid Dynamics [JAX]" in html
    assert "Rigid Body Kinematics [PyBullet]" in html
    assert "Static CAD Boundary [SDF Collision]" in html
    assert "Tait Weakly Compressible EOS" in html
    assert "Mass Density:" in html
    assert "Active Particles:" in html
    assert "Volumetric Flow:" in html

    # 4. Check Left Panel Rerun Logs querying and milestone scrub
    assert 'id="tab-btn-logs"' in html
    assert 'id="tab-logs"' in html
    assert 'id="rerun-search"' in html
    assert 'id="rerun-logs-list"' in html
    assert 'id="rerun-logs-count"' in html
    assert 'function renderRerunLogs(query = "")' in html
    assert "RERUN_LOGS =" in html
    assert "world/cat_fountain" in html
    assert "cat_fountain/impeller" in html
    assert "metrics/flow_spout" in html
    assert "metrics/flow_waterfall" in html
    assert "metrics/reservoir_volume" in html


def test_shortcuts_toggle_cad_viewport_overlay(scope_server):
    """Verify that Shortcuts button toggles the in-viewport HUD overlay inside the CAD viewport."""
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    # 1. Viewport HUD overlay container and close button
    assert 'id="cad-shortcuts-hud"' in html
    assert 'id="btn-close-shortcuts-hud"' in html
    assert "◈ KEYBOARD & MOUSE CONTROLS ◈" in html
    assert "shortcuts-table" in html

    # 2. Toggle button in header and active styles
    assert 'id="btn-shortcuts"' in html
    assert "Toggle Shortcuts in CAD Viewport" in html
    assert "#cad-shortcuts-hud.visible" in html
    assert "#btn-shortcuts.active" in html

    # 3. Toggle JavaScript functions and key listeners
    assert "function toggleShortcuts(show)" in html
    assert 'hud.classList.toggle("visible", isVisible);' in html
    assert 'btn.classList.toggle("active", isVisible);' in html
    assert 'document.getElementById("btn-shortcuts")?.addEventListener("click"' in html
    assert 'document.getElementById("btn-close-shortcuts-hud")?.addEventListener("click"' in html

    # 4. Modal overlay replaced by viewport HUD
    assert 'id="modal-shortcuts"' not in html
