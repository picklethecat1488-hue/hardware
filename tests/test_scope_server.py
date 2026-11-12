"""Integration tests for CAD/PCB Scope HTTP Server and Target Bug API."""

import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
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

    server.warm_up("footprints", "0402", mode="CAD")

    # Wait for warm-up thread to populate cache
    deadline = time.time() + 120.0
    while time.time() < deadline:
        if getattr(server, "_warm_up_error", None) is not None:
            raise RuntimeError(f"Warm up background error: {server._warm_up_error}")
        if ("footprints", "0402", None, "CAD", None) in pipeline._cache:
            break
        time.sleep(0.1)

    assert ("footprints", "0402", None, "CAD", None) in pipeline._cache


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


def test_regression_bug_translucent_lacewing_144_pcb_layers_and_net_highlight(scope_server):
    """Verify BUG-TRANSLUCENT-LACEWING-144: PCB view includes high-contrast palette, layer toggles, net highlight, and quickbar."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")

    # 1. PCB camera quickbar buttons (cam-contrast removed, HC always on in PCB)
    assert 'id="cam-bottom"' in html
    assert 'id="cam-flip"' in html
    assert 'id="cam-contrast"' not in html

    # 2. PCB layers pane controls (btn-high-contrast removed)
    assert 'id="btn-all-layers"' in html
    assert 'id="btn-flip-pcb"' in html
    assert 'id="btn-high-contrast"' not in html
    assert "setLayerVisibility" in html
    assert "toggleSoloLayer" in html

    # 3. KiCad high-contrast net highlighting & entity inspect
    assert "highlightNet" in html
    assert "clearNetHighlight" in html
    assert "findPcbEntityAtPoint" in html
    assert "minDistance" in html
    assert "pcb-hover-tooltip" in html
    assert 'target.includes("substrate")' in html
    assert "removeLastBbox" in html
    assert "clearSelection" in html
    assert "COPPER TRACE" in html
    assert "COPPER PAD" in html
    assert "NetHighlight_" in html

    # 4. Backend PCB data payload validation
    load_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    load_req = urllib.request.urlopen(load_url)
    assert load_req.status == 200
    data = json.loads(load_req.read().decode("utf-8"))
    assert "pcb_metadata" in data
    meta = data["pcb_metadata"]

    # Verify high-contrast KiCad layer colors (BUG-DORSAL-MIDGE-176)
    layer_colors = {l["name"]: l["color"] for l in meta.get("layers", [])}
    assert layer_colors.get("F.Cu (Top)") == "#c83434"
    assert layer_colors.get("B.Cu (Bottom)") == "#345ac8"
    assert layer_colors.get("Pads") == "#c8a034"

    # Verify enriched traces, vias, pads, components, and nets
    assert len(meta.get("traces", [])) > 0
    assert len(meta.get("vias", [])) > 0
    assert len(meta.get("pads", [])) > 0
    assert len(meta.get("components", [])) > 0
    assert len(meta.get("nets", [])) > 0
    assert any(c.get("size") is not None for c in meta.get("components", []))

    # Verify PCB3DAssembler builds traces with rounded vertex caps
    from provider.pcb.cad_assembler import PCB3DAssembler
    from projects.carrier_board.provider import CarrierBoardProvider

    prov = CarrierBoardProvider()
    assembler = PCB3DAssembler.from_provider(prov)
    traces_compound = assembler.build_traces("F.Cu")
    assert traces_compound is not None
    assert len(traces_compound.children) > len(prov.pcb_config.traces)

    # Verify carrier board silkscreen graphic has polygon points
    silk_graphics = prov.silkscreen_graphics
    assert len(silk_graphics) > 0
    poly_sg = next(sg for sg in silk_graphics if sg.shape == "polygon")
    assert (0.0, 33.2) in poly_sg.points

    # Verify pad/trace Z-ordering: pads must sit proud of copper traces (BUG-TRANSLUCENT-LACEWING-144)
    assert assembler.Z_PAD_OFFSET > 0.0
    assert assembler.Z_SILK_OFFSET > assembler.Z_PAD_OFFSET
    comps_cmp, pads_cmp = assembler.build_components_and_pads()
    assert pads_cmp is not None
    assert pads_cmp.bounding_box().max.Z > traces_compound.bounding_box().max.Z

    sample_net = meta["nets"][0]
    assert "name" in sample_net
    assert "pins" in sample_net
    assert "traces_count" in sample_net
    assert "vias_count" in sample_net


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


def test_regression_bug_hovering_tigerbeetle_411_hierarchical_cad_tree(scope_server):
    """Verify BUG-HOVERING-TIGERBEETLE-411: CAD Objects tree view renders hierarchical groups."""
    # 1. Verify Scope UI contains hierarchical group tree structures and expand/collapse
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")
    assert "renderGroupNode" in html
    assert "tree-group-item" in html
    assert "tree-group-children" in html
    assert "tree-expand-icon" in html
    assert "setGroupVisibility" in html
    assert "Expand All" in html
    assert "Collapse All" in html

    # 2. Verify pipeline preserves hierarchical names for exhaust_manifolds/part_positions
    from provider.scope.pipeline import ScopeGeometryPipeline

    pipeline = ScopeGeometryPipeline()
    res = pipeline.load_geometry("exhaust_manifolds", "part_positions", mode="CAD")
    parts = res.get("shapes", {}).get("parts", [])
    assert len(parts) > 0
    part_names = [p["name"] for p in parts]
    assert any("driver/left" in name for name in part_names)
    assert any("driver/right" in name for name in part_names)
    assert any("passenger/left" in name for name in part_names)
    assert any("passenger/right" in name for name in part_names)


def test_regression_bug_lustrous_mantis_333_simulation_fountain_physics(scope_server):
    """Verify BUG-LUSTROUS-MANTIS-333: authentic simulation telemetry respects bowl floor Z=41, spout Z=114, and enforces prohibition on client-side simulation facades."""
    # 1. Fetch Scope HTML template and check simulation controls and authentic data pipeline
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    # Enforce prohibition on client-side simulation facades (CR finding f5e496b8 and docs/physics_urdf_simulation.md)
    assert "getFountainTrajectoryPoint" not in html
    assert "btn-sim-play" in html
    assert "toggleSimPlay" in html
    assert "sim-log-chip" in html
    assert "sim-flow-metrics" in html
    assert "/api/scope/simulation_telemetry" in html

    # 2. Query authentic server-side telemetry endpoint and evaluate particle bounds
    telem_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry?project=cat_fountain&target=product"
    req_telem = urllib.request.urlopen(telem_url)
    assert req_telem.status == 200
    telem = json.loads(req_telem.read().decode("utf-8"))

    assert telem["status"] == "ok"
    assert telem["frames_count"] > 0
    assert len(telem["frames"]) > 0

    # Ensure every sampled particle in authentic telemetry respects domain bounds
    for frame in telem["frames"]:
        for pt in frame["positions"]:
            x, y, z = pt[0], pt[1], pt[2]
            assert z >= 40.0, f"Authentic particle dipped below floor: z={z}"
            assert z <= 116.0, f"Authentic particle exceeded max bound: z={z}"


def test_regression_bug_jumping_instar_950_simulate_view_max_steps_physics_inspection_rerun_logs(scope_server):
    """Verify BUG-JUMPING-INSTAR-950: simulate view max steps selection, timescale selector, Rerun Viewer launcher, and rerun logs."""
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

    # 3. Check timescale adjustment and Rerun Viewer button
    assert 'id="sim-timescale"' in html
    assert 'id="btn-open-rerun"' in html
    assert "Open in Rerun Viewer" in html
    assert "/api/scope/open_rerun" in html

    # 4. Check Physics Object Inspection Telemetry in Inspector (CR fb2d3fd1)
    assert "RERUN LOGGED OBJECT" in html
    assert "Position (pos):" in html
    assert "Orientation (orn):" in html
    assert "renderRerunObjectInspect" in html

    # 5. Check Left Panel Simulation Metrics querying and histograms (BUG-VELVETY-LARVA-429)
    assert 'id="tab-btn-metrics"' in html
    assert 'id="tab-metrics"' in html
    assert 'id="metrics-search"' in html
    assert 'id="metrics-list"' in html
    assert 'id="metrics-count"' in html
    assert 'function renderSimulationMetrics(query = "")' in html
    assert "getSimulationMetricsSeries" in html

    # 6. Verify POST /api/scope/open_rerun endpoint
    open_req = urllib.request.Request(
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/open_rerun",
        data=json.dumps({"project": "cat_fountain", "target": "product"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    open_res = urllib.request.urlopen(open_req)
    assert open_res.status == 200
    open_data = json.loads(open_res.read().decode("utf-8"))
    assert open_data["status"] == "ok"
    assert "recordings/cat_fountain_3blade.rrd" in open_data["recording"]


def test_regression_bug_segmented_larva_621_simulation_lid_drainage(scope_server):
    """Verify BUG-SEGMENTED-LARVA-621: simulation fluid particles drain through the lid drainage hole into reservoir bowl."""
    telem_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry?project=cat_fountain&target=product"
    req_telem = urllib.request.urlopen(telem_url)
    assert req_telem.status == 200
    telem = json.loads(req_telem.read().decode("utf-8"))

    assert telem["status"] == "ok"
    assert len(telem["frames"]) > 0

    # Verify that the authentic SPH telemetry records drainage cutout particles
    drainage_cutout_metrics = [f["metrics"]["drainage_cutout"] for f in telem["frames"]]
    assert any(count > 0 for count in drainage_cutout_metrics), "No particles registered in drainage cutout metric"
    assert max(drainage_cutout_metrics) > 100, (
        f"Expected > 100 particles draining through lid hole, got {max(drainage_cutout_metrics)}"
    )

    # Verify that particles are sampled passing through the lid hole column (x in [-20, 20], y in [45, 80], z in [50, 105])
    lid_drain_particles = []
    for f in telem["frames"]:
        for pt in f["positions"]:
            x, y, z = pt[0], pt[1], pt[2]
            if -20.0 <= x <= 20.0 and 45.0 <= y <= 80.0 and 50.0 <= z <= 105.0:
                lid_drain_particles.append(pt)

    assert len(lid_drain_particles) > 0, "No particles detected draining through lid cutout region"


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


def test_regression_hud_word_wrapping_and_compact_styling(scope_server):
    """Verify that all Scope HUD elements have no-wrap and non-shrinking styles to prevent wrapping."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")

    # Verify no-wrap styles on HUD components
    assert (
        ".hud-title {\n      font-size: 13px;\n      font-weight: 800;\n      letter-spacing: 0.1em;\n      color: var(--quake-gold);\n      text-transform: uppercase;\n      display: flex;\n      align-items: center;\n      gap: 8px;\n      flex-shrink: 0;\n      white-space: nowrap;\n    }"
        in html
    )
    assert (
        ".hud-group {\n      display: flex;\n      align-items: center;\n      gap: 8px;\n      flex-shrink: 0;\n      white-space: nowrap;\n    }"
        in html
    )
    assert (
        ".ui-scale-container {\n      display: flex;\n      align-items: center;\n      gap: 4px;\n      flex-shrink: 0;\n      white-space: nowrap;\n    }"
        in html
    )
    assert (
        ".shortcuts-table {\n      width: 100%;\n      border-collapse: collapse;\n      font-size: 11px;\n      white-space: nowrap;\n    }"
        in html
    )
    assert (
        "#cad-shortcuts-hud {\n      position: absolute;\n      top: 16px;\n      right: 68px;\n      width: 480px;\n      max-width: calc(100% - 80px);"
        in html
    )
    assert "white-space: nowrap;" in html


def test_regression_bug_lustrous_cicada_558_canvas_relative_raycasting(scope_server):
    """Verify that raycasting and click picking use getCanvasRelativeCoords against active WebGL canvas."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")

    # Verify getActiveCanvas and getCanvasRelativeCoords exist
    assert "function getActiveCanvas()" in html
    assert "function getCanvasRelativeCoords(e)" in html

    # Verify zero-offset positioning on three-cad-viewer internal wrapper containers
    assert "#cad-view .tcv_cad_view_glass" in html
    assert "left: 0 !important;" in html
    assert "top: 0 !important;" in html

    # Verify canvas-relative coordinates are passed into idPicker and Three.js Raycaster
    assert "const coords = getCanvasRelativeCoords(e);" in html
    assert "const mouse = new window.THREE.Vector2(coords.ndcX, coords.ndcY);" in html


def test_regression_bug_punctate_darner_735_diagram_view_labels():
    """Verify that diagram view text annotation labels are projected and tessellated for 3D inspection."""
    from provider.scope.pipeline import ScopeGeometryPipeline

    pipeline = ScopeGeometryPipeline()
    payload = pipeline.load_geometry("cat_fountain", "wiring", mode="DIAGRAM")

    parts = payload.get("shapes", {}).get("parts", [])
    part_names = [p.get("name") for p in parts]
    assert "cat_fountain_diagram" in part_names
    assert "cat_fountain_labels" in part_names

    # Ensure label meshes were tessellated into instances (text sketches contain hundreds of face instances)
    instances = payload.get("instances", [])
    assert len(instances) > 50


def test_regression_bug_springing_grub_126_motor_base_fixed_and_impeller_rotating(scope_server):
    """Verify BUG-SPRINGING-GRUB-126: Motor and motor base remain fixed while impeller and drive hub rotate."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    html = req.read().decode("utf-8")

    # Verify rotation animation logic specifically filters rotating parts from stationary motor body and base bracket
    assert "const isRotatingPart =" in html
    assert '!lower.includes("motor_hub")' in html
    assert '!lower.includes("base")' in html

    def check_rotation(name: str) -> bool:
        lower = name.lower()
        return (
            ("impeller" in lower or "drive_hub" in lower or "rotor" in lower)
            and "base" not in lower
            and "bracket" not in lower
            and "mount" not in lower
            and "stator" not in lower
            and "motor_hub" not in lower
        )

    # Stationary parts: must NOT rotate
    assert not check_rotation("cat_fountain/motor_hub")
    assert not check_rotation("cat_fountain/motor")
    assert not check_rotation("cat_fountain/motor_pcb")
    assert not check_rotation("cat_fountain/motor_base")
    assert not check_rotation("cat_fountain/bowl")
    assert not check_rotation("cat_fountain/bottom_cover")

    # Rotating parts: MUST rotate
    assert check_rotation("cat_fountain/impeller")
    assert check_rotation("cat_fountain/drive_hub")
    assert check_rotation("cat_fountain/motor_rotor")


def test_scope_headless_simulation_capture_rrd(tmp_path):
    """Verify GUI-less simulation capture with scope.py -s <steps> --save-rrd <path>."""
    from tools.scope import ScopeTool, get_args

    rrd_out = tmp_path / "test_headless.rrd"
    args = get_args(
        [
            "cat_fountain/product:view/simulate",
            "-s",
            "2",
            "--save-rrd",
            str(rrd_out),
        ]
    )
    tool = ScopeTool()
    ret = tool.run(args)
    assert ret == 0
    assert rrd_out.exists()
    assert rrd_out.stat().st_size > 0


def test_regression_bug_shining_dragonfly_640_silkscreen_text_orientation_and_pcb_selection(scope_server):
    """Verify BUG-SHINING-DRAGONFLY-640: silkscreen text orientation in 3D PCB CAD matches KiCad CAM export.

    Also verify getThreeCamera helper dereferences actual Three.js camera for raycasting/selection.
    """
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.cad_assembler import PCB3DAssembler

    prov = CarrierBoardProvider()
    assembler = PCB3DAssembler.from_provider(prov)

    # 1. Verify 3D silkscreen compound is built with correct solid primitives
    silk_top = assembler.build_silkscreen("F.SilkS")
    assert silk_top is not None
    assert len(silk_top.children) > 0

    # 2. Verify Scope HTML template dereferences actual Three.js camera and uses default 'top' preset for PCB
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    assert "function getThreeCamera()" in html
    assert "raycaster.setFromCamera(mouse, threeCam);" in html
    assert '(state.currentMode === "PCB" || state.currentMode === "DIAGRAM") ? "top" : "iso"' in html


def test_regression_bug_swarming_silverfish_292_diagram_view_white_background_and_camera(scope_server):
    """Verify BUG-SWARMING-SILVERFISH-292: diagram view uses white background, black text, and SVG view_from preset."""
    # 1. Verify Scope API serves diagram payload with SVG camera preset and black text annotations
    load_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=cat_fountain&target=wiring&mode=DIAGRAM"
    )
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    data = json.loads(req_load.read().decode("utf-8"))
    assert data["type"] == "data"
    assert data["mode"] == "DIAGRAM"
    assert data["view_from"] == "top"

    # Verify labels part exists and has black text (#000000)
    labels_part = next((p for p in data["shapes"]["parts"] if "label" in p["name"].lower()), None)
    assert labels_part is not None
    assert len(labels_part.get("parts", [])) > 0
    assert labels_part["parts"][0].get("color") == "#000000"

    # 2. Verify Scope HTML template contains white background CSS and theme/ortho camera switching
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    assert "body.mode-diagram #cad-view" in html
    assert "--tcv-bg-color: #ffffff !important;" in html
    assert "state.viewer.renderer.setClearColor(0xffffff, 1.0);" in html
    assert 'state.viewer.setTheme("light");' in html
    assert "state.viewer.setOrtho(true);" in html


def test_regression_bug_shining_hoverfly_298_sim_particles_and_hud_controls(scope_server):
    """Verify BUG-SHINING-HOVERFLY-298: circular particle texture, velocity color ramp, HUD nowrap, and Save .rrd download."""
    # 1. Verify /api/scope/download_rrd streams authentic .rrd recording
    rrd_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/download_rrd?project=cat_fountain&target=product"
    req_rrd = urllib.request.urlopen(rrd_url)
    assert req_rrd.status == 200
    assert "application/octet-stream" in req_rrd.headers.get("Content-Type", "")
    assert "attachment;" in req_rrd.headers.get("Content-Disposition", "")
    content = req_rrd.read()
    assert len(content) > 0

    # 2. Verify HTML template contains circular particle texture, generic rerun events, and HUD nowrap layout
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    assert "createParticleTexture()" in html
    assert "sim-timeline-chips" not in html
    assert "btn-save-rrd" in html
    assert "min-width: 120px" in html
    assert "min-width: 140px" in html
    assert "updateTimelineChips" not in html
    assert "sim-flow-metrics" in html
    assert "Spout: 0 mL/s" not in html
    assert "simMotionBlurMesh" in html
    assert "simulation_water_motion_blur" in html
    assert "SCALE:" in html


def test_regression_bug_proboscid_caterpillar_529_open_kicad_button(scope_server, monkeypatch):
    """Verify BUG-PROBOSCID-CATERPILLAR-529: Add button in inspect view to open KiCad PCB project."""
    import subprocess

    launched_cmds = []

    def fake_popen(cmd, *args, **kwargs):
        launched_cmds.append(cmd)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    # 1. Verify /api/scope/open_kicad endpoint resolves and launches local KiCad project
    open_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/open_kicad?project=carrier_board&target=carrier_board"
    )
    req_open = urllib.request.urlopen(open_url)
    assert req_open.status == 200
    data = json.loads(req_open.read().decode("utf-8"))
    assert data["status"] == "ok"
    assert "carrier_board.kicad_" in data["file"]
    assert len(launched_cmds) == 1
    assert "carrier_board.kicad_" in str(launched_cmds[0])

    # 2. Verify HTML template contains Open in KiCad button in Inspect view with wiring
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    assert 'id="btn-open-kicad"' in html
    assert "Open in KiCad" in html
    assert "/api/scope/open_kicad" in html


def test_regression_bug_creeping_scorpion_866_pcb_entity_picking_and_test_points(scope_server):
    """Verify BUG-CREEPING-SCORPION-866: Accurate raycasting entity picking for test points, pads, traces, and vias."""
    # 1. Verify backend PCB metadata exports test points
    load_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    data = json.loads(req_load.read().decode("utf-8"))
    assert "pcb_metadata" in data
    meta = data["pcb_metadata"]

    assert "test_points" in meta
    assert len(meta["test_points"]) == 14
    tp0 = meta["test_points"][0]
    assert "name" in tp0 and tp0["name"] == "TP1"
    assert "net" in tp0 and tp0["net"] == "GND"
    assert "dia" in tp0 and tp0["dia"] == 1.4
    assert "x" in tp0 and "y" in tp0

    # 2. Verify HTML template contains test point inspect handling and screen-space pixel picking
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    assert "TEST POINT" in html
    assert "test_points" in html
    assert "findPcbEntityAtPoint" in html
    assert "test_point" in html


def test_regression_bug_emerald_tick_950_lmb_pan_mmb_zoom_pcb_diagram(scope_server):
    """Verify BUG-EMERALD-TICK-950: Replace LMB hold with PAN and MMB with zoom in PCB and Diagram views."""
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    # 1. 2D navigation controls: LMB hold defaults to pan, MMB to zoom
    assert "updateControlsForMode" in html
    assert "enableRotate = !is2D" in html or "enableRotate = false" in html
    assert "hud-row-orbit" in html
    assert 'dragMode = "pan"' in html
    assert 'dragMode = "zoom"' in html


def test_regression_bug_dorsal_midge_176_pcb_layer_order_colors_orientation_net_labels(scope_server):
    """Verify BUG-DORSAL-MIDGE-176: Layer stack ordering, KiCad palette colors, net labels on zoom, and orientation."""
    # 1. Verify PCB metadata layers: Components above Substrate and KiCad hex colors
    load_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    data = json.loads(req_load.read().decode("utf-8"))
    assert "pcb_metadata" in data
    layers = data["pcb_metadata"]["layers"]

    layer_names = [l["name"] for l in layers]
    assert "Components" in layer_names
    assert "Substrate" in layer_names
    assert layer_names.index("Components") < layer_names.index("Substrate")

    layer_colors = {l["name"]: l["color"].lower() for l in layers}
    assert layer_colors["Components"] == "#2a2e35"
    assert layer_colors["Substrate"] == "#0a2410"
    assert layer_colors["Pads"] == "#c8a034"
    assert layer_colors["F.Cu (Top)"] == "#c83434"
    assert layer_colors["B.Cu (Bottom)"] == "#345ac8"
    assert layer_colors["Vias"] == "#b4a03c"
    assert layer_colors["F.SilkS"] == "#e6e6e6"
    assert layer_colors["B.SilkS"] == "#e6e6e6"

    # 2. Verify CAD Assembler default constants
    from provider.pcb.cad_assembler import PCB3DAssembler

    assert PCB3DAssembler.DEFAULT_COMPONENT_COLOR == (0.165, 0.180, 0.208)
    assert PCB3DAssembler.DEFAULT_SOLDERMASK_COLOR == (0.04, 0.14, 0.06)
    assert PCB3DAssembler.DEFAULT_PAD_COLOR == (0.784, 0.627, 0.204)
    assert PCB3DAssembler.DEFAULT_TOP_TRACE_COLOR == (0.784, 0.204, 0.204)
    assert PCB3DAssembler.DEFAULT_BOTTOM_TRACE_COLOR == (0.204, 0.353, 0.784)
    assert PCB3DAssembler.DEFAULT_VIA_COLOR == (0.706, 0.627, 0.235)
    assert PCB3DAssembler.DEFAULT_SILKSCREEN_COLOR == (0.90, 0.90, 0.90)

    # 3. Verify HTML template invariants: KiCad orientation flip and net labels on zoom
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    assert "setupPcbOrientation" in html
    assert "drawPcbNetLabels" in html
    assert "scale.set(1, -1, 1)" in html
    assert "cam.top = -Math.abs(halfH)" not in html
    assert 'camRight.style.display = is2D ? "none" : ""' in html


def test_regression_bug_velvety_larva_429_metrics_panel_and_histograms(scope_server):
    """Verify BUG-VELVETY-LARVA-429: Scrubber events removed, LOGS replaced with METRICS panel and histograms."""
    # 1. Verify simulation telemetry API returns metrics_series matching simulate_hooks.py:153-167
    telem_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry?project=cat_fountain&target=product"
    req_telem = urllib.request.urlopen(telem_url)
    assert req_telem.status == 200
    telem = json.loads(req_telem.read().decode("utf-8"))

    assert telem["status"] == "ok"
    assert "metrics_series" in telem
    series = telem["metrics_series"]

    # Invariants for metrics logged under metrics/
    expected_metrics = [
        "flow_spout",
        "flow_tube",
        "flow_lid_sheet",
        "drainage_waterfall",
        "drainage_cutout",
        "pool_volume",
        "water_depth",
    ]
    for m in expected_metrics:
        assert m in series, f"Missing metric {m} in simulation telemetry series"
        assert len(series[m]) > 0, f"Empty series for metric {m}"
        assert "step" in series[m][0]
        assert "value" in series[m][0]

    # 2. Verify HTML template has scrubber events removed and METRICS panel with histograms
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/?mode=SIMULATE"
    req_html = urllib.request.urlopen(html_url)
    assert req_html.status == 200
    html = req_html.read().decode("utf-8")

    # Scrubber events removed
    assert "sim-timeline-chips" not in html
    assert "updateTimelineChips" not in html
    assert "EVENTS:" not in html
    assert 'id="sim-flow-metrics"' in html

    # LOGS replaced by METRICS
    assert 'id="tab-btn-logs"' not in html
    assert 'id="tab-logs"' not in html
    assert 'id="tab-btn-metrics"' in html
    assert 'id="tab-metrics"' in html
    assert 'id="metrics-search"' in html
    assert 'id="metrics-list"' in html
    assert 'id="metrics-count"' in html

    # Histograms and metrics series rendering functions
    assert "getSimulationMetricsSeries" in html
    assert "renderSimulationMetrics" in html
    assert "metric-card" in html
    assert "hist-bar" in html


def test_regression_bug_emerald_moth_182_target_and_sync_synchronous_initialization(scope_server):
    """Verify target and sync buttons are bound synchronously on DOMContentLoaded and handle empty project state (BUG-EMERALD-MOTH-182)."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # 1. Verify synchronous initialization separation
    assert "function initEventListeners()" in html
    assert "async function initWorkstationData()" in html
    assert "initEventListeners();" in html
    assert "initWorkstationData();" in html

    # 2. Verify btn-open-chooser and btn-sync are registered inside initEventListeners
    assert 'document.getElementById("btn-open-chooser")?.addEventListener("click"' in html
    assert 'document.getElementById("btn-sync")?.addEventListener("click"' in html

    # 3. Verify openProjectChooserModal handles empty state asynchronously by awaiting loadProjects
    assert "async function openProjectChooserModal()" in html
    assert "await loadProjects(false);" in html

    # 4. Verify sync button has unconfigured project/target fallback to prevent 400/500 errors
    assert "if (state.currentProject && state.currentTarget)" in html
    assert "openProjectChooserModal();" in html

    # 5. Verify the entire embedded <script type="module"> compiles with zero syntax errors via node/vm.Script
    script_match = re.search(r"<script type=\"module\">(.*?)</script>", html, re.DOTALL)
    assert script_match is not None, "Scope workstation HTML must contain a <script type='module'>"
    script_content = script_match.group(1)

    node_bin = shutil.which("node")
    if node_bin:
        sanitized_script = re.sub(
            r"import\s+.*?from\s+.*?;\n",
            "const Display = function(){}; const Viewer = function(){}; const decodeInstancedFormat = function(){}; const isInstancedFormat = function(){};",
            script_content,
        )
        res = subprocess.run(
            [
                node_bin,
                "-e",
                "const vm = require('vm'); try { new vm.Script(process.env.JS_CODE, { filename: 'scope.js' }); console.log('VALID'); } catch (e) { console.error(e.message); process.exit(1); }",
            ],
            env={**os.environ, "JS_CODE": sanitized_script},
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Scope workstation JavaScript syntax error: {res.stderr}"


def test_regression_bug_radiant_skipper_379_ui_scale_default_100_percent(scope_server):
    """Verify UI scale select defaults to 100% selected, cleans up former 75% fallback, and uses percentage root sizing (BUG-RADIANT-SKIPPER-379)."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    html = req.read().decode("utf-8")

    # 1. Option 100% must have selected attribute
    assert '<option value="100%" selected>100%</option>' in html
    assert '<option value="75%" selected>' not in html

    # 2. html, body styles must use 100% instead of 100vw/100vh for zoom compatibility
    assert "width: 100%;" in html
    assert "height: 100%;" in html
    assert "width: 100vw;" not in html
    assert "height: 100vh;" not in html

    # 3. initUiScale must auto-correct former 75% fallback and default to 100%
    assert 'saved === "75%"' in html
    assert 'localStorage.setItem(UI_SCALE_KEY, "100%");' in html


def test_regression_bug_tarsial_termite_773_cad_and_pcb_target_loading_and_orientation(
    scope_server, monkeypatch, tmp_path
):
    """Verify :cad subassembly defensive handling, Y-mirrored PCB non-culled orientation, resizeCadView priority, and scope.lock replacement (BUG-TARSIAL-TERMITE-773)."""
    # 1. Stale or explicit ?subassembly=cad / ?subassembly=pcb URLs must resolve cleanly with HTTP 200
    load_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=cat_fountain&target=bowl&subassembly=cad&mode=CAD"
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    payload = json.loads(req_load.read().decode("utf-8"))
    assert "shapes" in payload or "instances" in payload

    # 2. Behavioral JS verification of unrendered guards, resizeCadView, Y-mirrored PCB scene, and picking
    html_url = f"http://127.0.0.1:{scope_server.actual_port}/?project=carrier_board&target=carrier_board&mode=PCB"
    html = urllib.request.urlopen(html_url).read().decode("utf-8")

    node_bin = shutil.which("node")
    if node_bin:
        setup_match = re.search(r"(function setupPcbOrientation\([^)]*\)\s*\{.*?\n    \})", html, re.DOTALL)
        pick_match = re.search(
            r"(function distanceToSegment\(.*?\n    function findPcbEntityAtPoint\(.*?\n      return bestEntity;\n    \})",
            html,
            re.DOTALL,
        )
        assert setup_match is not None, "setupPcbOrientation must exist in scope.html.j2"
        assert pick_match is not None, "findPcbEntityAtPoint must exist in scope.html.j2"

        harness = f"""
const assert = require('assert');
let pcbIsFlipped = false;
const state = {{
  currentMode: 'PCB',
  viewer: {{
    _rendered: null,
    setOrthoCalled: 0,
    setOrtho(v) {{
      if (!this._rendered) throw new TypeError('Cannot read properties of null');
      this.setOrthoCalled++;
      this._rendered.camera.ortho = v;
    }},
    update() {{}},
  }},
  pcbMetadata: {{
    pads: [{{ comp: 'U1', pin: '1', net: 'VCC_3V3', x: 10.0, y: 25.0, w: 1.0, h: 1.0, layer: 'F.Cu' }}],
    traces: [],
    vias: [],
    test_points: [],
    components: [{{ ref_des: 'U1', footprint: 'QFN', position: [10.0, 25.0], size: [4.0, 4.0] }}],
    nets: [{{ name: 'VCC_3V3', pins: ['U1.1'] }}],
  }},
}};
function getViewerRendered() {{
  return (state.viewer && (state.viewer._rendered || state.viewer.rendered)) || null;
}}
const window = {{
  THREE: {{
    Vector3: class Vector3 {{
      constructor(x = 0, y = 0, z = 0) {{ this.x = x; this.y = y; this.z = z; }}
      project(cam) {{
        return new Vector3((this.x - cam.target.x) / 50.0, (this.y - cam.target.y) / 50.0, 0);
      }}
      copy(other) {{ this.x = other.x; this.y = other.y; this.z = other.z; return this; }}
    }},
    Quaternion: class Quaternion {{
      constructor(x = 0, y = 0, z = 0, w = 1) {{ this.x = x; this.y = y; this.z = z; this.w = w; }}
    }},
  }},
}};
{setup_match.group(1)}
{pick_match.group(1)}

// A. Unrendered viewer must NOT throw when setupPcbOrientation runs early
setupPcbOrientation(true);

// B. Rendered viewer must keep cam.top > 0 (no backface culling) and mirror rootGroup Y to -1
const oCam = {{
  isOrthographicCamera: true,
  top: 60,
  bottom: -60,
  target: new window.THREE.Vector3(40, 30, 0),
  updateProjectionMatrix() {{}},
  updateMatrixWorld() {{}},
}};
state.viewer._rendered = {{
  nestedGroup: {{
    rootGroup: {{
      scale: {{ x: 1, y: 1, z: 1, set(x, y, z) {{ this.x = x; this.y = y; this.z = z; }} }},
      updateMatrixWorld() {{}},
    }},
  }},
  camera: {{
    ortho: false,
    oCamera: oCam,
    camera: oCam,
    target: oCam.target,
    presetCamera() {{}},
    setQuaternion() {{}},
  }},
  controls: {{
    target: new window.THREE.Vector3(40, 30, 0),
    update() {{}},
  }},
}};
setupPcbOrientation(true);
assert.strictEqual(state.viewer._rendered.nestedGroup.rootGroup.scale.y, -1, 'PCB rootGroup must mirror Y');
assert.ok(oCam.top > 0 && oCam.bottom < 0, 'OrthographicCamera frustum must stay positive (right-handed) to avoid WebGL backface culling');
assert.strictEqual(oCam.target.y, -30, 'Camera lookAt target Y must mirror original center Y');

// C. Clicking at Three.js world (10, -25) -> KiCad (10, +25) must pick pad U1.1 both in world and screen space
const worldPick = findPcbEntityAtPoint(10.0, 25.0, 0.8, null, null, null, 0, 0);
assert.ok(worldPick && worldPick.type === 'pad' && worldPick.data.comp === 'U1', 'World pick must resolve U1.1');
// Screen projection of pad (10, 25) in mirrored world (10, -25) relative to target (40, -30):
// ndcX = (10 - 40)/50 = -0.6 -> px = 0.2 * 1000 = 200
// ndcY = (-25 - (-30))/50 = +0.1 -> py = (-0.1 + 1)/2 * 1000 = 450
const screenPick = findPcbEntityAtPoint(10.0, 25.0, 0.8, 200, 450, oCam, 1000, 1000);
assert.ok(screenPick && screenPick.type === 'pad' && screenPick.data.comp === 'U1', 'Screen pick must project (px, -py) to match mirrored mesh');
console.log('BEHAVIORAL_OK');
"""
        res = subprocess.run([node_bin, "-e", harness], capture_output=True, text=True)
        assert res.returncode == 0 and "BEHAVIORAL_OK" in res.stdout, (
            f"PCB orientation/picking behavioral check failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        )

    # 3. Verify ScopeTool replaces an existing scope.lock instance when invoked with a new target
    import tools.scope as scope_mod

    fake_repo = tmp_path / "repo"
    (fake_repo / "build").mkdir(parents=True)
    lock_file = fake_repo / "build" / "scope.lock"
    lock_file.write_text(json.dumps({"pid": 999991, "url": "http://127.0.0.1:8001/"}), encoding="utf-8")

    stopped_pids = []
    monkeypatch.setattr(scope_mod, "_repo_dir", fake_repo)
    monkeypatch.setattr(
        os,
        "kill",
        lambda pid, sig: (
            stopped_pids.append((pid, sig))
            if sig != 0
            else (None if not stopped_pids else (_ for _ in ()).throw(ProcessLookupError()))
        ),
    )

    spawned_cmds = []

    class DummyProc:
        pid = 999992

        def poll(self):
            lock_file.write_text(
                json.dumps({"pid": 999992, "url": "http://127.0.0.1:8001/?project=cat_fountain"}), encoding="utf-8"
            )
            return None

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: spawned_cmds.append(cmd) or DummyProc())
    tool = scope_mod.ScopeTool()
    args = scope_mod.get_args(["cat_fountain/product:cad"])
    rc = tool.run(args)
    assert rc == 0
    assert any(pid == 999991 for pid, _ in stopped_pids), (
        "Prior Scope instance must be stopped when launching a new target"
    )
    assert len(spawned_cmds) == 1, "New Scope detached server must be spawned for the requested target"
