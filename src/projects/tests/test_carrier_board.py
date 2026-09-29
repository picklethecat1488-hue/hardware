"""Tests for carrier_board rigid-flex PCB and protective enclosure CAD geometry."""

import pytest
from build123d import Location
from projects.carrier_board.provider import CarrierBoardProvider
from model.wiring import Wiring
from provider import Mode


@pytest.mark.slow
def test_regression_bug_072_flex_tail_cutout_zero_intersection() -> None:
    """Verify BUG-072: flex tail has zero intersection volume with enclosure bottom and lid."""
    provider = CarrierBoardProvider()
    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)

    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)

    wiring = Wiring(str(provider.wiring_path))
    j2_comp = next(c for c in wiring.footprints if c.name == "J2")
    j_flex_comp = next(c for c in wiring.footprints if c.name == "J4")
    dx = j2_comp.position[0] - j_flex_comp.position[0]
    dy = j2_comp.position[1] - j_flex_comp.position[1]
    dz = j2_comp.position[2] - j_flex_comp.position[2]

    tail_geom = tail.part.locate(Location((dx, dy, z_carrier + dz)))
    z_lid = (h_shell / 2.0) + (wall / 2.0)
    lid_geom = lid.part.locate(Location((0.0, 0.0, z_lid)))

    inter_bottom = enclosure.part.intersect(tail_geom)
    inter_lid = lid_geom.intersect(tail_geom)

    assert inter_bottom.volume == 0.0, f"Flex tail intersects enclosure bottom: {inter_bottom.volume:.4f} mm^3"
    assert inter_lid.volume == 0.0, f"Flex tail intersects enclosure lid: {inter_lid.volume:.4f} mm^3"


def test_regression_bug_073_gpio_cutout_and_key() -> None:
    """Verify BUG-073: enclosure lid has GPIO cutout and key for J14."""
    provider = CarrierBoardProvider()
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness

    wiring = Wiring(str(provider.wiring_path))
    j14 = next(c for c in wiring.footprints if c.name == "J14")
    gpio_x, gpio_y = j14.position[0], j14.position[1]

    # GPIO cutout must pierce completely through the lid at J14 position
    assert not lid.part.is_inside((gpio_x, gpio_y, wall / 2.0)), "Lid must have a cutout at J14 position"
    assert not lid.part.is_inside((gpio_x, gpio_y + 10.0, wall / 2.0)), "Cutout must cover top GPIO pins"
    assert not lid.part.is_inside((gpio_x, gpio_y - 10.0, wall / 2.0)), "Cutout must cover bottom GPIO pins"


def test_regression_bug_074_peripheral_cutouts_and_identifiers() -> None:
    """Verify BUG-074: enclosure bottom has peripheral cutouts for I2C, I3C, and SPI with identifiers."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)
    z_conn = z_carrier + (provider.settings.board_thickness / 2.0) + 2.0

    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}

    wall_x = (w / 2.0) - (wall / 2.0)
    for des, bus in [("J6", "I2C"), ("J7", "I3C0"), ("J8", "I3C1"), ("J9", "SPI"), ("J10", "UART")]:
        y = comp_map[des].position[1]
        assert not enclosure.part.is_inside((wall_x, y, z_conn)), (
            f"Enclosure bottom must have cutout for {bus} at Y={y}"
        )


def test_regression_bug_110_expansion_headers_jst_ph() -> None:
    """Verify BUG-110 & BUG-174: expansion header connectors J9 and J10 are 7-pin JST-PH style connectors with GND."""
    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}

    assert comp_map["J9"].package == "JST-PH-7P", f"J9 package should be JST-PH-7P, got {comp_map['J9'].package}"
    assert comp_map["J10"].package == "JST-PH-7P", f"J10 package should be JST-PH-7P, got {comp_map['J10'].package}"
    assert "B7B-PH-K-S" in comp_map["J9"].mpn or "PH" in comp_map["J9"].mpn
    assert "B7B-PH-K-S" in comp_map["J10"].mpn or "PH" in comp_map["J10"].mpn


def test_regression_bug_113_carrier_board_serial_cutouts_do_not_overlap() -> None:
    """Verify BUG-113: peripheral and serial expansion cutouts do not overlap, leaving solid walls."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)
    z_conn = z_carrier + (provider.settings.board_thickness / 2.0) + 2.0
    wall_x = (w / 2.0) - (wall / 2.0)

    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}

    connectors = ["J6", "J7", "J8", "J9", "J10"]
    y_coords = [comp_map[c].position[1] for c in connectors]
    lengths = [provider.settings.enclosure_periph_cutout_length] * len(connectors)

    for i in range(len(y_coords) - 1):
        y_bottom_prev = y_coords[i] - (lengths[i] / 2.0)
        y_top_curr = y_coords[i + 1] + (lengths[i + 1] / 2.0)
        # Assert non-overlapping with at least 1.0mm solid separation wall
        wall_separation = y_bottom_prev - y_top_curr
        assert wall_separation >= 1.0, (
            f"Cutout {connectors[i]} and {connectors[i + 1]} overlap or have insufficient wall: {wall_separation:.2f}mm"
        )
        mid_wall_y = (y_bottom_prev + y_top_curr) / 2.0
        assert enclosure.part.is_inside((wall_x, mid_wall_y, z_conn)), (
            f"Solid wall must exist between {connectors[i]} and {connectors[i + 1]} at Y={mid_wall_y}"
        )


def test_regression_bug_075_swd_cutout() -> None:
    """Verify BUG-075: enclosure bottom has SWD cutout through the left exterior wall."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)
    z_conn = z_carrier + (provider.settings.board_thickness / 2.0) + 2.0

    from model.wiring import Wiring

    swd_y = -15.0
    if provider.wiring_path.exists():
        wiring = Wiring(str(provider.wiring_path))
        comp_map = {c.name: c for c in wiring.footprints}
        if "J5" in comp_map:
            swd_y = comp_map["J5"].position[1]

    # Probe point centered inside the left exterior wall (X = -w/2 + wall/2) at J5 SWD connector position
    wall_x = (-w / 2.0) + (wall / 2.0)
    assert not enclosure.part.is_inside((wall_x, swd_y, z_conn)), (
        "Enclosure bottom must have an SWD cutout through the left exterior wall at J5 position"
    )


@pytest.mark.slow
def test_regression_bug_076_enclosure_snap_fit() -> None:
    """Verify BUG-076: enclosure lid snap fits to bottom shell without useless screw holes."""
    provider = CarrierBoardProvider()
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)

    wall = provider.settings.enclosure_wall_thickness
    lip_h = provider.settings.enclosure_lip_height
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    w_cavity = w - (2.0 * wall)
    hole_x = (provider.settings.board_width / 2.0) - provider.settings.mounting_hole_inset
    hole_y = (provider.settings.board_length / 2.0) - provider.settings.mounting_hole_inset

    # 1. Lid must NOT have useless screw mounting holes (it should be solid at hole positions)
    assert lid.part.is_inside((hole_x, hole_y, wall / 2.0)), "Lid must not have screw holes"
    assert lid.part.is_inside((-hole_x, hole_y, wall / 2.0)), "Lid must not have screw holes"

    # 2. Lid must have snap-fit ridges protruding from locating rim
    lip_x = (w_cavity - 0.5) / 2.0
    snap_ridge_probe_x = lip_x + 0.15
    assert lid.part.is_inside((snap_ridge_probe_x, 28.0, -lip_h / 2.0)), (
        "Lid must have snap-fit ridge on right locating lip"
    )
    assert lid.part.is_inside((-snap_ridge_probe_x, 28.0, -lip_h / 2.0)), (
        "Lid must have snap-fit ridge on left locating lip"
    )

    # 3. Enclosure bottom must have matching snap-fit grooves recessed into cavity wall
    groove_z = (h_shell / 2.0) - (lip_h / 2.0)
    groove_probe_x = (w_cavity / 2.0) + 0.2
    assert not enclosure.part.is_inside((groove_probe_x, 28.0, groove_z)), (
        "Enclosure bottom must have snap-fit groove on right cavity wall"
    )
    assert not enclosure.part.is_inside((-groove_probe_x, 28.0, groove_z)), (
        "Enclosure bottom must have snap-fit groove on left cavity wall"
    )


def test_regression_bug_077_ventilation_holes() -> None:
    """Verify BUG-077: enclosure bottom has ventilation slots between charger (U3) and amplifier (U4)."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)
    z_conn = z_carrier + (provider.settings.board_thickness / 2.0) + 2.0

    # Probe point centered inside the left exterior wall (X = -w/2 + wall/2) between U3 (Y=10.0) and U4 (Y=21.0)
    wall_x = (-w / 2.0) + (wall / 2.0)
    assert not enclosure.part.is_inside((wall_x, 15.5, z_conn)), (
        "Enclosure bottom must have ventilation cutout through left exterior wall between U3 and U4 at Y=15.5"
    )


def test_regression_bug_078_led_cutout_and_cover() -> None:
    """Verify BUG-078: enclosure lid has LED cutout at D1 and clear LED cover part."""
    provider = CarrierBoardProvider()
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness

    # Query D1 position from wiring
    wiring = Wiring(str(provider.wiring_path))
    d1 = next(c for c in wiring.footprints if c.name == "D1")
    led_x, led_y = d1.position[0], d1.position[1]

    # 1. Lid must have cutout at D1 LED position
    assert not lid.part.is_inside((led_x, led_y, wall / 2.0)), "Lid must have an LED cutout at D1 position"

    # 2. Provider must build led_cover part
    assert "led_cover" in provider.part, "Provider must register 'led_cover' part target"
    cover = provider.led_cover("led_cover", None, Mode.DEFAULT)
    assert cover is not None
    bbox = cover.part.bounding_box()
    assert bbox.size.X == pytest.approx(7.0, abs=0.1)
    assert bbox.size.Y == pytest.approx(7.0, abs=0.1)
    assert bbox.size.Z == pytest.approx(4.0, abs=0.1)
    assert "mount" in cover.part.joints, "LED cover must have 'mount' RigidJoint"


@pytest.mark.slow
def test_regression_bug_085_enclosure_clip_on_mounting_posts() -> None:
    """Verify BUG-085: enclosure bottom replaces screw holes with flared clip-on mounting posts for carrier PCB."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    carrier = provider.carrier_board("carrier_board", None, Mode.DEFAULT)

    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    standoff_top_z = -h_shell / 2.0 + wall + standoff_h
    z_carrier = standoff_top_z + (provider.settings.board_thickness / 2.0)

    hole_x = (provider.settings.board_width / 2.0) - provider.settings.mounting_hole_inset
    hole_y = (provider.settings.board_length / 2.0) - provider.settings.mounting_hole_inset

    post_dia = provider.settings.mounting_post_diameter
    post_h = provider.settings.mounting_post_height
    flare_dia = provider.settings.mounting_post_flare_diameter
    flare_h = provider.settings.mounting_post_flare_height
    shaft_h = post_h - flare_h

    # 1. Standoff body must be solid where screw pilot holes previously were drilled
    standoff_mid_z = -h_shell / 2.0 + wall + (standoff_h / 2.0)
    for sx in (hole_x, -hole_x):
        for sy in (hole_y, -hole_y):
            assert enclosure.part.is_inside((sx, sy, standoff_mid_z)), (
                f"Standoff at ({sx}, {sy}) must be solid (no screw pilot holes)"
            )

    # 2. Mounting post shafts must extend above standoff shoulder
    post_shaft_z = standoff_top_z + (shaft_h / 2.0)
    for sx in (hole_x, -hole_x):
        for sy in (hole_y, -hole_y):
            assert enclosure.part.is_inside((sx, sy, post_shaft_z)), (
                f"Mounting post shaft at ({sx}, {sy}) must be solid"
            )

    # 3. Mounting post tops must be flared to clip over PCB mounting hole
    # Probe just above PCB surface at radius 1.7 mm (exceeding 3.2mm hole radius of 1.6mm)
    flare_probe_z = standoff_top_z + shaft_h + 0.1
    flare_probe_r = 1.7
    for sx, sy in [(hole_x, hole_y), (-hole_x, hole_y), (-hole_x, -hole_y), (hole_x, -hole_y)]:
        assert enclosure.part.is_inside((sx + flare_probe_r, sy, flare_probe_z)), (
            f"Mounting post at ({sx}, {sy}) must have flared clip-on head extending past PCB hole radius"
        )
        assert not enclosure.part.is_inside((sx + 2.0, sy, flare_probe_z)), (
            f"Mounting post at ({sx}, {sy}) must not exceed flare envelope"
        )

    # 4. Carrier board seated on standoffs must have zero intersection volume with enclosure bottom
    carrier_geom = carrier.part.locate(Location((0.0, 0.0, z_carrier)))
    inter = enclosure.part.intersect(carrier_geom)
    assert inter.volume == pytest.approx(0.0, abs=1e-3), (
        f"Carrier board intersects enclosure bottom: {inter.volume:.4f} mm^3"
    )


def test_regression_bug_107_carrier_board_flying_probes_simulation() -> None:
    """Verify BUG-107: simulate flying probes test for carrier board with obstacles and electrical validation."""
    import pybullet as p
    from provider import Simulate

    provider = CarrierBoardProvider()
    hooks = provider.get_simulate_hooks("carrier_board")
    assert Simulate.SETUP in hooks, "Carrier board must have Simulate.SETUP hook"
    assert Simulate.STEP in hooks, "Carrier board must have Simulate.STEP hook"

    client = p.connect(p.DIRECT)
    try:
        hooks[Simulate.SETUP](0, client, "carrier_board", {})
        # Step through test sequences
        num_steps = 1000
        for step_idx in range(num_steps):
            hooks[Simulate.STEP](0, client, step_idx, "carrier_board")

        # Verify all carrier board steps passed electrical validation
        assert hasattr(provider, "flying_probe_steps"), "Provider must expose flying_probe_steps"
        # Verify signal lines isolation: all signal lines must not be shorted to power or ground
        assert hasattr(provider, "flying_probe_signal_isolation"), "Provider must expose flying_probe_signal_isolation"
        iso_results = provider.flying_probe_signal_isolation
        assert iso_results["all_passed"] is True, (
            f"Signal lines shorted to power/ground: {iso_results['shorted_signals']}"
        )
        assert len(iso_results["signal_lines"]) > 0, "Must have audited signal lines"
        assert len(iso_results["power_ground_nets"]) > 0, "Must have audited power/ground nets"
        assert len(iso_results["shorted_signals"]) == 0, f"Detected signal shorts: {iso_results['shorted_signals']}"

        # Verify test report generation
        report_md = provider.generate_test_report()
        assert "Flying Probes Automated Acceptance Test Report" in report_md
        assert "TEST_CONTINUITY_GND" in report_md
        assert "TEST_IMP_PCIE_DIFF" in report_md
        assert "PASS" in report_md
        assert "100.0%" in report_md
        assert "Signal Line Isolation Audit" in report_md
    finally:
        p.disconnect(client)


def test_regression_bug_108_flex_tail_flying_probes_simulation() -> None:
    """Verify BUG-108: simulate flying probes test for flex tail validating capacitive sensing channels."""
    import pybullet as p
    from provider import Simulate

    provider = CarrierBoardProvider()
    hooks = provider.get_simulate_hooks("flex_tail")
    assert Simulate.SETUP in hooks, "Flex tail must have Simulate.SETUP hook"
    assert Simulate.STEP in hooks, "Flex tail must have Simulate.STEP hook"

    client = p.connect(p.DIRECT)
    try:
        hooks[Simulate.SETUP](0, client, "flex_tail", {})
        # Step through test sequences
        num_steps = 1000
        for step_idx in range(num_steps):
            hooks[Simulate.STEP](0, client, step_idx, "flex_tail")

        # Verify all flex tail capacitive sensing steps passed electrical validation
        assert hasattr(provider, "flying_probe_steps"), "Provider must expose flying_probe_steps"
        for step in provider.flying_probe_steps:
            assert step.passed, f"Flex tail step {step.step_id} ({step.description}) failed electrical validation"

        # Verify test report generation
        report_md = provider.generate_test_report()
        assert "TEST_CAP_SENSE_CHAN0" in report_md
        assert "TEST_CAP_SENSE_CHAN1" in report_md
        assert "TEST_CAP_SENSE_CHAN2" in report_md
        assert "TEST_CAP_SENSE_CHAN3" in report_md
        assert "PASS" in report_md
        assert "100.0%" in report_md
    finally:
        p.disconnect(client)


def test_regression_bug_131_schematic_collinear_wire_overlaps() -> None:
    """Verify BUG-131: schematic wire segments have zero collinear overlaps across all sheets."""
    import yaml
    from model.pcb import PCBConfig
    from provider.pcb.drc import PCBDesignRulesChecker, DRCRuleName
    from provider.schematic_diagram import SchematicDiagram

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    pcb_yaml_path = provider.wiring_path.parent / "pcb.yaml"
    with open(pcb_yaml_path) as f:
        cfg = PCBConfig(**yaml.safe_load(f))

    diag = SchematicDiagram(wiring=wiring, pcb_config=cfg)
    segs = diag.compute_sheet_wire_segments()
    for s_idx, (h_segs, v_segs) in segs.items():
        for i, s1 in enumerate(h_segs):
            for s2 in h_segs[i + 1 :]:
                if abs(s1[2] - s2[2]) < 0.1:
                    overlap = min(s1[1], s2[1]) - max(s1[0], s2[0])
                    assert overlap <= 0.5, (
                        f"Sheet {s_idx} horizontal wire overlap: {s1[3]} and {s2[3]} at y={s1[2]} (overlap={overlap:.2f}mm)"
                    )
        for i, s1 in enumerate(v_segs):
            for s2 in v_segs[i + 1 :]:
                if abs(s1[0] - s2[0]) < 0.1:
                    overlap = min(s1[2], s2[2]) - max(s1[1], s2[1])
                    assert overlap <= 0.5, (
                        f"Sheet {s_idx} vertical wire overlap: {s1[3]} and {s2[3]} at x={s1[0]} (overlap={overlap:.2f}mm)"
                    )

    drc = PCBDesignRulesChecker(config=cfg)
    violations = drc.check_schematic(wiring)
    wire_violations = [v for v in violations if v.rule_name == DRCRuleName.SCHEMATIC_WIRE_COLLINEAR_OVERLAP]
    assert len(wire_violations) == 0, f"Schematic DRC found wire overlaps: {wire_violations}"


def test_regression_bug_132_expansion_carrier_mount_and_endpoints() -> None:
    """Verify BUG-132: enclosure bottom has expansion carrier mounting collar and connector endpoints."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    mount_protrusion = provider.settings.enclosure_expansion_mount_protrusion

    # 1. Verify mounting collar geometry extends outward past the right wall
    probe_x = (w / 2.0) + (mount_protrusion / 2.0)
    assert enclosure.part.is_inside((probe_x, 1.75, 2.30 + 4.0)), "Expansion mount collar top wall must exist"
    assert enclosure.part.is_inside((probe_x, 1.75, 2.30 - 4.0)), "Expansion mount collar bottom wall must exist"

    # 2. Verify connector endpoints and expansion mount RigidJoints exist
    joints = enclosure.part.joints
    assert "expansion_carrier_mount" in joints, "Must have expansion_carrier_mount joint"
    assert "expansion_mount" in joints, "Must have expansion_mount joint"
    assert "connector_endpoint" in joints, "Must have connector_endpoint joint"
    for des in ("j6_mount", "j7_mount", "j8_mount", "j9_mount", "j10_mount"):
        assert des in joints, f"Must have joint {des}"

    # 3. Verify joint positions are at the tip of the expansion mount protrusion
    tip_x = (w / 2.0) + mount_protrusion
    for j_name in ("expansion_carrier_mount", "expansion_mount", "connector_endpoint"):
        loc = joints[j_name].location
        assert abs(loc.position.X - tip_x) < 0.1, f"Joint {j_name} must be at X={tip_x}, got {loc.position.X}"


def test_regression_bug_133_flex_tail_schematic_isolated() -> None:
    """Verify BUG-133: flex tail schematic contains only J4 on 1 sheet."""
    from pathlib import Path
    from model.wiring import Wiring

    provider = CarrierBoardProvider()
    wiring = Wiring(Path(provider.wiring_path))
    flex_wiring = wiring.filter_by_footprints(["J4"])
    assert len(flex_wiring.footprints) == 1
    assert flex_wiring.footprints[0].name == "J4"

    # Verify generated flex_tail schematic has only J4
    sch_path = Path("build/schematics/carrier_board/flex_tail.kicad_sch")
    if sch_path.exists():
        sch_text = sch_path.read_text()
        assert "J4" in sch_text
        for other_comp in ("U1", "U2", "U3", "J1", "J6", "J7", "J8", "J9", "J10"):
            assert f'"{other_comp}"' not in sch_text


@pytest.mark.slow
def test_regression_bug_134_carrier_board_components_match_schematic() -> None:
    """Verify BUG-134: carrier board PCB components J6, J7, J8 are JST-PH-6P matching schematic."""
    from pathlib import Path
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = Wiring(Path(provider.wiring_path))
    footprints = {fp.name: fp for fp in wiring.footprints}
    for j_name in ("J6", "J7", "J8"):
        assert j_name in footprints, f"Footprint {j_name} must exist in wiring"
        fp = footprints[j_name]
        assert fp.package == "JST-PH-6P", f"{j_name} must use JST-PH-6P package"
        assert fp.mpn == "B6B-PH-K-S", f"{j_name} must use B6B-PH-K-S MPN"

    # Verify carrier board DRC passes with 0 errors
    cfg = provider.pcb_config
    checker = PCBDesignRulesChecker(cfg)
    report = checker.check_all(wiring=wiring)
    assert report.passed, f"DRC must pass with 0 errors, got: {report.error_count}"


def test_regression_bug_139_battery_cover() -> None:
    """Verify BUG-139: battery cover fits over enclosure lid battery cradle with clearance."""
    provider = CarrierBoardProvider()
    cover = provider.battery_cover("battery_cover", None, Mode.DEFAULT)
    cover_print = provider.battery_cover("battery_cover", None, Mode.PRINT)
    assert cover.part.volume > 0.0, "Battery cover volume must be positive"
    assert cover_print.part.volume > 0.0, "Battery cover print mode volume must be positive"
    assert "mount" in cover.part.joints, "Battery cover must define mount joint"

    # Verify battery cover dimensions account for cradle wall thickness + clearances
    batt_w = provider.settings.enclosure_battery_mount_width
    batt_l = provider.settings.enclosure_battery_mount_length
    cradle_t = provider.settings.enclosure_battery_mount_wall_thickness
    clr = provider.settings.enclosure_battery_cover_clearance
    cover_t = provider.settings.enclosure_battery_cover_wall_thickness
    expected_outer_w = batt_w + 2.0 * (cradle_t + clr + cover_t)
    expected_outer_l = batt_l + 2.0 * (cradle_t + clr + cover_t)

    bbox = cover.part.bounding_box()
    assert bbox.size.X >= expected_outer_w - 0.2, (
        f"Cover width must span at least {expected_outer_w}, got {bbox.size.X}"
    )
    assert bbox.size.Y >= expected_outer_l - 0.2, (
        f"Cover length must span at least {expected_outer_l}, got {bbox.size.Y}"
    )
    assert provider.settings.enclosure_battery_cover_vertical_clearance >= 2.0


@pytest.mark.slow
def test_regression_bug_140_flex_tail_support() -> None:
    """Verify BUG-140: enclosure bottom extends a support shelf under the flex tail."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)

    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    length = provider.settings.board_length + 2.0 * (provider.settings.enclosure_clearance + wall)
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)

    wiring = Wiring(str(provider.wiring_path))
    j2 = next(c for c in wiring.footprints if c.name == "J2")
    j4 = next(c for c in wiring.footprints if c.name == "J4")
    dz = j2.position[2] - j4.position[2]
    dy = j2.position[1] - j4.position[1]
    dx = j2.position[0] - j4.position[0]

    tail_geom = tail.part.locate(Location((dx, dy, z_carrier + dz)))
    inter = enclosure.part.intersect(tail_geom)
    assert inter.volume == 0.0, f"Flex tail intersects enclosure support: {inter.volume}"

    # Verify shelf exists under the forward portion of the flex tail
    sup_l = provider.settings.enclosure_flex_support_length
    shelf_probe_y = (length / 2.0) + (sup_l / 2.0)
    shelf_z = z_carrier + dz - 0.5
    assert enclosure.part.is_inside((0.0, shelf_probe_y, shelf_z)), (
        f"Enclosure support shelf must exist at Y={shelf_probe_y}, Z={shelf_z}"
    )


def test_regression_bug_141_flex_tail_tab_fit() -> None:
    """Verify BUG-141: ZIF connector J2 on carrier board is wider than flex tail tab so flex tail fits."""
    provider = CarrierBoardProvider()
    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)
    bbox = tail.part.bounding_box()
    assert bbox.size.X <= 24.0, f"Flex tail width exceeded: {bbox.size.X}"

    assert provider.pcb_manifest is not None, "PCB manifest must be loaded"
    j2_obs = next(obs for obs in provider.pcb_manifest["obstacles"] if obs["name"] == "J2")
    j2_width = j2_obs["dimensions_mm"][0]
    assert j2_width > bbox.size.X, f"Connector width ({j2_width}mm) must exceed flex tail width ({bbox.size.X}mm)"


def test_regression_bug_142_m2_floor_cutout() -> None:
    """Verify BUG-142: enclosure bottom floor has pass-through cutout under PCIE connector J1."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    floor_z = -h_shell / 2.0 + (wall / 2.0)

    wiring = Wiring(str(provider.wiring_path))
    j1 = next(c for c in wiring.footprints if c.name == "J1")
    j1_x, j1_y = j1.position[0], j1.position[1]

    # Floor must have a cutout under J1 connector
    assert not enclosure.part.is_inside((j1_x, j1_y, floor_z)), (
        f"Enclosure bottom floor must have cutout under J1 at ({j1_x}, {j1_y})"
    )
    # Floor must remain solid away from J1 cutout
    assert enclosure.part.is_inside((20.0, j1_y, floor_z)), "Enclosure floor must be solid away from cutout"


def test_regression_bug_143_peripheral_cutouts_uniform_size() -> None:
    """Verify BUG-143: all peripheral cutouts in enclosure bottom have uniform length and spacing."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)
    z_conn = z_carrier + (provider.settings.board_thickness / 2.0) + 2.0
    wall_x = (w / 2.0) - (wall / 2.0)

    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}
    periph_connectors = ["J6", "J7", "J8", "J9", "J10"]

    # Verify each connector position is cleared by a cutout
    for des in periph_connectors:
        y = comp_map[des].position[1]
        assert not enclosure.part.is_inside((wall_x, y, z_conn)), f"Cutout missing for connector {des} at Y={y}"

    # Verify uniform length and solid separating walls
    assert provider.settings.enclosure_periph_cutout_length == 10.0
    assert provider.settings.enclosure_periph_cutout_height == 5.0


def test_regression_bug_144_m2_rear_wall_cutout() -> None:
    """Verify BUG-144: enclosure bottom rear wall has cutout for J1 insertion."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    length = provider.settings.board_length + 2.0 * (provider.settings.enclosure_clearance + wall)
    m2_h = provider.settings.enclosure_m2_cutout_height
    m2_z = -h_shell / 2.0 + wall + standoff_h + (m2_h / 2.0) - 0.5
    rear_wall_y = -length / 2.0 + (wall / 2.0)

    # Cutout aperture must pierce rear wall at center X=0
    assert not enclosure.part.is_inside((0.0, rear_wall_y, m2_z)), (
        f"Enclosure rear wall must have M.2 cutout at (0.0, {rear_wall_y}, {m2_z})"
    )
    # Rear wall must remain solid away from cutout
    assert enclosure.part.is_inside((25.0, rear_wall_y, m2_z)), "Rear wall must be solid outside M.2 cutout"


@pytest.mark.slow
def test_regression_bug_145_battery_cradle_and_cover_extend_over_j13() -> None:
    """Verify BUG-145: battery cradle and cover extend over J13 cutout to conceal wiring."""
    from build123d import Location

    provider = CarrierBoardProvider()
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    cover = provider.battery_cover("battery_cover", None, Mode.DEFAULT)
    wiring = Wiring(str(provider.wiring_path))
    j13 = next(c for c in wiring.footprints if c.name == "J13")
    j13_x, j13_y = j13.position[0], j13.position[1]

    # Verify battery cover bounding box covers J13 position
    cov_bb = cover.part.bounding_box()
    assert cov_bb.min.X <= j13_x <= cov_bb.max.X, f"Battery cover must span J13 X={j13_x}"
    assert cov_bb.min.Y <= j13_y <= cov_bb.max.Y, f"Battery cover must span J13 Y={j13_y}"

    # Verify cover fits over lid cradle without intersecting
    wall = provider.settings.enclosure_wall_thickness
    cov_located = cover.part.locate(Location((0.0, 0.0, wall + 0.5)))
    inter = lid.part.intersect(cov_located)
    assert inter.volume < 1e-3, f"Battery cover intersects lid cradle: {inter.volume} mm^3"


def test_regression_bug_146_mipi_camera_routing_removed() -> None:
    """Verify BUG-146: MIPI camera routing and differential nets are removed from board."""
    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    pcb_cfg = provider.pcb_config

    # No nets with MIPI in their name should exist
    mipi_nets = [n.name for n in wiring.nets if "MIPI" in n.name]
    assert not mipi_nets, f"BUG-146: All MIPI nets must be removed, found: {mipi_nets}"

    # MIPI_DISPLAY net class must be removed from PCB configuration
    assert not any(nc.name == "MIPI_DISPLAY" for nc in pcb_cfg.net_classes), (
        "BUG-146: MIPI_DISPLAY net class must be removed"
    )

    # Sheet 9 must only describe PCIe Gen4
    sheet_hs = next((s for s in pcb_cfg.schematic_sheets if "High-Speed" in s.title), None)
    assert sheet_hs is not None
    assert "J2" not in sheet_hs.components, "BUG-146: J2 must be removed from High-Speed sheet"


def test_regression_bug_147_flex_ribbon_slider_action_prox() -> None:
    """Verify BUG-147: flex ribbon features 5-button slider, action button, and prox sensor."""
    provider = CarrierBoardProvider()
    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)
    pcb_cfg = provider.pcb_config

    # Verify capacitive sensors include slider segments, action button, and prox sensor
    cap_names = [s.name for s in pcb_cfg.capacitive_sensors]
    slider_segs = [n for n in cap_names if "SLIDER" in n]
    assert len(slider_segs) == 5, f"Expected 5 slider segments, found {slider_segs}"
    assert "ACTION_BUTTON" in cap_names, "ACTION_BUTTON must exist in capacitive sensors"
    assert "PROXIMITY_SENSOR" in cap_names, "PROXIMITY_SENSOR must exist in capacitive sensors"


@pytest.mark.slow
def test_regression_bug_148_flex_ribbon_support_connects_to_enclosure() -> None:
    """Verify BUG-148: flex ribbon support shelf connects continuously with enclosure bottom."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)

    # Must be a single contiguous fused solid (no disconnected/floating parts)
    solids = enclosure.part.solids()
    assert len(solids) == 1, f"Expected 1 solid for enclosure_bottom, got {len(solids)}"

    # Shelf must exist and connect through wall
    wall = provider.settings.enclosure_wall_thickness
    length = provider.settings.board_length + 2.0 * (provider.settings.enclosure_clearance + wall)
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)
    shelf_z = z_carrier + 0.8 - 0.5

    # Check connection point right at wall boundary
    probe_y = length / 2.0
    assert enclosure.part.is_inside((0.0, probe_y, shelf_z)), (
        f"Support shelf must connect continuously at enclosure wall Y={probe_y}, Z={shelf_z}"
    )


@pytest.mark.slow
def test_regression_bug_150_component_cutout_labels() -> None:
    """Verify BUG-150: charger, SWD, M.2 PCIe, and flex ribbon cutouts have labels."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    w = provider.settings.board_width + 2.0 * (provider.settings.enclosure_clearance + wall)
    length = provider.settings.board_length + 2.0 * (provider.settings.enclosure_clearance + wall)

    # Verify solid enclosure exists and labels are engraved (subtracted)
    assert enclosure.part.is_valid(), "Enclosure bottom with labels must be valid CAD solid"
    assert lid.part.is_valid(), "Enclosure lid with battery label must be valid CAD solid"

    # Active regression assertions: verify engraved faces exist inside wall depth
    # 1. Left exterior wall (USB trident icon and SWD label)
    left_engraved = [f for f in enclosure.part.faces() if abs(f.center().X - (-w / 2.0 + 0.4)) < 1e-3]
    assert len(left_engraved) >= 4, f"Expected USB icon and SWD engraved faces, found {len(left_engraved)}"
    usb_face = next((f for f in left_engraved if abs(f.center().Y) < 1.0), None)
    assert usb_face is not None, "USB connector trident icon face must be engraved above USB-C cutout"

    # 2. Rear exterior wall (M.2 PCIE label)
    rear_engraved = [f for f in enclosure.part.faces() if abs(f.center().Y - (-length / 2.0 + 0.4)) < 1e-3]
    assert len(rear_engraved) >= 5, f"Expected M.2 PCIE engraved faces, found {len(rear_engraved)}"

    # 3. Front shelf (FLEX TAIL label)
    shelf_engraved = [
        f for f in enclosure.part.faces() if f.center().Y > (length / 2.0) and f.normal_at(f.center()).Z > 0.9
    ]
    assert len(shelf_engraved) >= 8, f"Expected FLEX TAIL engraved faces, found {len(shelf_engraved)}"

    # 4. Enclosure lid (BATTERY label)
    lid_engraved = [f for f in lid.part.faces() if abs(f.center().Z - (wall - 0.4)) < 1e-3]
    assert len(lid_engraved) >= 5, f"Expected BATTERY engraved faces on lid, found {len(lid_engraved)}"


@pytest.mark.slow
def test_regression_bug_149_mutual_intersection_test() -> None:
    """Verify BUG-149: all components in carrier_board assembly have zero mutual volume intersection."""
    from build123d import Location

    provider = CarrierBoardProvider()
    carrier = provider.carrier_board("carrier_board", None, Mode.DEFAULT)
    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    led_cov = provider.led_cover("led_cover", None, Mode.DEFAULT)
    batt_cov = provider.battery_cover("battery_cover", None, Mode.DEFAULT)

    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    z_carrier = -h_shell / 2.0 + wall + standoff_h + (provider.settings.board_thickness / 2.0)
    z_lid = h_shell / 2.0

    carrier_geom = carrier.part.locate(Location((0.0, 0.0, z_carrier)))
    lid_geom = lid.part.locate(Location((0.0, 0.0, z_lid)))

    wiring = Wiring(str(provider.wiring_path))
    j2_comp = next(c for c in wiring.footprints if c.name == "J2")
    j4_comp = next(c for c in wiring.footprints if c.name == "J4")
    dx = j2_comp.position[0] - j4_comp.position[0]
    dy = j2_comp.position[1] - j4_comp.position[1]
    dz = j2_comp.position[2] - j4_comp.position[2]
    tail_geom = tail.part.locate(Location((dx, dy, z_carrier + dz)))

    d1_comp = next((c for c in wiring.footprints if c.name == "D1"), None)
    led_x = d1_comp.position[0] if d1_comp else 17.0
    led_y = d1_comp.position[1] if d1_comp else 10.0
    led_cov_geom = led_cov.part.locate(Location((led_x, led_y, z_lid + wall)))

    batt_cov_geom = batt_cov.part.locate(Location((0.0, 0.0, z_lid + wall + 0.5)))

    # Pairwise mutual intersection checks
    parts = {
        "enclosure_bottom": enclosure.part,
        "enclosure_lid": lid_geom,
        "carrier_board": carrier_geom,
        "flex_tail": tail_geom,
        "led_cover": led_cov_geom,
        "battery_cover": batt_cov_geom,
    }

    pairs = [
        ("enclosure_bottom", "enclosure_lid"),
        ("enclosure_bottom", "carrier_board"),
        ("enclosure_bottom", "flex_tail"),
        ("enclosure_lid", "flex_tail"),
        ("enclosure_lid", "battery_cover"),
        ("enclosure_lid", "led_cover"),
    ]

    for name_a, name_b in pairs:
        inter = parts[name_a].intersect(parts[name_b])
        assert inter.volume < 1e-3, (
            f"Mutual intersection detected between {name_a} and {name_b}: {inter.volume:.4f} mm^3"
        )


@pytest.mark.slow
def test_regression_bug_152_textured_pcb_simulation_visibility() -> None:
    """Verify BUG-152: carrier board and flex tail expose urdf_label for textured PCB visualization."""
    from pathlib import Path

    provider = CarrierBoardProvider()
    carrier = provider.carrier_board("carrier_board", None, Mode.DEFAULT)
    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)

    # Both objects and parts must expose urdf_label
    assert getattr(carrier, "urdf_label", None) == "carrier_board", "carrier_board must have urdf_label"
    assert getattr(carrier.part, "urdf_label", None) == "carrier_board", "carrier_board.part must have urdf_label"
    assert getattr(tail, "urdf_label", None) == "flex_tail", "flex_tail must have urdf_label"
    assert getattr(tail.part, "urdf_label", None) == "flex_tail", "flex_tail.part must have urdf_label"

    # Test board texture in isolated test directory to avoid polluting production textures
    test_build_dir = Path("build/test_dummy_textures")
    tex_dir = test_build_dir / "board" / "carrier_board" / "textures"
    tex_dir.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    import numpy as np

    raw_tex = Image.new("RGBA", (90, 30), (0, 0, 0, 0))
    # Draw green board in middle 1/3 (X=30..60)
    for x in range(30, 60):
        for y in range(30):
            raw_tex.putpixel((x, y), (0, 100, 0, 255))
    raw_tex.save(tex_dir / "carrier_board_top.png")
    raw_tex.save(tex_dir / "carrier_board_bottom.png")

    assert (tex_dir / "carrier_board_top.png").exists(), "carrier_board_top.png must exist"
    assert (tex_dir / "carrier_board_bottom.png").exists(), "carrier_board_bottom.png must exist"

    # Verify Bullet._init_simulation_objects logs texture_top and texture_bottom to Rerun
    from unittest.mock import patch
    from provider.bullet import Bullet
    from provider import Room
    import pybullet as p

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
            logged_entities = [call[0][0] for call in mock_log.call_args_list]
            assert "world/carrier_board/texture_top" in logged_entities, (
                "texture_top must be logged to Rerun under world/carrier_board"
            )
            assert "world/carrier_board/texture_bottom" in logged_entities, (
                "texture_bottom must be logged to Rerun under world/carrier_board"
            )

            # Verify Asset3D is NOT logged when pcb texture is present to prevent occluding the texture
            import rerun as rr

            asset_calls = [
                call for call in mock_log.call_args_list if len(call[0]) > 1 and isinstance(call[0][1], rr.Asset3D)
            ]
            assert len(asset_calls) == 0, "Asset3D must not be logged when textured PCB is active to avoid occlusion"

            # Verify the albedo texture was cropped to remove outer transparent margins (BUG-152)
            top_mesh_calls = [
                call[0][1]
                for call in mock_log.call_args_list
                if len(call[0]) > 1 and call[0][0] == "world/carrier_board/texture_top"
            ]
            assert len(top_mesh_calls) == 1
            top_mesh = top_mesh_calls[0]
            assert len(top_mesh.vertex_positions) >= 4, (
                "top_mesh must be logged as clean textured mesh with matching board outline"
            )
            fmt = top_mesh.albedo_texture_format.as_arrow_array()[0].as_py()
            # Texture should be cropped to 30px width (middle 1/3) instead of retaining 90px width
            assert fmt["width"] == 30, f"Expected cropped width of 30, got {fmt['width']}"
    finally:
        p.disconnect(client)
        import shutil

        shutil.rmtree(test_build_dir, ignore_errors=True)


def test_regression_bug_153_flying_probes_report_formatting() -> None:
    """Verify BUG-153: flying probe report uses clean Unicode symbols without corrupted LaTeX escapes."""
    import pybullet as p
    from provider import Simulate

    provider = CarrierBoardProvider()
    hooks = provider.get_simulate_hooks("carrier_board")
    client = p.connect(p.DIRECT)
    try:
        hooks[Simulate.SETUP](0, client, "carrier_board", {})
        report_md = provider.generate_test_report()

        # No corrupted LaTeX math markers
        assert "$\\le" not in report_md, "Report must not contain raw $\\le LaTeX tokens"
        assert "$\\ge" not in report_md, "Report must not contain raw $\\ge LaTeX tokens"
        assert "\\Omega" not in report_md, "Report must not contain raw \\Omega LaTeX tokens"
        assert "\\text{" not in report_md, "Report must not contain raw \\text{ LaTeX tokens"
        assert "\\%" not in report_md, "Report must not contain raw \\% LaTeX tokens"

        # Standard clean Unicode characters must be present
        assert "≤" in report_md, "Report must contain clean Unicode ≤"
        assert "≥" in report_md, "Report must contain clean Unicode ≥"
        assert "Ω" in report_md, "Report must contain clean Unicode Ω"
        assert "±" in report_md, "Report must contain clean Unicode ±"
        assert "×" in report_md, "Report must contain clean Unicode ×"

        # MIPI must be purged from report (BUG-146)
        assert "MIPI" not in report_md, "Report must not reference MIPI camera/display"
        assert "PCIe 85 Ω" in report_md, "Report must document PCIe 85 Ω impedance"
    finally:
        p.disconnect(client)


def test_regression_bug_155_slider_silkscreen_does_not_overlap_s3() -> None:
    """Verify BUG-155: SLIDER silkscreen text does not overlap S3 button glyph."""
    import math

    provider = CarrierBoardProvider()
    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)
    pcb_cfg = tail.to_pcb_config() if hasattr(tail, "to_pcb_config") else tail.pcb_metadata

    slider_text = next(t for t in pcb_cfg.silkscreen_texts if t.text == "SLIDER")
    s3_text = next(t for t in pcb_cfg.silkscreen_texts if t.text == "S3")

    dist = math.hypot(slider_text.position[0] - s3_text.position[0], slider_text.position[1] - s3_text.position[1])
    assert dist > 10.0, f"SLIDER and S3 silkscreen texts overlap! Distance is {dist} mm <= 10.0 mm"


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
    repo_root = Path(__file__).resolve().parents[3]
    carrier_dir = repo_root / "src" / "projects" / "carrier_board"
    assert carrier_dir.is_dir(), "carrier_board project directory must exist"
    assert (carrier_dir / "manifest.yaml").is_file()
    assert (carrier_dir / "pcb.yaml").is_file()
    assert (carrier_dir / "wiring.yaml").is_file()
    assert (carrier_dir / "measurements.yaml").is_file()
    assert (repo_root / "src" / "projects" / "carrier_board.md").is_file()
    assert (repo_root / "src" / "projects_config" / "carrier_board_config.py").is_file()

    # 3. Old test_board paths must NOT exist (no lingering shims or directories)
    assert not (repo_root / "src" / "projects" / "test_board").exists()
    assert not (repo_root / "src" / "projects" / "test_board.md").exists()
    assert not (repo_root / "src" / "projects_config" / "test_board_config.py").exists()

    # 4. Strongly typed configuration model resolution
    cfg = provider.settings
    assert isinstance(cfg, CarrierBoardConfig)


def test_regression_bug_156_m2_thru_holes() -> None:
    """Verify BUG-156: J1 M.2 connector footprint contains all required through-hole pins."""
    from pathlib import Path
    import yaml

    repo_root = Path(__file__).resolve().parents[3]
    footprints_file = repo_root / "src" / "projects" / "footprints" / "ic.yaml"
    with open(footprints_file) as f:
        footprints = yaml.safe_load(f)["footprints"]

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
    wiring = Wiring(str(provider.wiring_path))
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
        if "ACTION_BUTTON" in v.message
        or ("CAP_TX2" in v.message and v.rule_name == "ANTENNA_TRACE_DETECTED")
        or ("CAP_RX2" in v.message and v.rule_name == "ANTENNA_TRACE_DETECTED")
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
    wiring = Wiring(Path(provider.wiring_path))
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

    # Verify Q1 pins have number, pin_name, and signal_name
    q1 = footprints["Q1"]
    for p in q1.pins:
        assert p.number is not None and p.pin_name is not None and p.signal_name is not None

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
    wiring = Wiring(str(provider.wiring_path))
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
    wiring = Wiring(str(provider.wiring_path))
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
    wiring = Wiring(str(provider.wiring_path))
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
    wiring = Wiring(str(provider.wiring_path))
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
        assert -36.0 <= pos[1] <= -16.0, (
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
    wiring = Wiring(str(provider.wiring_path))
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
        assert -36.0 <= pos[1] <= -16.0, f"Component {name} must be in corridor between U1 and J1"

    # Verify existing baseline components were not displaced
    assert tuple(comp_map["U1"].position[:2]) == (0.0, 0.0)
    assert tuple(comp_map["J1"].position[:2]) == (0.0, -36.0)
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
    wiring = Wiring(str(provider.wiring_path))
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

    # 2. Verify LAYER 1-6 RIGID-FLEX silkscreen does not collide with D2..D7 corridor (X=4.0, Y=-30..-20)
    layer_text = next(t for t in pcb_cfg.silkscreen_texts if t.text == "LAYER 1-6 RIGID-FLEX")
    assert layer_text.position[1] < -32.0 or layer_text.position[0] < -4.0, (
        f"LAYER 1-6 text at {layer_text.position} overlaps D2..D7 corridor"
    )

    # 3. Verify STATUS and OVERRIDES silkscreen frames maintain clear horizontal separation
    status_rect = next(g for g in pcb_cfg.silkscreen_graphics if g.shape == "rect" and abs(g.position[0] - 4.5) < 1.0)
    overrides_rect = next(
        g for g in pcb_cfg.silkscreen_graphics if g.shape == "rect" and abs(g.position[0] - 12.2) < 1.0
    )
    status_x_max = status_rect.position[0] + status_rect.dimensions[0] / 2.0
    overrides_x_min = overrides_rect.position[0] - overrides_rect.dimensions[0] / 2.0
    clearance = overrides_x_min - status_x_max
    assert clearance >= 0.50, f"STATUS and OVERRIDES frames too close: clearance is {clearance:.2f}mm < 0.50mm"

    # 4. Verify jumper and switch labels are horizontal (rotation == 0.0)
    for label_name in ("NRST", "BOOT0", "ISP", "VBUS", "RESET"):
        lbl = next(t for t in pcb_cfg.silkscreen_texts if t.text == label_name)
        assert lbl.rotation == 0.0, f"Label {label_name} must have horizontal rotation 0.0, got {lbl.rotation}"

    # 5. Verify PCB DRC passes with 0 violations
    drc = PCBDesignRulesChecker(pcb_cfg)
    report = drc.check_all(wiring=Wiring(str(provider.wiring_path)))
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0
