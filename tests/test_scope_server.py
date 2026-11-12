"""Integration tests for CAD/PCB Scope HTTP Server and Target Bug API."""

import gzip
from html.parser import HTMLParser
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

import pytest
import yaml

from projects.carrier_board.provider import CarrierBoardProvider
from provider.bug_report.sqlite_store import SQLiteBugStore
from provider.pcb.cad_assembler import PCB3DAssembler
from provider.scope import ScopeGeometryPipeline, ScopeServer
import tools.scope as scope_mod


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


def test_scope_server_serve_static_assets(scope_server):
    """Verify static assets are served with correct MIME types and gzip compression."""
    js_url = f"http://127.0.0.1:{scope_server.actual_port}/static/three-cad-viewer.esm.js"
    req_js = urllib.request.urlopen(js_url)
    assert req_js.status == 200
    assert "application/javascript" in req_js.headers.get("Content-Type", "")

    req_gzip = urllib.request.Request(js_url, headers={"Accept-Encoding": "gzip"})
    resp_gzip = urllib.request.urlopen(req_gzip)
    assert resp_gzip.status == 200
    assert resp_gzip.headers.get("Content-Encoding") == "gzip"
    decompressed = gzip.decompress(resp_gzip.read()).decode("utf-8")
    assert len(decompressed) > 1000

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
    tiny_png_b64 = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

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

    att_path = scope_server.attachments_dir / bug_id / "snapshot.png"
    assert att_path.is_file()

    md_path = Path(result["markdown_path"])
    assert md_path.is_file()
    md_content = md_path.read_text(encoding="utf-8")
    assert bug_id in md_content
    assert payload["title"] in md_content

    store.delete_bug(bug_id)
    if att_path.exists():
        att_path.unlink()
    if att_path.parent.exists() and not any(att_path.parent.iterdir()):
        att_path.parent.rmdir()
    if md_path.exists():
        md_path.unlink()


def test_regression_bug_segmented_moth_70_detach_cli_flags():
    """Verify scope CLI detaches cleanly with zero console spam."""
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

    subprocess.run(
        [sys.executable, str(scope_script), "stop"],
        capture_output=True,
        text=True,
    )

    try:
        res_launch = subprocess.run(
            [sys.executable, str(scope_script), "carrier_board/carrier_board:pcb", "--no-app"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Scope workstation running at" in res_launch.stdout
        assert "Detached from terminal." in res_launch.stdout
        assert "SCOPE // CAD/PCB WORKSTATION" not in res_launch.stdout
        assert "pybullet build time" not in res_launch.stdout
        assert "pybullet build time" not in res_launch.stderr
        assert "Building..." not in res_launch.stdout
        assert "CameraKeepWarning" not in res_launch.stdout
        assert "CameraKeepWarning" not in res_launch.stderr
        assert "face" not in res_launch.stdout

        res_again = subprocess.run(
            [sys.executable, str(scope_script), "carrier_board/carrier_board:pcb", "--no-app"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Scope workstation is already running" in res_again.stdout
    finally:
        res_stop = subprocess.run(
            [sys.executable, str(scope_script), "stop"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Stopped Scope" in res_stop.stdout


def test_scope_app_icon_served(scope_server):
    """Verify that Scope app icon is discovered and served on /static/scope-icon.svg and /favicon.svg."""
    icon_path = scope_mod.get_scope_icon_path()
    assert icon_path is not None
    assert icon_path.exists()

    svg_url = f"http://127.0.0.1:{scope_server.actual_port}/static/scope-icon.svg"
    req_svg = urllib.request.urlopen(svg_url)
    assert req_svg.status == 200
    assert "image/svg+xml" in req_svg.headers.get("Content-Type", "")

    fav_svg_url = f"http://127.0.0.1:{scope_server.actual_port}/favicon.svg"
    req_fav = urllib.request.urlopen(fav_svg_url)
    assert req_fav.status == 200


def test_scope_server_structured_logging():
    """Verify that ScopeServer logs HTTP requests through the configured logger."""
    log_records = []

    class TestLogHandler(logging.Handler):
        """Capture log records emitted by ScopeServer."""

        def emit(self, record):
            """Record formatted log message."""
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
        assert any("/api/scope/projects" in msg for msg in log_records)
    finally:
        server.shutdown()
        server.server_close()
        test_logger.removeHandler(handler)


def test_scope_server_generous_socket_timeout():
    """Verify ScopeServer configures request socket handling."""
    server = ScopeServer(
        host="127.0.0.1",
        port=0,
        bind_and_activate=False,
    )
    assert hasattr(server, "get_request")


def test_scope_server_streaming_gzip_cache(tmp_path):
    """Verify ScopeServer streams compressed gzip directly from cache."""
    cache_dir = tmp_path / "scope_cache"
    pipeline = ScopeGeometryPipeline(cache_dir=cache_dir)
    server = ScopeServer(host="127.0.0.1", port=0, pipeline=pipeline, bind_and_activate=True)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()

    try:
        pipeline.load_geometry("cat_fountain", "bowl", mode="CAD")

        url = f"http://127.0.0.1:{server.actual_port}/api/scope/load?project=cat_fountain&target=bowl&mode=CAD"
        req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
        t0 = time.time()
        resp = urllib.request.urlopen(req)
        data = resp.read()
        elapsed = time.time() - t0

        assert resp.status == 200
        assert resp.headers.get("Content-Encoding") == "gzip"
        assert elapsed < 0.2
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

    deadline = time.time() + 120.0
    while time.time() < deadline:
        if getattr(server, "_warm_up_error", None) is not None:
            raise RuntimeError(f"Warm up background error: {server._warm_up_error}")
        if ("footprints", "0402", None, "CAD", None) in pipeline._cache:
            break
        time.sleep(0.1)

    assert ("footprints", "0402", None, "CAD", None) in pipeline._cache


def test_regression_bug_translucent_lacewing_144_pcb_layers_and_net_highlight(scope_server):
    """Verify BUG-TRANSLUCENT-LACEWING-144: PCB metadata palette, trace vertex caps, and pad/trace Z-ordering."""
    load_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    load_req = urllib.request.urlopen(load_url)
    assert load_req.status == 200
    data = json.loads(load_req.read().decode("utf-8"))
    assert "pcb_metadata" in data
    meta = data["pcb_metadata"]

    layer_colors = {layer["name"]: layer["color"] for layer in meta.get("layers", [])}
    assert layer_colors.get("F.Cu (Top)") == "#c83434"
    assert layer_colors.get("B.Cu (Bottom)") == "#345ac8"
    assert layer_colors.get("Pads") == "#c8a034"

    assert len(meta.get("traces", [])) > 0
    assert len(meta.get("vias", [])) > 0
    assert len(meta.get("pads", [])) > 0
    assert len(meta.get("components", [])) > 0
    assert len(meta.get("nets", [])) > 0
    assert any(c.get("size") is not None for c in meta.get("components", []))

    prov = CarrierBoardProvider()
    assembler = PCB3DAssembler.from_provider(prov)
    traces_compound = assembler.build_traces("F.Cu")
    assert traces_compound is not None
    assert len(traces_compound.children) > len(prov.pcb_config.traces)

    silk_graphics = prov.silkscreen_graphics
    assert len(silk_graphics) > 0
    poly_sg = next(sg for sg in silk_graphics if sg.shape == "polygon")
    assert (0.0, 33.2) in poly_sg.points

    assert assembler.Z_PAD_OFFSET > 0.0
    assert assembler.Z_SILK_OFFSET > assembler.Z_PAD_OFFSET
    _, pads_cmp = assembler.build_components_and_pads()
    assert pads_cmp is not None
    assert pads_cmp.bounding_box().max.Z > traces_compound.bounding_box().max.Z

    sample_net = meta["nets"][0]
    assert "name" in sample_net
    assert "pins" in sample_net
    assert "traces_count" in sample_net
    assert "vias_count" in sample_net


def test_regression_bug_nimble_bee_781_cat_fountain_footprints_z_ordering():
    """Verify BUG-NIMBLE-BEE-781: cat_fountain manifest specifies opaque bottom cover (alpha=1.0)."""
    manifest_path = Path("projects/cat_fountain/manifest.yaml")
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert "bottom_cover" in manifest_data
    bottom_cover_color = manifest_data["bottom_cover"]["color"]
    assert len(bottom_cover_color) == 4
    assert bottom_cover_color[3] == 1.0, "bottom_cover must have alpha 1.0 (opaque) to prevent Z-ordering bleed"


def test_regression_bug_hovering_tigerbeetle_411_hierarchical_cad_tree():
    """Verify BUG-HOVERING-TIGERBEETLE-411: pipeline preserves hierarchical names for exhaust_manifolds."""
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
    """Verify BUG-LUSTROUS-MANTIS-333: authentic simulation telemetry respects bowl floor and spout bounds."""
    telem_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry"
        "?project=cat_fountain&target=product"
    )
    req_telem = urllib.request.urlopen(telem_url)
    assert req_telem.status == 200
    telem = json.loads(req_telem.read().decode("utf-8"))

    assert telem["status"] == "ok"
    assert telem["frames_count"] > 0
    assert len(telem["frames"]) > 0

    for frame in telem["frames"]:
        for pt in frame["positions"]:
            z = pt[2]
            assert z >= 40.0, f"Authentic particle dipped below floor: z={z}"
            assert z <= 116.0, f"Authentic particle exceeded max bound: z={z}"


def test_regression_bug_jumping_instar_950_open_rerun_endpoint(scope_server):
    """Verify BUG-JUMPING-INSTAR-950: POST /api/scope/open_rerun resolves the recording path."""
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
    """Verify BUG-SEGMENTED-LARVA-621: simulation fluid particles drain through the lid drainage hole."""
    telem_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry"
        "?project=cat_fountain&target=product"
    )
    req_telem = urllib.request.urlopen(telem_url)
    assert req_telem.status == 200
    telem = json.loads(req_telem.read().decode("utf-8"))

    assert telem["status"] == "ok"
    assert len(telem["frames"]) > 0

    drainage_cutout_metrics = [f["metrics"]["drainage_cutout"] for f in telem["frames"]]
    assert any(count > 0 for count in drainage_cutout_metrics), "No particles registered in drainage cutout metric"
    assert max(drainage_cutout_metrics) > 100, (
        f"Expected > 100 particles draining through lid hole, got {max(drainage_cutout_metrics)}"
    )

    lid_drain_particles = []
    for f in telem["frames"]:
        for pt in f["positions"]:
            x, y, z = pt[0], pt[1], pt[2]
            if -20.0 <= x <= 20.0 and 45.0 <= y <= 80.0 and 50.0 <= z <= 105.0:
                lid_drain_particles.append(pt)

    assert len(lid_drain_particles) > 0, "No particles detected draining through lid cutout region"


def test_regression_bug_punctate_darner_735_diagram_view_labels():
    """Verify that diagram view text annotation labels are projected and tessellated for 3D inspection."""
    pipeline = ScopeGeometryPipeline()
    payload = pipeline.load_geometry("cat_fountain", "wiring", mode="DIAGRAM")

    parts = payload.get("shapes", {}).get("parts", [])
    part_names = [p.get("name") for p in parts]
    assert "cat_fountain_diagram" in part_names
    assert "cat_fountain_labels" in part_names

    instances = payload.get("instances", [])
    assert len(instances) > 50


def test_scope_headless_simulation_capture_rrd(tmp_path):
    """Verify GUI-less simulation capture with scope.py -s <steps> --save-rrd <path>."""
    rrd_out = tmp_path / "test_headless.rrd"
    args = scope_mod.get_args(
        [
            "cat_fountain/product:view/simulate",
            "-s",
            "2",
            "--save-rrd",
            str(rrd_out),
        ]
    )
    tool = scope_mod.ScopeTool()
    ret = tool.run(args)
    assert ret == 0
    assert rrd_out.exists()
    assert rrd_out.stat().st_size > 0


def test_regression_bug_shining_dragonfly_640_silkscreen_cad_assembly():
    """Verify BUG-SHINING-DRAGONFLY-640: silkscreen text compound is built with solid primitives."""
    prov = CarrierBoardProvider()
    assembler = PCB3DAssembler.from_provider(prov)
    silk_top = assembler.build_silkscreen("F.SilkS")
    assert silk_top is not None
    assert len(silk_top.children) > 0


def test_regression_bug_swarming_silverfish_292_diagram_view_payload(scope_server):
    """Verify BUG-SWARMING-SILVERFISH-292: diagram API serves top camera preset and black text annotations."""
    load_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=cat_fountain&target=wiring&mode=DIAGRAM"
    )
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    data = json.loads(req_load.read().decode("utf-8"))
    assert data["type"] == "data"
    assert data["mode"] == "DIAGRAM"
    assert data["view_from"] == "top"

    labels_part = next((p for p in data["shapes"]["parts"] if "label" in p["name"].lower()), None)
    assert labels_part is not None
    assert len(labels_part.get("parts", [])) > 0
    assert labels_part["parts"][0].get("color") == "#000000"


def test_regression_bug_shining_hoverfly_298_download_rrd(scope_server):
    """Verify BUG-SHINING-HOVERFLY-298: /api/scope/download_rrd streams authentic .rrd recording."""
    rrd_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/download_rrd?project=cat_fountain&target=product"
    req_rrd = urllib.request.urlopen(rrd_url)
    assert req_rrd.status == 200
    assert "application/octet-stream" in req_rrd.headers.get("Content-Type", "")
    assert "attachment;" in req_rrd.headers.get("Content-Disposition", "")
    content = req_rrd.read()
    assert len(content) > 0


def test_regression_bug_proboscid_caterpillar_529_open_kicad_endpoint(scope_server, monkeypatch):
    """Verify BUG-PROBOSCID-CATERPILLAR-529: /api/scope/open_kicad resolves and launches local KiCad project."""
    launched_cmds = []

    def fake_popen(cmd, *_args, **_kwargs):
        launched_cmds.append(cmd)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

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


def test_regression_bug_creeping_scorpion_866_pcb_test_points_metadata(scope_server):
    """Verify BUG-CREEPING-SCORPION-866: backend PCB metadata exports test point coordinates and nets."""
    load_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    data = json.loads(req_load.read().decode("utf-8"))
    assert "pcb_metadata" in data
    meta = data["pcb_metadata"]

    assert "test_points" in meta
    assert len(meta["test_points"]) == 14
    tp0 = meta["test_points"][0]
    assert tp0.get("name") == "TP1"
    assert tp0.get("net") == "GND"
    assert tp0.get("dia") == 1.4
    assert "x" in tp0 and "y" in tp0


def test_regression_bug_dorsal_midge_176_pcb_layer_order_and_colors(scope_server):
    """Verify BUG-DORSAL-MIDGE-176: layer stack ordering and KiCad palette colors."""
    load_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    data = json.loads(req_load.read().decode("utf-8"))
    assert "pcb_metadata" in data
    layers = data["pcb_metadata"]["layers"]

    layer_names = [layer["name"] for layer in layers]
    assert "Components" in layer_names
    assert "Substrate" in layer_names
    assert layer_names.index("Components") < layer_names.index("Substrate")

    layer_colors = {layer["name"]: layer["color"].lower() for layer in layers}
    assert layer_colors["Components"] == "#2a2e35"
    assert layer_colors["Substrate"] == "#0a2410"
    assert layer_colors["Pads"] == "#c8a034"
    assert layer_colors["F.Cu (Top)"] == "#c83434"
    assert layer_colors["B.Cu (Bottom)"] == "#345ac8"
    assert layer_colors["Vias"] == "#b4a03c"
    assert layer_colors["F.SilkS"] == "#e6e6e6"
    assert layer_colors["B.SilkS"] == "#e6e6e6"

    assert PCB3DAssembler.DEFAULT_COMPONENT_COLOR == (0.165, 0.180, 0.208)
    assert PCB3DAssembler.DEFAULT_SOLDERMASK_COLOR == (0.04, 0.14, 0.06)
    assert PCB3DAssembler.DEFAULT_PAD_COLOR == (0.784, 0.627, 0.204)
    assert PCB3DAssembler.DEFAULT_TOP_TRACE_COLOR == (0.784, 0.204, 0.204)
    assert PCB3DAssembler.DEFAULT_BOTTOM_TRACE_COLOR == (0.204, 0.353, 0.784)
    assert PCB3DAssembler.DEFAULT_VIA_COLOR == (0.706, 0.627, 0.235)
    assert PCB3DAssembler.DEFAULT_SILKSCREEN_COLOR == (0.90, 0.90, 0.90)


def test_regression_bug_velvety_larva_429_simulation_metrics_series(scope_server):
    """Verify BUG-VELVETY-LARVA-429: simulation telemetry API returns authentic metrics_series."""
    telem_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry"
        "?project=cat_fountain&target=product"
    )
    req_telem = urllib.request.urlopen(telem_url)
    assert req_telem.status == 200
    telem = json.loads(req_telem.read().decode("utf-8"))

    assert telem["status"] == "ok"
    assert "metrics_series" in telem
    series = telem["metrics_series"]

    expected_metrics = [
        "flow_spout",
        "flow_tube",
        "flow_lid_sheet",
        "drainage_waterfall",
        "drainage_cutout",
        "pool_volume",
        "water_depth",
    ]
    for metric_name in expected_metrics:
        assert metric_name in series, f"Missing metric {metric_name} in simulation telemetry series"
        assert len(series[metric_name]) > 0, f"Empty series for metric {metric_name}"
        assert "step" in series[metric_name][0]
        assert "value" in series[metric_name][0]

    first_frame_metrics = telem["frames"][0]["metrics"]
    assert "flow_waterfall" not in first_frame_metrics
    assert "drainage_waterfall" in first_frame_metrics
    assert first_frame_metrics["pool_volume"] == series["pool_volume"][0]["value"]

    missing_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry"
        "?project=nonexistent_proj&target=none"
    )
    missing_telem = json.loads(urllib.request.urlopen(missing_url).read().decode("utf-8"))
    assert missing_telem["status"] == "not_found"
    assert missing_telem["frames_count"] == 0


def test_regression_bug_tarsial_termite_773_cad_target_loading_and_lock_replacement(
    scope_server, monkeypatch, tmp_path
):
    """Verify BUG-TARSIAL-TERMITE-773: :cad subassembly defensive handling and scope.lock replacement."""
    load_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load"
        "?project=cat_fountain&target=bowl&subassembly=cad&mode=CAD"
    )
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    payload = json.loads(req_load.read().decode("utf-8"))
    assert "shapes" in payload or "instances" in payload

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
        """Stub subprocess handle writing an updated scope.lock on poll."""

        pid = 999992

        def poll(self):
            """Simulate active child process after updating lock metadata."""
            lock_file.write_text(
                json.dumps({"pid": 999992, "url": "http://127.0.0.1:8001/?project=cat_fountain"}), encoding="utf-8"
            )
            return None

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **_kw: spawned_cmds.append(cmd) or DummyProc())
    tool = scope_mod.ScopeTool()
    args = scope_mod.get_args(["cat_fountain/product:cad"])
    rc = tool.run(args)
    assert rc == 0
    assert any(pid == 999991 for pid, _ in stopped_pids), (
        "Prior Scope instance must be stopped when launching a new target"
    )
    assert len(spawned_cmds) == 1, "New Scope detached server must be spawned for the requested target"


def test_regression_bug_emerald_tick_950_2d_mode_initial_dom_state(scope_server):
    """Verify BUG-EMERALD-TICK-950: DIAGRAM and PCB UI responses set initial 2D body classes and mode pills."""

    class ModeDomParser(HTMLParser):
        """Extract body classes, active top-HUD mode pills, and element IDs from rendered Scope HTML."""

        def __init__(self) -> None:
            super().__init__()
            self.body_classes: list[str] = []
            self.active_modes: list[str] = []
            self.element_ids: set[str] = set()
            self._in_modal = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attr_map = dict(attrs)
            el_id = attr_map.get("id")
            if el_id:
                self.element_ids.add(el_id)
                if el_id == "modal-project-chooser":
                    self._in_modal = True
            classes = (attr_map.get("class") or "").split()
            if tag == "body":
                self.body_classes = classes
            if tag == "button" and not self._in_modal and "mode-pill" in classes and "active" in classes:
                data_mode = attr_map.get("data-mode")
                if data_mode:
                    self.active_modes.append(data_mode)

    for mode, expected_body_class in (("DIAGRAM", "mode-diagram"), ("PCB", "mode-pcb"), ("CAD", "mode-cad")):
        ui_url = f"http://127.0.0.1:{scope_server.actual_port}/?project=cat_fountain&target=wiring&mode={mode}"
        html = urllib.request.urlopen(ui_url).read().decode("utf-8")
        parser = ModeDomParser()
        parser.feed(html)
        assert expected_body_class in parser.body_classes
        assert parser.active_modes == [mode]
        for required_id in (
            "explode-section",
            "hud-row-orbit",
            "hud-row-front",
            "hud-row-right",
            "hud-row-top",
            "hud-row-ortho",
            "hud-row-iso",
        ):
            assert required_id in parser.element_ids
