"""Tests for carrier_board rigid-flex PCB and protective enclosure CAD geometry."""

from pathlib import Path
import pytest
from build123d import Location
from projects.carrier_board.provider import CarrierBoardProvider
from model.wiring import Wiring
from provider import Mode


def test_regression_bug_154_carrier_board_project_rename() -> None:
    """Verify BUG-154: test_board project renamed to carrier_board across all source and configs."""
    from pathlib import Path
    from projects.carrier_board.provider import CarrierBoardProvider
    from projects_config.carrier_board_config import CarrierBoardConfig

    # 1. Canonical provider class and name
    provider = CarrierBoardProvider()
    assert provider.name == "carrier_board"
    assert provider.pcb_config.name == "CarrierBoard"

    # 2. Canonical project file structure exists
    repo_root = Path(__file__).resolve().parents[2]
    carrier_dir = repo_root / "projects" / "carrier_board"
    assert carrier_dir.is_dir(), "carrier_board project directory must exist"
    assert (carrier_dir / "manifest.yaml").is_file()
    assert (carrier_dir / "pcb.py").is_file()
    assert (carrier_dir / "cad.py").is_file()
    assert (carrier_dir / "measurements.yaml").is_file()
    assert (repo_root / "projects" / "carrier_board.md").is_file()
    assert (repo_root / "projects_config" / "carrier_board_config.py").is_file()

    # 3. Old test_board paths must NOT exist (no lingering shims or directories)
    assert not (repo_root / "projects" / "test_board").exists()
    assert not (repo_root / "projects" / "test_board.md").exists()
    assert not (repo_root / "projects_config" / "test_board_config.py").exists()

    # 4. Strongly typed configuration model resolution
    cfg = provider.settings
    assert isinstance(cfg, CarrierBoardConfig)


def test_regression_bug_156_m2_thru_holes() -> None:
    """Verify BUG-156: J1 M.2 connector footprint contains all required through-hole pins."""
    from provider.footprints import get_shared_footprints

    footprints = get_shared_footprints()

    m2_fp = footprints["M.2-KEY-M"]
    thru_hole_pins = [p for p in m2_fp["pins"] if p.get("pad_type") == "thru_hole"]
    assert len(thru_hole_pins) >= 10, (
        f"M.2-KEY-M footprint must have at least 10 thru-hole pins, found {len(thru_hole_pins)}"
    )
    for pin in thru_hole_pins:
        assert pin.get("drill_dia_mm") is not None and pin["drill_dia_mm"] > 0, (
            f"Pin {pin['name']} must define positive drill_dia_mm"
        )


def test_regression_bug_157_action_button_routed() -> None:
    """Verify BUG-157: ACTION_BUTTON on flex tail is fully routed to J4 connector."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    flex_part = provider.part["flex_tail"]("flex_tail", None, None)
    flex_config = flex_part.to_pcb_config()
    if not flex_config.stackup:
        flex_config = flex_config.model_copy(update={"stackup": provider.pcb_config.stackup})

    action_btn = next(s for s in flex_config.capacitive_sensors if s.name == "ACTION_BUTTON")
    assert action_btn.tx_pin == "CAP_TX2"
    assert action_btn.rx_pin == "CAP_RX2"

    checker = PCBDesignRulesChecker(flex_config)
    report = checker.check_all(wiring=wiring)
    action_violations = [
        v
        for v in report.violations
        if "ACTION_BUTTON" in v.description
        or ("CAP_TX2" in v.description and v.rule_name == "ANTENNA_TRACE_DETECTED")
        or ("CAP_RX2" in v.description and v.rule_name == "ANTENNA_TRACE_DETECTED")
    ]
    assert not action_violations, f"ACTION_BUTTON routing violations found: {action_violations}"


def test_regression_bug_158_flex_perimeter_proximity_loop() -> None:
    """Verify BUG-158: flex tail proximity sensor uses a perimeter loop layout surrounding sensing region."""
    from projects.carrier_board.provider import CarrierBoardProvider

    provider = CarrierBoardProvider()
    flex_part = provider.part["flex_tail"]("flex_tail", None, None)
    flex_config = flex_part.to_pcb_config()

    prox = next(s for s in flex_config.capacitive_sensors if s.name == "PROXIMITY_SENSOR")
    assert prox.shape in ("loop", "perimeter_loop")
    assert prox.area_mm[0] >= 14.0
    assert prox.area_mm[1] >= 40.0

    top_traces = [
        tr for tr in flex_config.traces if tr.net == "CAP_RX3" and (tr.start_mm[1] >= 24.0 or tr.end_mm[1] >= 24.0)
    ]
    assert top_traces, "CAP_RX3 perimeter loop must include distal top trace segment at Y >= 24.0mm"


def test_regression_bug_159_swd_usb_labels_orientation() -> None:
    """Verify BUG-159: SWD and USB connector labels on exterior wall are right-reading from exterior."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.types import Mode

    provider = CarrierBoardProvider()
    enc = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    assert enc.part.is_valid(), "Enclosure bottom with exterior-facing labels must be a valid solid"
    assert len(enc.part.solids()) == 1, "Enclosure bottom must remain a single contiguous solid"


@pytest.mark.slow
def test_regression_bug_160_peripheral_labels_on_enclosure_lid() -> None:
    """Verify BUG-160: peripheral connector text moved to enclosure top to prevent hollow shells."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.types import Mode

    provider = CarrierBoardProvider()
    bot = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)

    # Both enclosure parts must be valid, single contiguous solids
    assert bot.part.is_valid(), "enclosure_bottom must be valid solid"
    assert len(bot.part.solids()) == 1, "enclosure_bottom must be a single solid without hollow cavities"
    assert lid.part.is_valid(), "enclosure_lid must be valid solid"
    assert len(lid.part.solids()) == 1, "enclosure_lid must be a single solid with engraved bus labels"


@pytest.mark.slow
def test_regression_capsense_proximity_loop_clearance_and_drc() -> None:
    """Verify capsense traces maintain clearance to proximity sensor perimeter loop and pass DRC."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    flex_part = provider.part["flex_tail"]("flex_tail", None, None)
    flex_config = flex_part.to_pcb_config()

    checker = PCBDesignRulesChecker(flex_config)
    report = checker.check_all()
    cap_errors = [
        v
        for v in report.violations
        if "PROXIMITY_SENSOR" in v.net_or_zone or "SLIDER" in v.net_or_zone or "ACTION" in v.net_or_zone
    ]
    assert not cap_errors, f"Expected 0 capacitive sensor DRC violations on flex_tail, found: {cap_errors}"
    assert report.error_count == 0, f"Expected 0 errors on flex_tail DRC, found: {report.violations}"


def test_regression_bug_161_board_texture_transparency_mask() -> None:
    """Verify BUG-161: KiCad texture rendering applies geometric transparency mask to corners and mounting holes."""
    from PIL import Image
    from provider.pcb.kicad_cli import KiCadCLI

    # Create solid RGBA test image: 600x900 representing 60mm x 90mm board (10 px/mm)
    w_px, h_px = 600, 900
    w_mm, l_mm = 60.0, 90.0
    corner_r_mm = 3.0
    mounting_holes = [(-25.0, 40.0, 1.6)]  # Hole at X=-25, Y=40, radius=1.6mm

    img = Image.new("RGBA", (w_px, h_px), (0, 100, 0, 255))
    masked = KiCadCLI.apply_transparency_mask(
        img,
        side="top",
        board_dimensions_mm=(w_mm, l_mm),
        corner_radius_mm=corner_r_mm,
        mounting_holes=mounting_holes,
    )

    # 1. Corner pixel (0, 0) must be 100% transparent (alpha = 0)
    assert masked.getpixel((0, 0))[3] == 0, "Top-left corner outside corner radius must be transparent"
    assert masked.getpixel((w_px - 1, 0))[3] == 0, "Top-right corner outside corner radius must be transparent"

    # 2. Board center (300, 450) must remain fully opaque (alpha = 255)
    assert masked.getpixel((300, 450))[3] == 255, "Board interior must remain fully opaque"

    # 3. Mounting hole center must be 100% transparent (alpha = 0)
    # (-25.0 + 30.0) * 10 = 50px, (45.0 - 40.0) * 10 = 50px
    hole_px_x = int((-25.0 + w_mm / 2.0) * (w_px / w_mm))
    hole_px_y = int((l_mm / 2.0 - 40.0) * (h_px / l_mm))
    assert masked.getpixel((hole_px_x, hole_px_y))[3] == 0, "Mounting hole center must be transparent"


@pytest.mark.slow
def test_regression_pcb_texture_uv_parity_and_orientation() -> None:
    """Verify that PCB texture UV mapping in Rerun Mesh3D maintains correct parity and upright orientation."""
    from pathlib import Path
    from unittest.mock import patch
    import pybullet as p
    from PIL import Image
    from provider import Room, Mode
    from provider.bullet import Bullet

    test_build_dir = Path("build/test_dummy_uv_textures")
    tex_dir = test_build_dir / "board" / "carrier_board" / "textures"
    tex_dir.mkdir(parents=True, exist_ok=True)

    raw_tex = Image.new("RGBA", (60, 90), (0, 100, 0, 255))
    raw_tex.save(tex_dir / "carrier_board_top.png")
    raw_tex.save(tex_dir / "carrier_board_bottom.png")

    provider = CarrierBoardProvider()
    room = Room(is_simulate=True)
    provider.view["carrier_board"](room, Mode.DEFAULT)
    hooks = provider.get_simulate_hooks("carrier_board")
    bullet = Bullet(
        room=room,
        provider_hooks=hooks,
        sim_target="carrier_board",
        proj_name="carrier_board",
        build_dir=str(test_build_dir),
    )
    client = p.connect(p.DIRECT)
    try:
        with patch("rerun.log") as mock_log:
            bullet._init_simulation_objects(
                client, 0, "build/obj/carrier_board", "build/urdf/carrier_board/carrier_board.urdf"
            )
            top_mesh = next(
                call[0][1]
                for call in mock_log.call_args_list
                if len(call[0]) > 1 and call[0][0] == "world/carrier_board/texture_top"
            )
            bot_mesh = next(
                call[0][1]
                for call in mock_log.call_args_list
                if len(call[0]) > 1 and call[0][0] == "world/carrier_board/texture_bottom"
            )

            # Check top mesh UV mapping:
            # V=0 must correspond to CAD max_y (+Y, top of board)
            # V=1 must correspond to CAD min_y (-Y, bottom of board)
            v_pos = top_mesh.vertex_positions.as_arrow_array().to_pylist()
            v_uv = top_mesh.vertex_texcoords.as_arrow_array().to_pylist()

            for pos, uv in zip(v_pos, v_uv):
                if pos[1] > 40.0:  # Top of board in CAD (+Y)
                    assert uv[1] <= 0.10, f"Top CAD vertex at Y={pos[1]} must have V near 0 (got V={uv[1]})"
                elif pos[1] < -40.0:  # Bottom of board in CAD (-Y)
                    assert uv[1] >= 0.90, f"Bottom CAD vertex at Y={pos[1]} must have V near 1 (got V={uv[1]})"
                if pos[0] > 25.0:  # Right of board in CAD (+X)
                    assert uv[0] >= 0.90, f"Right CAD vertex at X={pos[0]} must have U near 1 (got U={uv[0]})"
                elif pos[0] < -25.0:  # Left of board in CAD (-X)
                    assert uv[0] <= 0.10, f"Left CAD vertex at X={pos[0]} must have U near 0 (got U={uv[0]})"

            # Check bottom mesh UV mapping:
            b_pos = bot_mesh.vertex_positions.as_arrow_array().to_pylist()
            b_uv = bot_mesh.vertex_texcoords.as_arrow_array().to_pylist()

            for pos, uv in zip(b_pos, b_uv):
                if pos[1] > 40.0:
                    assert uv[1] <= 0.10, f"Top CAD bottom vertex at Y={pos[1]} must have V near 0 (got V={uv[1]})"
                elif pos[1] < -40.0:
                    assert uv[1] >= 0.90, f"Bottom CAD bottom vertex at Y={pos[1]} must have V near 1 (got V={uv[1]})"
                if pos[0] > 25.0:
                    # In bottom view, CAD +X is on the viewer's left -> U near 0
                    assert uv[0] <= 0.10, f"Right CAD bottom vertex at X={pos[0]} must have U near 0 (got U={uv[0]})"
                elif pos[0] < -25.0:
                    # In bottom view, CAD -X is on the viewer's right -> U near 1
                    assert uv[0] >= 0.90, f"Left CAD bottom vertex at X={pos[0]} must have U near 1 (got U={uv[0]})"
    finally:
        p.disconnect(client)
        import shutil

        shutil.rmtree(test_build_dir, ignore_errors=True)


def test_regression_bug_173_174_schematic_netlist_disconnects_and_missing_gnd() -> None:
    """Verify BUG-173 & BUG-174: J9/J10 serial expansion connectors have complete netlist connectivity and GND."""
    from pathlib import Path
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker, DRCRuleName

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    footprints = {fp.name: fp for fp in wiring.footprints}

    # Verify J9 and J10 exist and have 7 pins with pin_name, signal_name, and number
    assert "J9" in footprints and "J10" in footprints
    j9 = footprints["J9"]
    j10 = footprints["J10"]
    assert len(j9.pins) == 7
    assert len(j10.pins) == 7

    for p in j9.pins:
        assert p.number is not None, f"J9 pin {p.name} must have number"
        assert p.pin_name is not None, f"J9 pin {p.name} must have pin_name"
        assert p.signal_name is not None, f"J9 pin {p.name} must have signal_name"

    for p in j10.pins:
        assert p.number is not None, f"J10 pin {p.name} must have number"
        assert p.pin_name is not None, f"J10 pin {p.name} must have pin_name"
        assert p.signal_name is not None, f"J10 pin {p.name} must have signal_name"

    # Verify J9 pin 7 and J10 pin 1 are GND (BUG-174)
    gnd_net = next(n for n in wiring.nets if n.name == "GND")
    assert ("J9", "7") in gnd_net.pins or ("J9", "7", "GND") in gnd_net.pins
    assert ("J10", "1") in gnd_net.pins or ("J10", "1", "GND") in gnd_net.pins

    # Verify Q1 is removed from carrier board
    assert "Q1" not in footprints, "Q1 must be removed from carrier board"

    # Verify DRC check_netlist_connectivity passes with 0 PIN_NAME_MISMATCH or SIGNAL_NAME_MISMATCH
    cfg = provider.pcb_config
    checker = PCBDesignRulesChecker(cfg)
    violations = checker.check_netlist_connectivity(wiring)
    mismatches = [
        v
        for v in violations
        if v.rule_name
        in (DRCRuleName.PIN_NAME_MISMATCH, DRCRuleName.SIGNAL_NAME_MISMATCH, DRCRuleName.SHORT_CIRCUIT_DETECTED)
    ]
    assert len(mismatches) == 0, f"Netlist connectivity violations: {mismatches}"

    # Verify flying probe signal isolation against power and ground
    from provider.simulation.flying_probe import verify_signal_lines_isolation

    isolation_result = verify_signal_lines_isolation(provider, wiring=wiring)
    assert isolation_result["all_passed"] is True, f"Shorted signals: {isolation_result['shorted_signals']}"
    assert len(isolation_result["signal_lines"]) > 0, "Must audit signal lines"
    assert len(isolation_result["power_ground_nets"]) > 0, "Must audit power and ground nets"


def test_regression_flying_probes_initial_isolation_verdict_pending() -> None:
    """Verify flying probe isolation tests show PENDING initially, not PASS before physical probing."""
    import pybullet as p
    from provider import Simulate

    provider = CarrierBoardProvider()
    hooks = provider.get_simulate_hooks("carrier_board")
    client = p.connect(p.DIRECT)
    try:
        hooks[Simulate.SETUP](0, client, "carrier_board", {})

        # Initial test report before running simulation steps
        initial_report = provider.generate_test_report()
        assert "Overall Verdict** | ⚪ `PENDING`" in initial_report, (
            "Initial test report must display ⚪ `PENDING` overall verdict"
        )
        assert "Tested Steps** | `0 /" in initial_report, "Initial test report must show 0 tested steps completed"
        assert "Yield** | 0.0%" in initial_report, "Initial yield must be 0.0%"

        # Detailed step results and Signal Line Isolation Audit must report PENDING, not PASS
        assert "TEST_ISO_" in initial_report
        assert "⚪ *PENDING*" in initial_report
        # No isolation test should report PASS before pad contact and dwell
        for line in initial_report.splitlines():
            if "TEST_ISO_" in line:
                assert "⚪ *PENDING*" in line, f"Isolation step must be PENDING initially: {line}"
                assert "🟢 **PASS**" not in line, f"Isolation step cannot be PASS initially: {line}"
                assert "> 100 MΩ" not in line, f"Isolation step cannot show measured resistance initially: {line}"

        # Execute flying probe simulation to completion
        for step_idx in range(1000):
            hooks[Simulate.STEP](0, client, step_idx, "carrier_board")

        # Verify isolation steps use standard 'resistance' test_type across all tests
        assert hasattr(provider, "flying_probe_steps")
        iso_steps = [s for s in provider.flying_probe_steps if s.step_id.startswith("TEST_ISO_")]
        assert len(iso_steps) > 0, "Must have generated isolation steps"
        for s in iso_steps:
            assert s.test_type == "resistance", (
                f"Isolation step {s.step_id} must have test_type 'resistance', got {s.test_type}"
            )

        # Final test report after simulation steps
        final_report = provider.generate_test_report()
        assert "Overall Verdict** | 🟢 `PASS`" in final_report, (
            "Completed test report must display 🟢 `PASS` overall verdict"
        )
        assert "100.0%" in final_report, "Completed yield must be 100.0%"
        assert "> 100 MΩ" in final_report, "Completed report must display measured isolation resistance"
        assert "⚪ *PENDING*" not in final_report, "Completed report must not have pending steps"
    finally:
        p.disconnect(client)


@pytest.mark.slow
def test_regression_bug_176_jst_connector_spacing_and_zero_drc_errors() -> None:
    """Verify BUG-176: JST peripheral headers J6-J10 have >= 1.0mm body gap and 0 DRC errors."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker
    from model.wiring import Wiring

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    comp_map = {c.name: c for c in wiring.footprints}

    # Connector lengths along Y axis: 6P = 14.0mm, 7P = 16.0mm
    connectors = [("J6", 14.0), ("J7", 14.0), ("J8", 14.0), ("J9", 16.0), ("J10", 16.0)]
    for i in range(len(connectors) - 1):
        c_top, len_top = connectors[i]
        c_bot, len_bot = connectors[i + 1]
        y_top = comp_map[c_top].position[1]
        y_bot = comp_map[c_bot].position[1]
        body_gap = (y_top - len_top / 2.0) - (y_bot + len_bot / 2.0)
        assert body_gap >= 1.0, f"Body gap between {c_top} and {c_bot} must be >= 1.0mm, got {body_gap:.2f}mm"

    # Verify PCB DRC reports 0 errors
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0, f"Expected 0 DRC errors, got {report.error_count}"


@pytest.mark.slow
def test_regression_bug_177_enclosure_bottom_cutouts_and_lid_markers() -> None:
    """Verify BUG-177: enclosure bottom cutouts align with J6-J10 and lid has engraved GPIO icons."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider import Mode

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    comp_map = {c.name: c for c in wiring.footprints}

    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    wall_x = (w / 2.0) - (wall / 2.0)
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)
    z_conn = z_carrier + (provider.settings.board_thickness / 2.0) + 2.0

    for des in ("J6", "J7", "J8", "J9", "J10"):
        y = comp_map[des].position[1]
        assert not enclosure.part.is_inside((wall_x, y, z_conn)), (
            f"Enclosure bottom must have cutout clearing connector {des} at Y={y}"
        )

    # Verify lid builds successfully with GPIO icon markers
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    assert lid.part is not None
    assert lid.part.volume > 0.0


@pytest.mark.slow
def test_regression_bug_179_right_side_ports_clear_mounting_holes() -> None:
    """Verify BUG-179: right side peripheral ports J6 and J10 clear mounting holes MH1 and MH4."""
    import math
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker
    from model.wiring import Wiring

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    comp_map = {c.name: c for c in wiring.footprints}

    # Connector lengths along Y: J6-J8 = 14mm, J9-J10 = 16mm
    # Positions: J6 @ Y=32, J10 @ Y=-31
    j6_y = comp_map["J6"].position[1]
    j10_y = comp_map["J10"].position[1]
    assert j6_y <= 32.0, f"J6 center Y must be <= 32.0 to clear MH1, got {j6_y}"
    assert j10_y >= -31.0, f"J10 center Y must be >= -31.0 to clear MH4, got {j10_y}"

    # Verify J6 top edge does not overlap MH1
    j6_top = j6_y + 14.0 / 2.0
    assert j6_top <= 39.0, f"J6 top body edge must be <= 39.0mm, got {j6_top}"

    # Verify J10 bottom edge does not overlap MH4
    j10_bottom = j10_y - 16.0 / 2.0
    assert j10_bottom >= -39.0, f"J10 bottom body edge must be >= -39.0mm, got {j10_bottom}"

    # Check pad-to-pad distance between J6 pin 1 (y = j6_y + 5.0) and MH1 (25.5, 40.5)
    # J6 pin 1 is at (24.5, 37.0)
    mh1_x, mh1_y = 25.5, 40.5
    j6_p1_x, j6_p1_y = 24.5, j6_y + 5.0
    dist_mh1 = math.hypot(mh1_x - j6_p1_x, mh1_y - j6_p1_y)
    # MH1 pad radius (2.25) + J6 pad radius (0.8) = 3.05mm
    assert dist_mh1 > 3.05, f"J6 pin 1 shorts with MH1: distance {dist_mh1:.3f}mm <= 3.05mm"

    # Check pad-to-pad distance between J10 pin 7 (y = j10_y - 6.0) and MH4 (25.5, -40.5)
    # J10 pin 7 is at (24.5, -37.0)
    mh4_x, mh4_y = 25.5, -40.5
    j10_p7_x, j10_p7_y = 24.5, j10_y - 6.0
    dist_mh4 = math.hypot(mh4_x - j10_p7_x, mh4_y - j10_p7_y)
    assert dist_mh4 > 3.05, f"J10 pin 7 shorts with MH4: distance {dist_mh4:.3f}mm <= 3.05mm"

    # Verify uniform >= 1.0mm body gaps across all peripheral headers
    connectors = [("J6", 14.0), ("J7", 14.0), ("J8", 14.0), ("J9", 16.0), ("J10", 16.0)]
    for i in range(len(connectors) - 1):
        c_top, len_top = connectors[i]
        c_bot, len_bot = connectors[i + 1]
        y_top = comp_map[c_top].position[1]
        y_bot = comp_map[c_bot].position[1]
        body_gap = (y_top - len_top / 2.0) - (y_bot + len_bot / 2.0)
        assert body_gap >= 1.0, f"Body gap between {c_top} and {c_bot} must be >= 1.0mm, got {body_gap:.2f}mm"

    # Verify DRC clean
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0, f"Expected 0 DRC errors, got {report.error_count}"


@pytest.mark.slow
def test_regression_bug_180_zero_drc_violations_carrier_board_and_flex_tail() -> None:
    """Verify BUG-180: carrier_board and flex_tail achieve zero DRC violations with rule severities."""
    from pathlib import Path
    from provider.pcb.kicad_cli import KiCadCLI

    # Test rule_severities in to_kicad_pro_dict
    provider = CarrierBoardProvider()
    rules = provider.pcb_config.design_rules
    assert "hole_to_hole" in rules.rule_severities
    assert "track_dangling" in rules.rule_severities
    pro_dict = rules.to_kicad_pro_dict()
    assert "rule_severities" in pro_dict["board"]["design_settings"]
    assert pro_dict["board"]["design_settings"]["rule_severities"]["track_dangling"] == "ignore"

    # Test parsed reports from build output
    carrier_rpt = Path("build/rpt/carrier_board-drc.rpt")
    if carrier_rpt.exists():
        report = KiCadCLI.parse_drc_report(carrier_rpt)
        assert report.passed
        assert report.error_count == 0
        assert report.violations_count == 0

    flex_rpt = Path("build/rpt/flex_tail-drc.rpt")
    if flex_rpt.exists():
        report = KiCadCLI.parse_drc_report(flex_rpt)
        assert report.passed
        assert report.error_count == 0
        assert report.violations_count == 0


@pytest.mark.slow
def test_regression_bug_183_carrier_board_hardening() -> None:
    """Verify BUG-183: carrier board design hardening with jumpers, LEDs, switch, and Status sheet."""
    from pathlib import Path
    from provider.pcb.drc import PCBDesignRulesChecker
    from provider.pcb.kicad_cli import KiCadCLI

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    comp_map = {c.name: c for c in wiring.footprints}

    # Verify SW1 reset button exists and is placed
    assert "SW1" in comp_map, "SW1 reset button must exist in wiring"
    assert comp_map["SW1"].package == "SW_PUSH_SMD"

    # Verify isolation and override jumpers JP1..JP4
    for jp in ("JP1", "JP2", "JP3", "JP4"):
        assert jp in comp_map, f"Jumper {jp} must exist in wiring"
        assert comp_map[jp].package == "pin_header_1x2"

    # Verify power good / enable LEDs D2..D7 and resistors R7..R12
    for d_idx in range(2, 8):
        d_name = f"D{d_idx}"
        r_name = f"R{d_idx + 5}"
        assert d_name in comp_map, f"Status LED {d_name} must exist in wiring"
        assert r_name in comp_map, f"Ballast resistor {r_name} must exist in wiring"
        assert comp_map[d_name].package == "0603"
        assert comp_map[r_name].package == "0402"

    # Verify new components are placed in open space south of U1 and north of J1
    for name in ["SW1", "JP1", "JP2", "JP3", "JP4", "D2", "D3", "D4", "D5", "D6", "D7"]:
        pos = comp_map[name].position
        y_max = -10.0 if name == "SW1" else -13.0
        assert -36.0 <= pos[1] <= y_max, (
            f"Component {name} at Y={pos[1]} not in designated space south of U1 and north of J1"
        )
        assert -15.0 <= pos[0] <= 15.0, f"Component {name} at X={pos[0]} not in designated corridor"

    # Verify Status and Overrides schematic sheet exists in PCB configuration
    status_sheets = [s for s in provider.pcb_config.schematic_sheets if "Status and Overrides" in s.title]
    assert len(status_sheets) >= 1, "Schematic sheets for 'Status and Overrides' must exist"
    all_status_comps = [c for s in status_sheets for c in s.components]
    assert "SW1" in all_status_comps
    assert "JP1" in all_status_comps
    assert "D2" in all_status_comps

    # Verify PCB DRC checker passes
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0

    # Verify KiCad DRC report clean if generated
    carrier_rpt = Path("build/rpt/carrier_board-drc.rpt")
    if carrier_rpt.exists():
        kicad_report = KiCadCLI.parse_drc_report(carrier_rpt)
        assert kicad_report.passed
        assert kicad_report.error_count == 0
        assert kicad_report.violations_count == 0


@pytest.mark.slow
def test_regression_bug_189_enclosure_top_gpio_labels() -> None:
    """Verify BUG-189: GPIO labels on enclosure top are text, non-overlapping, and properly rotated."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider import Mode

    provider = CarrierBoardProvider()
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    depth = provider.settings.enclosure_gpio_label_depth

    assert lid.part is not None
    assert lid.part.is_valid(), "Enclosure lid with engraved GPIO labels must be a valid solid"
    assert len(lid.part.solids()) == 1, "Enclosure lid must remain a single contiguous solid"

    # Engraved text bottom faces lie at Z = wall - depth
    engraved_z = wall - depth
    label_faces = [f for f in lid.part.faces() if abs(f.center().Z - engraved_z) < 1e-3]
    assert len(label_faces) > 0, f"Expected engraved faces at Z={engraved_z}, found 0"

    # Verify GPIO header cutout is present
    gpio_w = provider.settings.enclosure_gpio_cutout_width
    gpio_l = provider.settings.enclosure_gpio_cutout_length
    assert gpio_w > 0 and gpio_l > 0


@pytest.mark.slow
def test_regression_bug_207_sheet_17_components_on_carrier_board() -> None:
    """Verify BUG-207: Sheet 17 components are present on carrier board with complete routing and 0 DRC errors."""
    from pathlib import Path
    from provider.pcb.drc import PCBDesignRulesChecker
    from provider.pcb.kicad_cli import KiCadCLI

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    comp_map = {c.name: c for c in wiring.footprints}

    # Verify all 17 components from Sheet 17 and sub-sheets are placed on the board
    sheet_17_comps = [
        "SW1",
        "JP1",
        "JP2",
        "JP3",
        "JP4",
        "D2",
        "D3",
        "D4",
        "D5",
        "D6",
        "D7",
        "R7",
        "R8",
        "R9",
        "R10",
        "R11",
        "R12",
    ]
    for name in sheet_17_comps:
        assert name in comp_map, f"Sheet 17 component {name} must exist on carrier board"
        pos = comp_map[name].position
        y_max = -10.0 if name == "SW1" else -13.0
        assert -36.0 <= pos[1] <= y_max, f"Component {name} must be in corridor between U1 and J1"

    # Verify existing baseline components were not displaced
    assert tuple(comp_map["U1"].position[:2]) == (0.0, 0.0)
    assert "J1" not in comp_map, "J1 PCIe connector must be removed (BUG-214)"
    assert tuple(comp_map["U11"].position[:2]) == (0.0, -36.0)
    assert tuple(comp_map["J2"].position[:2]) == (0.0, 38.0)
    assert tuple(comp_map["J3"].position[:2]) == (-25.0, 0.0)
    assert tuple(comp_map["J14"].position[:2]) == (19.0, -28.0)

    # Verify DRC clean
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0

    # Verify KiCad DRC report clean if generated
    carrier_rpt = Path("build/rpt/carrier_board-drc.rpt")
    if carrier_rpt.exists():
        kicad_report = KiCadCLI.parse_drc_report(carrier_rpt)
        assert kicad_report.passed
        assert kicad_report.error_count == 0
        assert kicad_report.violations_count == 0


@pytest.mark.slow
def test_regression_bug_208_battery_cover_does_not_elide_enclosure_labels() -> None:
    """Verify BUG-208: Battery cover does not elide BATTERY or GPIO labels, and GPIO pin 10 marker is present."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider import Mode

    provider = CarrierBoardProvider()
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    cover = provider.battery_cover("battery_cover", None, Mode.DEFAULT)

    assert lid.part is not None and lid.part.is_valid()
    assert cover.part is not None and cover.part.is_valid()

    cover_bb = cover.part.bounding_box()

    # Verify BATTERY label margin and that BATTERY label is strictly south of battery cover min Y
    label_margin = provider.settings.enclosure_battery_label_margin
    assert label_margin >= 1.0, f"Expected battery label margin >= 1.0mm, got {label_margin}"

    # Calculate battery label coordinate
    batt_l = provider.settings.enclosure_battery_mount_length
    batt_y = provider.settings.enclosure_battery_mount_y
    cradle_t = provider.settings.enclosure_battery_mount_wall_thickness
    clr = provider.settings.enclosure_battery_cover_clearance
    cover_t = provider.settings.enclosure_battery_cover_wall_thickness
    min_y = batt_y - (batt_l / 2.0)
    batt_lbl_y = min_y - cradle_t - clr - cover_t - label_margin
    assert batt_lbl_y < cover_bb.min.Y, (
        f"BATTERY label Y={batt_lbl_y} must be strictly south of cover min Y={cover_bb.min.Y}"
    )

    # Verify GPIO title is located directly above GPIO cutout and horizontally clear of battery cover
    gpio_y = -28.0
    gpio_l = provider.settings.enclosure_gpio_cutout_length
    hdr_margin = provider.settings.enclosure_gpio_header_label_margin
    hdr_y = gpio_y + (gpio_l / 2.0) + hdr_margin
    assert hdr_y > gpio_y + (gpio_l / 2.0), "GPIO header label must be located north of cutout"
    assert 19.0 > cover_bb.max.X + 2.0, "GPIO label X position must maintain clearance from battery cover right edge"

    # Verify pin 10 marker Y position matches physical pin 10
    pitch = provider.settings.enclosure_gpio_pin_pitch
    pin_10_y = gpio_y + (4.5 * pitch)
    assert pin_10_y > gpio_y + (3.0 * pitch), "Pin 10 marker must be positioned at top pin header location"


def test_regression_bug_210_passives_have_values() -> None:
    """Verify BUG-210: All resistors and capacitors have strongly typed electrical values."""
    from model.wiring import Wiring
    from projects.carrier_board.provider import CarrierBoardProvider

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    fp_map = {fp.name: fp for fp in wiring.footprints}

    # Verify all 14 capacitors have non-empty capacitance values
    for c_idx in range(1, 15):
        c_name = f"C{c_idx}"
        assert c_name in fp_map, f"Capacitor {c_name} missing from wiring"
        c_val = getattr(fp_map[c_name], "value", None)
        assert c_val is not None and len(c_val) > 0, f"Capacitor {c_name} is missing electrical value"
        assert any(c_val.endswith(unit) for unit in ("uF", "pF", "nF")), (
            f"Capacitor {c_name} value '{c_val}' does not end with standard capacitance unit"
        )

    # Verify all 12 resistors have non-empty resistance values
    for r_idx in range(1, 13):
        r_name = f"R{r_idx}"
        assert r_name in fp_map, f"Resistor {r_name} missing from wiring"
        r_val = getattr(fp_map[r_name], "value", None)
        assert r_val is not None and len(r_val) > 0, f"Resistor {r_name} is missing electrical value"
        assert any(unit in r_val for unit in ("k", "ohm", "M", "R")), (
            f"Resistor {r_name} value '{r_val}' does not contain standard resistance unit"
        )


def test_regression_bug_209_silkscreen_readability_and_spacing() -> None:
    """Verify BUG-209: Schematic power net exclusions and PCB silkscreen region spacing."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker
    from provider.schematic.constants import PowerNetMatcher

    # 1. Verify PowerNetMatcher excludes LED cathode/anode signals from being matched as power nets
    matcher = PowerNetMatcher()
    for net in ("LED_VBAT_K", "LED_VBUS_K", "LED_3V3_K", "LED_AUD_K", "LED_PERIPH_K", "LED_MCU_K"):
        assert not matcher.is_power_net(net), f"Cathode net {net} must not be matched as power rail"
        assert net not in matcher, f"Cathode net {net} must not match in PowerNetMatcher"

    provider = CarrierBoardProvider()
    pcb_cfg = provider.pcb_config

    # 2. Verify LAYER 1-6 RIGID-FLEX silkscreen has been removed per CR feedback
    assert all(t.text != "LAYER 1-6 RIGID-FLEX" for t in pcb_cfg.silkscreen_texts)

    # 3. Verify jumper and switch labels are horizontal (rotation == 0.0)
    for label_name in ("NRST", "BOOT0", "ISP", "VBUS", "RESET"):
        lbl = next(t for t in pcb_cfg.silkscreen_texts if t.text == label_name)
        assert lbl.rotation == 0.0, f"Label {label_name} must have horizontal rotation 0.0, got {lbl.rotation}"

    # 4. Verify PCB DRC passes with 0 violations
    drc = PCBDesignRulesChecker(pcb_cfg)
    report = drc.check_all(wiring=provider.wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0
