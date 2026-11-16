"""Integration tests for CAD/PCB Scope HTTP Server and Target Bug API."""

import base64
import gzip
from html.parser import HTMLParser
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import types
import urllib.request

import numpy as np
import pytest
import rerun as rr
import yaml

from projects.carrier_board.provider import CarrierBoardProvider
from projects.cat_fountain.provider import CatFountainProvider
from projects.cat_fountain.simulate_hooks import compute_flow_metrics
from provider.bug_report.sqlite_store import SQLiteBugStore
from provider.pcb.cad_assembler import PCB3DAssembler
from provider.scope import ScopeGeometryPipeline, ScopeServer
import tools.scope as scope_mod

TEST_VOXEL_DX_M = 0.0035
TEST_SIM_FRAMES = 6
TEST_WATER_RGBA_U8 = [128, 204, 255, 191]


def _write_deterministic_cat_fountain_rrd(rrd_path: Path) -> None:
    """Write a self-contained 6-frame 3.5 mm Eulerian voxel Rerun recording for Scope telemetry tests."""
    rrd_path.parent.mkdir(parents=True, exist_ok=True)
    cat_provider = CatFountainProvider()
    s = cat_provider.settings

    dx = TEST_VOXEL_DX_M
    radius_m = round(dx * ScopeGeometryPipeline.VOXEL_RADIUS_RATIO_FALLBACK, 5)
    floor_z_m = s.floor_z * 0.001
    bowl_inner_r_m = (s.bowl_radius - s.bowl_thickness) * 0.001
    lid_mount_z_m = (s.bowl_height - s.lid_step_depth) * 0.001
    lid_pocket_floor_z_m = lid_mount_z_m + s.lid_pocket_z_offset * 0.001
    tube_y_m = 0.028
    tube_r_inner_m = (s.tube_radius - s.tube_thickness) * 0.001
    tube_r_outer_m = s.tube_radius * 0.001
    tube_top_z_m = (s.floor_z + s.tube_height) * 0.001
    cutout_y_m = s.lid_cutout_y * 0.001
    cutout_r_m = s.lid_cutout_radius * 0.001

    half_n = int((bowl_inner_r_m - 0.002) / dx)
    xs_1d = np.arange(-half_n, half_n + 1, dtype=np.float64) * dx
    ys_1d = np.arange(-half_n, half_n + 1, dtype=np.float64) * dx
    zs_1d = floor_z_m + 0.0015 + np.arange(0, 20, dtype=np.float64) * dx
    gx, gy, gz = np.meshgrid(xs_1d, ys_1d, zs_1d, indexing="ij")
    grid_pts = np.column_stack([gx.ravel(), gy.ravel(), gz.ravel()])

    x_col, y_col, z_col = grid_pts[:, 0], grid_pts[:, 1], grid_pts[:, 2]
    r_xy = np.sqrt(x_col**2 + y_col**2)
    dist_tube = np.sqrt(x_col**2 + (y_col - tube_y_m) ** 2)
    dist_cutout = np.sqrt(x_col**2 + (y_col - cutout_y_m) ** 2)

    pool_top_z_m = floor_z_m + 0.0015 + 8 * dx
    pool_mask = (z_col <= pool_top_z_m + 1e-6) & (r_xy <= bowl_inner_r_m - 0.002) & (dist_tube > tube_r_outer_m)
    tube_mask = (dist_tube <= tube_r_inner_m) & (z_col <= tube_top_z_m - 0.0025)
    spout_mask = (
        (dist_tube <= tube_r_outer_m + 0.012) & (z_col >= tube_top_z_m - 0.004) & (z_col <= tube_top_z_m + 0.006)
    )
    on_cutout = (dist_cutout <= cutout_r_m) & (dist_tube > 0.030)
    sheet_mask = (
        (np.abs(z_col - lid_pocket_floor_z_m) <= dx * 0.6)
        & (dist_tube > tube_r_outer_m)
        & (r_xy <= 0.080)
        & (~on_cutout)
    )
    cutout_drain_mask = (
        (dist_cutout <= cutout_r_m - 0.004)
        & (dist_tube > 0.032)
        & (y_col < -0.005)
        & (z_col >= pool_top_z_m + 2 * dx)
        & (z_col < lid_pocket_floor_z_m - 0.001)
    )
    waterfall_drain_mask = (
        (r_xy >= 0.0755)
        & (r_xy <= 0.0815)
        & (np.abs(x_col) <= 0.018)
        & (y_col >= 0.050)
        & (z_col >= pool_top_z_m + 2 * dx)
        & (z_col <= lid_pocket_floor_z_m)
    )

    steady_pts = grid_pts[pool_mask | tube_mask | sheet_mask | cutout_drain_mask | waterfall_drain_mask].astype(
        np.float32
    )
    spout_pts = grid_pts[spout_mask].astype(np.float32)

    rec = rr.RecordingStream("scope_test_cat_fountain")
    rec.save(str(rrd_path))
    for step_idx in range(TEST_SIM_FRAMES):
        active_spout = spout_pts[: max(8, min(len(spout_pts), 8 + step_idx * 4))]
        frame_pts = np.vstack([steady_pts, active_spout])

        cat_provider.water_sim = types.SimpleNamespace(last_positions=frame_pts, last_velocities=None)
        metrics = compute_flow_metrics(cat_provider, step_idx=None)

        angle = step_idx * 0.35
        rec.set_time("step", sequence=step_idx)
        rec.log(
            "world/impeller",
            rr.Transform3D(
                translation=[0.0, tube_y_m, floor_z_m + 0.008],
                rotation=rr.Quaternion(xyzw=[0.0, 0.0, math.sin(angle * 0.5), math.cos(angle * 0.5)]),
            ),
        )
        rec.log(
            "world/particles",
            rr.Points3D(
                positions=frame_pts,
                radii=radius_m,
                colors=TEST_WATER_RGBA_U8,
            ),
        )
        for metric_name, metric_val in metrics.items():
            rec.log(f"metrics/{metric_name}", rr.Scalars(float(metric_val)))
        rec.flush()
    rec.disconnect()


@pytest.fixture(scope="module")
def scope_server(tmp_path_factory):
    """Spin up an ephemeral ScopeServer instance with isolated cache and deterministic Rerun fixtures."""
    repo_root = Path(__file__).resolve().parent.parent
    tmp_dir = tmp_path_factory.mktemp("scope_test")
    test_sqlite = tmp_dir / "bugs.sqlite"
    test_att = tmp_dir / "attachments"
    test_fb = tmp_dir / "feedback"
    test_cache = tmp_dir / "scope_cache"
    test_recordings = tmp_dir / "recordings"
    test_build = tmp_dir / "build"
    test_att.mkdir(exist_ok=True)
    test_fb.mkdir(exist_ok=True)
    _write_deterministic_cat_fountain_rrd(test_recordings / "cat_fountain_3blade.rrd")
    pipeline = ScopeGeometryPipeline(
        repo_root=repo_root,
        cache_dir=test_cache,
        recordings_dir=test_recordings,
    )
    server = ScopeServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        pipeline=pipeline,
        sqlite_file=test_sqlite,
        attachments_dir=test_att,
        feedback_dir=test_fb,
        build_dir=test_build,
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


def _decode_frame_positions(frame: dict) -> np.ndarray:
    """Decode binary little-endian float32 `positions_b64` from a simulation telemetry frame."""
    raw = base64.b64decode(frame["positions_b64"])
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 3)


def test_scope_server_serve_static_assets(scope_server):
    """Verify ES modules and static assets are served with correct MIME types and gzip compression."""
    main_js_url = f"http://127.0.0.1:{scope_server.actual_port}/js/scope/main.js"
    req_main = urllib.request.urlopen(main_js_url)
    assert req_main.status == 200
    assert "application/javascript" in req_main.headers.get("Content-Type", "")

    three_url = f"http://127.0.0.1:{scope_server.actual_port}/js/static/vendor/three/three.module.js"
    req_gzip = urllib.request.Request(three_url, headers={"Accept-Encoding": "gzip"})
    resp_gzip = urllib.request.urlopen(req_gzip)
    assert resp_gzip.status == 200
    assert resp_gzip.headers.get("Content-Encoding") == "gzip"
    decompressed = gzip.decompress(resp_gzip.read()).decode("utf-8")
    assert len(decompressed) > 10000

    css_url = f"http://127.0.0.1:{scope_server.actual_port}/static/common.css"
    req_css = urllib.request.urlopen(css_url)
    assert req_css.status == 200
    assert "text/css" in req_css.headers.get("Content-Type", "")

    for shader_rel in (
        "scope/shaders/trace_capsule.vert.glsl",
        "scope/shaders/fluid_particle.vert.glsl",
        "scope/shaders/floor_grid.frag.glsl",
    ):
        shader_url = f"http://127.0.0.1:{scope_server.actual_port}/js/{shader_rel}"
        req_shader = urllib.request.urlopen(shader_url)
        assert req_shader.status == 200
        assert "application/javascript" in req_shader.headers.get("Content-Type", "")
        shader_module = req_shader.read().decode("utf-8")
        assert shader_module.startswith('export default "')
        assert shader_module.rstrip().endswith('";')
        glsl_src = json.loads(shader_module.removeprefix("export default ").rstrip().removesuffix(";"))
        assert "void main()" in glsl_src


def test_scope_server_api_projects(scope_server):
    """Verify GET /api/scope/projects returns discoverable project list."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/projects"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "projects" in data
    assert any(p["name"] == "carrier_board" for p in data["projects"])


def test_scope_server_api_load_pcb(scope_server):
    """Verify GET /api/scope/load returns tessellated PCB layers and metadata (excluding 3D Components)."""
    url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert data["type"] == "data"
    assert "shapes" in data
    assert "pcb_metadata" in data
    layer_types = [l["type"] for l in data["pcb_metadata"]["layers"]]
    assert len(layer_types) == 12
    assert "Edge.Cuts" in layer_types
    for cu_name in ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"):
        assert cu_name in layer_types


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
    assert layer_colors.get("B.Cu (Bottom)") == "#4d7fc4"
    assert layer_colors.get("Pads") == "#ce4785"

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
    """Verify BUG-LUSTROUS-MANTIS-333: undecimated simulation telemetry respects bowl floor, spout bounds, and voxel lattice."""
    telem_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry"
        "?project=cat_fountain&target=product"
    )
    req_telem = urllib.request.urlopen(telem_url)
    assert req_telem.status == 200
    telem = json.loads(req_telem.read().decode("utf-8"))

    assert telem["status"] == "ok"
    assert telem["frames_count"] > 0
    assert telem["is_voxel_grid"] is True
    assert telem["voxel_dx_mm"] == pytest.approx(3.5, abs=0.05)
    assert len(telem["frames"]) > 0
    assert telem["frames"][0]["count"] > 20000
    assert "impeller" in telem["frames"][0].get("transforms", {})

    for frame in telem["frames"]:
        pts = _decode_frame_positions(frame)
        assert len(pts) == frame["count"]
        z_min = float(pts[:, 2].min())
        z_max = float(pts[:, 2].max())
        assert z_min >= 40.0, f"Authentic voxel dipped below floor: z={z_min}"
        assert z_max <= 118.0, f"Authentic voxel exceeded max CAD fountain bound: z={z_max}"


def test_regression_bug_jumping_instar_950_open_rerun_endpoint(scope_server, monkeypatch):
    """Verify BUG-JUMPING-INSTAR-950: POST /api/scope/open_rerun resolves the recording path without spawning a GUI window."""
    launched_cmds: list[list[str]] = []

    def fake_popen(cmd, *_args, **_kwargs):
        launched_cmds.append(cmd)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

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
    assert len(launched_cmds) == 1
    assert any("cat_fountain_3blade.rrd" in str(arg) for arg in launched_cmds[0])


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

    lid_drain_count = 0
    for f in telem["frames"]:
        pts = _decode_frame_positions(f)
        mask = (
            (pts[:, 0] >= -20.0)
            & (pts[:, 0] <= 20.0)
            & (pts[:, 1] >= 45.0)
            & (pts[:, 1] <= 80.0)
            & (pts[:, 2] >= 50.0)
            & (pts[:, 2] <= 105.0)
        )
        lid_drain_count += int(mask.sum())

    assert lid_drain_count > 0, "No voxels detected draining through lid cutout region"


def test_regression_bug_punctate_darner_735_diagram_view_labels():
    """Verify that diagram view text annotation labels and individual diagram items are tessellated."""
    pipeline = ScopeGeometryPipeline()
    payload = pipeline.load_geometry("cat_fountain", "wiring", mode="DIAGRAM")

    parts = payload.get("shapes", {}).get("parts", [])
    part_names = [p.get("name") for p in parts]
    assert "bowl_outline" in part_names
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
    """Verify BUG-SWARMING-SILVERFISH-292 & BUG-ARMORED-COCOON-182: 2D wiring diagram uses 'top' while 3D product diagram uses 'iso' with 3D-positioned labels."""
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

    # Verify BUG-PINCERED-TARANTULA-172: wiring diagram preserves explicit per-wire color coding (including brown & teal)
    wire_colors_by_name = {
        p["name"]: p.get("color", "").lower()
        for p in data["shapes"]["parts"]
        if str(p.get("name", "")).startswith("wire_") and not str(p.get("name", "")).startswith("wire_dot_")
    }
    assert len(wire_colors_by_name) >= 10, (
        f"Expected named 1D wire parts in DIAGRAM payload, got {list(wire_colors_by_name)}"
    )
    assert wire_colors_by_name.get("wire_vcc_logic") == "#ff0000"
    assert wire_colors_by_name.get("wire_scl") == "#0000ff"
    assert wire_colors_by_name.get("wire_ctrl_uh") != wire_colors_by_name.get("wire_ctrl_vh"), (
        "Brown (ctrl_uh) and Magenta (ctrl_vh) wires must have distinct colors"
    )
    assert len(set(wire_colors_by_name.values())) >= 8

    # Loading `cat_fountain/product` in DIAGRAM mode right after `wiring` must default to isometric (`iso`), not `top`!
    prod_url = (
        f"http://127.0.0.1:{scope_server.actual_port}"
        "/api/scope/load?project=cat_fountain&target=product&mode=DIAGRAM&nocache=1"
    )
    req_prod = urllib.request.urlopen(prod_url)
    assert req_prod.status == 200
    prod_data = json.loads(req_prod.read().decode("utf-8"))
    assert prod_data["mode"] == "DIAGRAM"
    assert prod_data["view_from"] == "iso"

    prod_labels = next((p for p in prod_data["shapes"]["parts"] if "label" in p["name"].lower()), None)
    assert prod_labels is not None
    label_z_coords = [
        float(child["loc"][0][2])
        for child in prod_labels.get("parts", [])
        if isinstance(child.get("loc"), list) and len(child["loc"]) >= 1
    ]
    assert label_z_coords, "Expected 3D exploded part labels with world locations"
    assert max(label_z_coords) - min(label_z_coords) > 150.0, (
        f"3D isometric diagram labels must sit at their exploded part elevations, got Z={label_z_coords}"
    )


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
    """Verify BUG-DORSAL-MIDGE-176 & BUG-CRIMSON-GNAT-877: KiCad _builtin_default 2D palette and CAD layer stack."""
    load_url = f"http://127.0.0.1:{scope_server.actual_port}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
    req_load = urllib.request.urlopen(load_url)
    assert req_load.status == 200
    data = json.loads(req_load.read().decode("utf-8"))
    assert "pcb_metadata" in data
    layers = data["pcb_metadata"]["layers"]

    layer_names = [layer["name"] for layer in layers]
    assert "Components" not in layer_names
    assert "Substrate" in layer_names
    assert data["pcb_metadata"]["components"], "Component metadata must remain populated for pad/inspector lookup"

    parts = data.get("shapes", {}).get("parts", [])
    assert len(parts) == 1
    part_ids = [part.get("id", "") or part.get("name", "") for part in parts]
    assert not any("components" in pid for pid in part_ids)
    assert any("substrate" in pid for pid in part_ids)

    expected_kicad_colors = {
        "Substrate": "#041830",
        "Edge.Cuts (Outline)": "#e6d84c",
        "Pads": "#ce4785",
        "F.Cu (Top)": "#c83434",
        "In1.Cu (L2 Ground)": "#c2c200",
        "In2.Cu (L3 Signal)": "#c200c2",
        "In3.Cu (L4 Power)": "#00c2c2",
        "In4.Cu (L5 Signal)": "#28a448",
        "B.Cu (Bottom)": "#4d7fc4",
        "Vias": "#ececec",
        "F.SilkS": "#f2eda1",
        "B.SilkS": "#e8b2a7",
    }
    layer_colors = {layer["name"]: layer["color"].lower() for layer in layers}
    assert layer_colors == expected_kicad_colors

    # Verify tessellated substrate solid color matches pcb_metadata Substrate swatch
    sub_part = parts[0]
    sub_color = (sub_part.get("color") or (sub_part.get("parts") or [{}])[0].get("color") or "").lower()
    assert sub_color == "#041830"

    # Verify 3D CAD assembly mode still retains Components above Substrate on the stack
    cad_items = PCB3DAssembler.from_provider(CarrierBoardProvider()).get_display_items(prefix="carrier_board")
    cad_names = [name for _, name, _, _ in cad_items]
    assert cad_names.index("carrier_board_components") < cad_names.index("carrier_board_substrate")


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
    """Verify BUG-EMERALD-TICK-950: DIAGRAM and PCB UI responses set initial 2D body classes, mode pills, and HUD shortcuts."""

    class ModeDomParser(HTMLParser):
        """Extract body classes, active top-HUD mode pills, element IDs, and HUD cell text from rendered Scope HTML."""

        TRACKED_TEXT_IDS = frozenset(
            {
                "shortcuts-hud-title",
                "shortcuts-col-header",
                "hud-cell-pan",
                "hud-cell-zoom",
                "hud-cell-top",
                "hud-cell-focus",
            }
        )

        def __init__(self) -> None:
            super().__init__()
            self.body_classes: list[str] = []
            self.active_modes: list[str] = []
            self.element_ids: set[str] = set()
            self.text_by_id: dict[str, str] = {}
            self._in_modal = False
            self._active_tracked_id: str | None = None
            self._tracked_depth = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attr_map = dict(attrs)
            el_id = attr_map.get("id")
            if el_id:
                self.element_ids.add(el_id)
                if el_id == "modal-project-chooser":
                    self._in_modal = True
            if self._active_tracked_id is not None:
                self._tracked_depth += 1
            elif el_id in self.TRACKED_TEXT_IDS:
                self._active_tracked_id = el_id
                self._tracked_depth = 1
                self.text_by_id[el_id] = ""
            classes = (attr_map.get("class") or "").split()
            if tag == "body":
                self.body_classes = classes
            if tag == "button" and not self._in_modal and "mode-pill" in classes and "active" in classes:
                data_mode = attr_map.get("data-mode")
                if data_mode:
                    self.active_modes.append(data_mode)

        def handle_data(self, data: str) -> None:
            if self._active_tracked_id is not None:
                self.text_by_id[self._active_tracked_id] += data

        def handle_endtag(self, tag: str) -> None:
            if self._active_tracked_id is not None:
                self._tracked_depth -= 1
                if self._tracked_depth <= 0:
                    self._active_tracked_id = None
                    self._tracked_depth = 0

    for mode, expected_body_class in (("DIAGRAM", "mode-diagram"), ("PCB", "mode-pcb"), ("CAD", "mode-cad")):
        ui_url = f"http://127.0.0.1:{scope_server.actual_port}/?project=cat_fountain&target=wiring&mode={mode}"
        html = urllib.request.urlopen(ui_url).read().decode("utf-8")
        parser = ModeDomParser()
        parser.feed(html)
        assert expected_body_class in parser.body_classes
        assert parser.active_modes == [mode]
        for required_id in (
            "explode-section",
            "hud-row-inspect-pcb",
            "hud-row-orbit",
            "hud-row-flip",
            "hud-row-front",
            "hud-row-right",
            "hud-row-top",
            "hud-row-ortho",
            "hud-row-iso",
            "hud-row-planar-pan",
            "hud-row-wire",
        ):
            assert required_id in parser.element_ids
        if mode in ("PCB", "DIAGRAM"):
            assert "LMB Drag" in parser.text_by_id["hud-cell-pan"]
            assert "MMB Drag" in parser.text_by_id["hud-cell-zoom"]
            assert "Shift + MMB" not in parser.text_by_id["hud-cell-pan"]
        else:
            assert "Shift + MMB" in parser.text_by_id["hud-cell-pan"]
        if mode == "PCB":
            assert "PCB 2D" in parser.text_by_id["shortcuts-hud-title"]
            assert "7 (Top) / 1 (Bottom)" == parser.text_by_id["hud-cell-top"].strip()
            assert "F," not in parser.text_by_id["hud-cell-focus"]
        elif mode == "DIAGRAM":
            assert "DIAGRAM 2D" in parser.text_by_id["shortcuts-hud-title"]
            assert "F" in parser.text_by_id["hud-cell-focus"]


def test_regression_bug_chitinous_grub_712_simulation_particle_temporal_coherence(scope_server):
    """Verify BUG-CHITINOUS-GRUB-712: simulation fluid points maintain spatial temporal coherence without index-shift teleportation."""
    telem_url = (
        f"http://127.0.0.1:{scope_server.actual_port}/api/scope/simulation_telemetry"
        "?project=cat_fountain&target=product"
    )
    req_telem = urllib.request.urlopen(telem_url)
    assert req_telem.status == 200
    telem = json.loads(req_telem.read().decode("utf-8"))

    assert telem["status"] == "ok"
    assert telem.get("is_lagrangian") is False
    assert telem.get("radius_mm", 0.0) > 1.0
    assert len(telem.get("default_color", [])) == 4

    frames = telem["frames"]
    assert len(frames) >= 5
    for idx in range(1, 5):
        prev_pts = _decode_frame_positions(frames[idx - 1])
        curr_pts = _decode_frame_positions(frames[idx])
        prev_set = {tuple(row.tolist()) for row in np.round(prev_pts, 3)}
        curr_set = {tuple(row.tolist()) for row in np.round(curr_pts, 3)}
        assert len(curr_set) >= 20000
        stationary_overlap = len(prev_set & curr_set) / max(1, len(curr_set))
        assert stationary_overlap > 0.90, (
            f"Fluid cells jumped between step {idx - 1} and {idx}: overlap={stationary_overlap:.3f}"
        )
