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

    # Probe point centered inside the left exterior wall (X = -w/2 + wall/2) at J5 SWD connector Y=-7.0
    wall_x = (-w / 2.0) + (wall / 2.0)
    assert not enclosure.part.is_inside((wall_x, -7.0, z_conn)), (
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
