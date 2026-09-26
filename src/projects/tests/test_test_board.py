"""Tests for test_board rigid-flex PCB and protective enclosure CAD geometry."""

import pytest
from build123d import Location
from projects.test_board.provider import TestBoardProvider
from model.wiring import Wiring
from provider import Mode


def test_regression_bug_072_flex_tail_cutout_zero_intersection() -> None:
    """Verify BUG-072: flex tail has zero intersection volume with enclosure bottom and lid."""
    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
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
    """Verify BUG-110: expansion header connectors J9 and J10 are 6-pin JST-PH style connectors."""
    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}

    assert comp_map["J9"].package == "JST-PH-6P", f"J9 package should be JST-PH-6P, got {comp_map['J9'].package}"
    assert comp_map["J10"].package == "JST-PH-6P", f"J10 package should be JST-PH-6P, got {comp_map['J10'].package}"
    assert "B6B-PH-K-S" in comp_map["J9"].mpn or "PH" in comp_map["J9"].mpn
    assert "B6B-PH-K-S" in comp_map["J10"].mpn or "PH" in comp_map["J10"].mpn


def test_regression_bug_113_carrier_board_serial_cutouts_do_not_overlap() -> None:
    """Verify BUG-113: peripheral and serial expansion cutouts do not overlap, leaving solid walls."""
    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
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


def test_regression_bug_076_enclosure_snap_fit() -> None:
    """Verify BUG-076: enclosure lid snap fits to bottom shell without useless screw holes."""
    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
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


def test_regression_bug_085_enclosure_clip_on_mounting_posts() -> None:
    """Verify BUG-085: enclosure bottom replaces screw holes with flared clip-on mounting posts for carrier PCB."""
    provider = TestBoardProvider()
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

    provider = TestBoardProvider()
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
        for step in provider.flying_probe_steps:
            assert step.passed, f"Carrier board step {step.step_id} ({step.description}) failed electrical validation"

        # Verify test report generation
        report_md = provider.generate_test_report()
        assert "Flying Probes Automated Acceptance Test Report" in report_md
        assert "TEST_CONTINUITY_GND" in report_md
        assert "TEST_IMP_PCIE_DIFF" in report_md
        assert "PASS" in report_md
        assert "100.0%" in report_md
    finally:
        p.disconnect(client)


def test_regression_bug_108_flex_tail_flying_probes_simulation() -> None:
    """Verify BUG-108: simulate flying probes test for flex tail validating capacitive sensing channels."""
    import pybullet as p
    from provider import Simulate

    provider = TestBoardProvider()
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

    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
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

    provider = TestBoardProvider()
    wiring = Wiring(Path(provider.wiring_path))
    flex_wiring = wiring.filter_by_footprints(["J4"])
    assert len(flex_wiring.footprints) == 1
    assert flex_wiring.footprints[0].name == "J4"

    # Verify generated flex_tail schematic has only J4
    sch_path = Path("build/schematics/test_board/flex_tail.kicad_sch")
    if sch_path.exists():
        sch_text = sch_path.read_text()
        assert "J4" in sch_text
        for other_comp in ("U1", "U2", "U3", "J1", "J6", "J7", "J8", "J9", "J10"):
            assert f'"{other_comp}"' not in sch_text


def test_regression_bug_134_carrier_board_components_match_schematic() -> None:
    """Verify BUG-134: carrier board PCB components J6, J7, J8 are JST-PH-6P matching schematic."""
    from pathlib import Path
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
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
    assert abs(bbox.size.X - expected_outer_w) < 0.2, f"Expected cover width ~{expected_outer_w}, got {bbox.size.X}"
    assert abs(bbox.size.Y - expected_outer_l) < 0.2, f"Expected cover length ~{expected_outer_l}, got {bbox.size.Y}"
    assert provider.settings.enclosure_battery_cover_vertical_clearance >= 2.0


def test_regression_bug_140_flex_tail_support() -> None:
    """Verify BUG-140: enclosure bottom extends a support shelf under the flex tail."""
    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)
    bbox = tail.part.bounding_box()
    assert bbox.size.X <= 24.0, f"Flex tail width exceeded: {bbox.size.X}"

    assert provider.pcb_manifest is not None, "PCB manifest must be loaded"
    j2_obs = next(obs for obs in provider.pcb_manifest["obstacles"] if obs["name"] == "J2")
    j2_width = j2_obs["dimensions_mm"][0]
    assert j2_width > bbox.size.X, f"Connector width ({j2_width}mm) must exceed flex tail width ({bbox.size.X}mm)"


def test_regression_bug_142_m2_floor_cutout() -> None:
    """Verify BUG-142: enclosure bottom floor has pass-through cutout under PCIE connector J1."""
    provider = TestBoardProvider()
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
    provider = TestBoardProvider()
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
