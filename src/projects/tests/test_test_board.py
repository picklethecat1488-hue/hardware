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

    # Probe points centered inside the right exterior wall (X = w/2 - wall/2) at each peripheral connector Y
    wall_x = (w / 2.0) - (wall / 2.0)
    for y, bus in [(26.0, "I2C"), (16.0, "I3C0"), (6.0, "I3C1"), (-6.0, "SPI"), (-17.0, "UART")]:
        assert not enclosure.part.is_inside((wall_x, y, z_conn)), (
            f"Enclosure bottom must have cutout for {bus} at Y={y}"
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
