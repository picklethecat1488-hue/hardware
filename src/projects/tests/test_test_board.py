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
    lengths = [
        provider.settings.enclosure_periph_4p_cutout_length,
        provider.settings.enclosure_periph_4p_cutout_length,
        provider.settings.enclosure_periph_4p_cutout_length,
        provider.settings.enclosure_periph_6p_cutout_length,
        provider.settings.enclosure_periph_6p_cutout_length,
    ]

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
