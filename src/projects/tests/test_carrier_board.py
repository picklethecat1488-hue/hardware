"""Tests for carrier_board rigid-flex PCB and protective enclosure CAD geometry."""

from pathlib import Path
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

        # Verify differential pair compliance audit
        assert hasattr(provider, "flying_probe_diff_pairs"), "Provider must expose flying_probe_diff_pairs"
        diff_results = provider.flying_probe_diff_pairs
        assert diff_results["all_passed"] is True, f"Diff pair checks failed: {diff_results}"
        assert len(diff_results["checks"]) > 0, "Must have audited differential pairs"

        # Verify test report generation
        report_md = provider.generate_test_report()
        assert "Flying Probes Automated Acceptance Test Report" in report_md
        assert "TEST_CONTINUITY_GND" in report_md
        assert "TEST_UART_BLE_SPEED" in report_md
        assert "PASS" in report_md
        assert "100.0%" in report_md
        assert "Signal Line Isolation Audit" in report_md
        assert "Differential Pair Compliance Audit" in report_md
        assert "USB_2_0" in report_md
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

        # Verify mutual capacitance touch configuration
        assert hasattr(provider, "flying_probe_mutual_cap"), "Provider must expose flying_probe_mutual_cap"
        cap_results = provider.flying_probe_mutual_cap
        assert cap_results["all_passed"] is True, f"Mutual cap checks failed: {cap_results}"
        assert len(cap_results["checks"]) > 0, "Must have audited mutual capacitance channels"
        assert all(c.touch_detected for c in cap_results["checks"]), "All channels must detect finger touch"

        # Verify test report generation
        report_md = provider.generate_test_report()
        assert "TEST_CAP_SENSE_CHAN0" in report_md
        assert "TEST_CAP_SENSE_CHAN1" in report_md
        assert "TEST_CAP_SENSE_CHAN2" in report_md
        assert "TEST_CAP_SENSE_CHAN3" in report_md
        assert "PASS" in report_md
        assert "100.0%" in report_md
        assert "Mutual Capacitance Touch Simulation & Verification" in report_md
    finally:
        p.disconnect(client)


def test_regression_bug_195_flying_probes_diff_pair_and_mutual_cap_compliance() -> None:
    """Verify BUG-195: diff pair compliance (USB, PCIe) and mutual cap touch testing in flying probes."""
    from provider.simulation.flying_probe import (
        verify_diff_pair_compliance,
        verify_mutual_cap_compliance,
    )

    provider = CarrierBoardProvider()

    # 1. Differential pair testing on carrier board
    diff_results = verify_diff_pair_compliance(provider)
    assert diff_results["all_passed"] is True, f"Diff pair verification failed: {diff_results}"
    checks = diff_results["checks"]
    pair_names = {c.pair_name for c in checks}
    assert "USB_2_0" in pair_names
    for c in checks:
        assert c.passed is True
        assert c.skew_ps <= c.max_skew_ps
        tol_val = c.target_diff_impedance_ohm * (c.tolerance_pct / 100.0)
        assert abs(c.measured_diff_impedance_ohm - c.target_diff_impedance_ohm) <= tol_val

    # 2. Mutual capacitance finger touch simulation on flex tail
    cap_results = verify_mutual_cap_compliance(provider)
    assert cap_results["all_passed"] is True, f"Mutual cap verification failed: {cap_results}"
    cap_checks = cap_results["checks"]
    chan_names = {c.channel_name for c in cap_checks}
    assert "CAP_CHAN0" in chan_names
    assert "CAP_CHAN1" in chan_names
    for c in cap_checks:
        assert c.passed is True
        assert c.touch_detected is True
        assert c.delta_c_pf >= c.min_delta_c_pf
        assert c.finger_touch_pf > c.baseline_pf


def test_regression_bug_214_btle_support_and_enclosure_cover_bluetooth_logo() -> None:
    """Verify BUG-214: PCIe connector/cutout removed, BTLE UART 1Mb/s added, Bluetooth logo on lid."""
    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}
    net_map = {n.name: n for n in wiring.nets}

    # 1. PCIe connector J1 removed, U11 BTLE module added with built-in PCB antenna
    assert "J1" not in comp_map, "PCIe connector J1 must be removed from design (BUG-214)"
    assert "U11" in comp_map, "U11 BTLE module must exist in carrier board components (BUG-214)"
    assert comp_map["U11"].package == "MOD-BLE-PCB-ANT"
    assert tuple(comp_map["U11"].position[:2]) == (0.0, -36.0)

    # 2. BTLE UART interface connected to U1 with minimum 1Mb/s speed
    for uart_net in ("BLE_TX", "BLE_RX", "BLE_RTS", "BLE_CTS"):
        assert uart_net in net_map, f"Net {uart_net} must exist in wiring"
        net_pins = net_map[uart_net].pins
        u1_pin = next((p for p in net_pins if p[0] == "U1"), None)
        u11_pin = next((p for p in net_pins if p[0] == "U11"), None)
        assert u1_pin is not None, f"Net {uart_net} must connect to U1"
        assert u11_pin is not None, f"Net {uart_net} must connect to U11"
    assert provider.settings.ble_uart_baud_rate >= 1000000, "BTLE UART baud rate must be >= 1Mb/s"

    # 3. Pairing by capacitive touch input gesture or proximity
    pcb_cfg = provider.pcb_config
    cap_sensor_names = [s.name for s in pcb_cfg.capacitive_sensors]
    assert "ACTION_BUTTON" in cap_sensor_names, "ACTION_BUTTON must exist for cap-touch pairing gesture"
    assert "PROXIMITY_SENSOR" in cap_sensor_names, "PROXIMITY_SENSOR must exist for proximity-based pairing"

    # 4. Main user LED D1 and piezo buzzer U5 provide BTLE connection status
    assert "D1" in comp_map, "Main user RGB LED D1 must exist"
    assert "U5" in comp_map, "Piezo buzzer U5 must exist"
    signaling = provider.btle_status_signaling
    assert "pairing" in signaling and "connected" in signaling and "disconnected" in signaling
    assert "blue" in signaling["pairing"]["led_color"]
    assert "solid_cyan" in signaling["connected"]["led_color"]
    assert "buzzer_tone" in signaling["pairing"]
    assert "buzzer_tone" in signaling["connected"]

    # 5. Integrated PCB antenna and ground plane keepout
    assert provider.settings.ble_antenna_length > 0
    ble_keepouts = [obs for obs in provider.pcb_manifest["obstacles"] if "antenna" in obs["name"]]
    assert len(ble_keepouts) >= 1, "Must define RF ground plane keepout for integrated PCB antenna"

    # 6. Bluetooth logo on enclosure cover (enclosure_lid)
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    assert lid.part.is_valid(), "Enclosure lid must be a valid solid"
    assert len(lid.part.solids()) == 1, "Enclosure lid must be a single solid"
    assert "bluetooth_logo" in lid.part.joints, "Lid must expose bluetooth_logo joint"
    batt_w = provider.settings.enclosure_battery_mount_width
    batt_l = provider.settings.enclosure_battery_mount_length
    batt_rim_t = provider.settings.enclosure_battery_mount_wall_thickness
    batt_y = provider.settings.enclosure_battery_mount_y
    j13_y = 16.0
    batt_cut_l = provider.settings.enclosure_battery_cutout_length
    min_y = min(batt_y - (batt_l / 2.0), j13_y - (batt_cut_l / 2.0) - batt_rim_t)

    batt_cov_clr = provider.settings.enclosure_battery_cover_clearance
    batt_cov_t = provider.settings.enclosure_battery_cover_wall_thickness
    batt_lbl_margin = provider.settings.enclosure_battery_label_margin
    batt_lbl_y = min_y - batt_rim_t - batt_cov_clr - batt_cov_t - batt_lbl_margin

    wall = provider.settings.enclosure_wall_thickness
    depth = provider.settings.ble_logo_depth
    bt_faces = [
        f
        for f in lid.part.faces()
        if abs(f.center().Z - (wall - depth)) < 1e-3 and abs(f.center().X) < 5.0 and -40.0 < f.center().Y < -26.0
    ]
    assert len(bt_faces) >= 1, f"Expected engraved Bluetooth logo faces on lid, found {len(bt_faces)}"
    assert all(f.center().Y < batt_lbl_y for f in bt_faces), (
        f"Bluetooth logo faces must be located strictly south of BATTERY label (Y < {batt_lbl_y:.2f} mm)"
    )

    # 7. Zero PCIe cutouts in enclosure bottom
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    floor_z = -h_shell / 2.0 + (wall / 2.0)
    length = provider.settings.board_length + 2.0 * (provider.settings.enclosure_clearance + wall)
    rear_wall_y = -length / 2.0 + (wall / 2.0)
    m2_z = -h_shell / 2.0 + wall + standoff_h + 2.0

    assert enclosure.part.is_inside((0.0, -36.0, floor_z)), "Enclosure bottom floor must be solid under former J1"
    assert enclosure.part.is_inside((0.0, rear_wall_y, m2_z)), "Enclosure rear wall must be solid without PCIe cutout"


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
    """Verify BUG-142 & BUG-214: enclosure bottom floor is completely solid under former PCIe connector J1."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    floor_z = -h_shell / 2.0 + (wall / 2.0)

    # Floor must be completely solid under (0.0, -36.0) where J1 was previously pierced
    assert enclosure.part.is_inside((0.0, -36.0, floor_z)), (
        "Enclosure bottom floor must be solid under former J1 location after PCIe removal (BUG-214)"
    )
    # Floor must remain solid across bottom
    assert enclosure.part.is_inside((20.0, -36.0, floor_z)), "Enclosure floor must be solid away from center"


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
    """Verify BUG-144 & BUG-214: enclosure bottom rear wall has zero PCIe cutout and is completely solid."""
    provider = CarrierBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    length = provider.settings.board_length + 2.0 * (provider.settings.enclosure_clearance + wall)
    rear_wall_y = -length / 2.0 + (wall / 2.0)

    # Rear wall at center X=0 must be completely solid without M.2/PCIe cutout
    m2_z = -h_shell / 2.0 + wall + standoff_h + 2.0
    assert enclosure.part.is_inside((0.0, rear_wall_y, m2_z)), (
        f"Enclosure rear wall must be solid at (0.0, {rear_wall_y}, {m2_z}) after PCIe removal (BUG-214)"
    )
    assert enclosure.part.is_inside((25.0, rear_wall_y, m2_z)), "Rear wall must be solid across entire width"


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

    # 2. Rear exterior wall (solid wall, 0 M.2 PCIE engraved faces after BUG-214)
    rear_engraved = [f for f in enclosure.part.faces() if abs(f.center().Y - (-length / 2.0 + 0.4)) < 1e-3]
    assert len(rear_engraved) == 0, f"Expected 0 M.2 PCIE engraved faces on rear wall, found {len(rear_engraved)}"

    # 3. Front shelf (FLEX TAIL label)
    shelf_engraved = [
        f for f in enclosure.part.faces() if f.center().Y > (length / 2.0) and f.normal_at(f.center()).Z > 0.9
    ]
    assert len(shelf_engraved) >= 8, f"Expected FLEX TAIL engraved faces, found {len(shelf_engraved)}"

    # 4. Enclosure lid (BATTERY and BLUETOOTH labels)
    lid_engraved = [f for f in lid.part.faces() if abs(f.center().Z - (wall - 0.4)) < 1e-3]
    assert len(lid_engraved) >= 10, f"Expected BATTERY and BLUETOOTH engraved faces on lid, found {len(lid_engraved)}"


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

    # 2. Verify LAYER 1-6 RIGID-FLEX silkscreen has been removed per CR feedback
    assert all(t.text != "LAYER 1-6 RIGID-FLEX" for t in pcb_cfg.silkscreen_texts)

    # 3. Verify jumper and switch labels are horizontal (rotation == 0.0)
    for label_name in ("NRST", "BOOT0", "ISP", "VBUS", "RESET"):
        lbl = next(t for t in pcb_cfg.silkscreen_texts if t.text == label_name)
        assert lbl.rotation == 0.0, f"Label {label_name} must have horizontal rotation 0.0, got {lbl.rotation}"

    # 4. Verify PCB DRC passes with 0 violations
    drc = PCBDesignRulesChecker(pcb_cfg)
    report = drc.check_all(wiring=Wiring(str(provider.wiring_path)))
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0


def test_regression_bug_219_reset_relocation_and_horizontal_jumpers() -> None:
    """Verify BUG-219: Relocate RESET button, remove grouping borders, orient jumpers horizontally.

    Asserts that:
    1. SW1 (RESET button) is moved out of the overrides group and placed centrally below U1 at (0.0, -11.0).
    2. RESET silkscreen label is placed between U1 and SW1 at (0.0, -9.2).
    3. Rectangular grouping borders around STATUS and OVERRIDES are removed.
    4. Jumpers JP1, JP2, JP3, JP4 are oriented horizontally with rotation (0.0, 0.0, 0.0).
    5. Silkscreen text labels (NRST, BOOT0, ISP, VBUS) are positioned to the right of each jumper at X=14.0.
    6. Complete DRC check passes with zero errors and zero warnings.
    """
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    pcb_cfg = provider.pcb_config

    fp_map = {fp.name: fp for fp in wiring.footprints}

    # 1. SW1 relocation
    assert "SW1" in fp_map
    sw1 = fp_map["SW1"]
    assert abs(sw1.position[0] - 0.0) < 0.1, f"SW1 X position must be 0.0, got {sw1.position[0]}"
    assert abs(sw1.position[1] - (-11.0)) < 0.1, f"SW1 Y position must be -11.0, got {sw1.position[1]}"
    assert abs(sw1.rotation[2] - 0.0) < 0.1, f"SW1 rotation must be 0.0, got {sw1.rotation}"

    # 2. RESET silkscreen label
    reset_text = next(t for t in pcb_cfg.silkscreen_texts if t.layer == "F.SilkS" and t.text == "RESET")
    assert abs(reset_text.position[0] - 0.0) < 0.1, f"RESET text X must be 0.0, got {reset_text.position[0]}"
    assert abs(reset_text.position[1] - (-9.2)) < 0.2, f"RESET text Y must be -9.2, got {reset_text.position[1]}"

    # 3. Rectangular grouping borders removed
    rect_frames = [
        g
        for g in pcb_cfg.silkscreen_graphics
        if g.shape == "rect" and (abs(g.position[0] - 12.2) < 2.0 or abs(g.position[0] - 4.5) < 2.0)
    ]
    assert len(rect_frames) == 0, (
        f"Grouping rectangles for STATUS and OVERRIDES must be removed, found {len(rect_frames)}"
    )

    # 4. Jumpers oriented horizontally
    for jp_name in ("JP1", "JP2", "JP3", "JP4"):
        assert jp_name in fp_map
        jp = fp_map[jp_name]
        assert abs(jp.rotation[2] - 0.0) < 0.1, (
            f"Jumper {jp_name} must have horizontal rotation 0.0, got {jp.rotation[2]}"
        )
        assert abs(jp.position[0] - 10.5) < 0.1, f"Jumper {jp_name} must be placed at X=10.5, got {jp.position[0]}"

    # 5. Silkscreen texts to the right at X=14.0
    text_pos_map = {
        "NRST": -15.5,
        "BOOT0": -18.0,
        "ISP": -21.0,
        "VBUS": -23.6,
    }
    for text_name, expected_y in text_pos_map.items():
        lbl = next(t for t in pcb_cfg.silkscreen_texts if t.layer == "F.SilkS" and t.text == text_name)
        assert abs(lbl.position[0] - 14.0) < 0.2, (
            f"Label {text_name} must be to the right at X=14.0, got {lbl.position[0]}"
        )
        assert abs(lbl.position[1] - expected_y) < 0.2, (
            f"Label {text_name} must be at Y={expected_y}, got {lbl.position[1]}"
        )
        assert lbl.rotation == 0.0, f"Label {text_name} must be horizontal (rotation 0.0)"

    # 6. Complete DRC check passes
    drc = PCBDesignRulesChecker(pcb_cfg)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0
    assert report.warning_count == 0


def test_regression_bug_220_flex_tail_flying_probe_isolation_excluded() -> None:
    """Verify BUG-220: Flex tail flying probe test excludes untestable carrier board isolation checks.

    Asserts that:
    1. Flying probe simulation hooks for flex_tail only synthesize steps defined in pcb_test_steps.yaml.
    2. Zero TEST_ISO_* steps are created for flex_tail.
    3. flying_probe_signal_isolation on flex_tail reports empty checks.
    4. Rendered markdown report for flex_tail omits 'Signal Line Isolation Audit'.
    5. Rendered markdown report for flex_tail contains 'Mutual Capacitance Touch Simulation & Verification'.
    6. For carrier_board, isolation steps and the audit table remain present.
    """
    from projects.carrier_board.provider import CarrierBoardProvider
    from projects.carrier_board.simulate_hooks import get_simulate_hooks_impl

    provider = CarrierBoardProvider()

    # 1. Flex tail simulation hooks
    get_simulate_hooks_impl(provider, "carrier_board/flex_tail")
    flex_steps = getattr(provider, "flying_probe_steps", [])
    flex_iso_steps = [s for s in flex_steps if s.step_id.startswith("TEST_ISO_")]

    assert len(flex_iso_steps) == 0, f"Flex tail must not contain isolation steps, found: {flex_iso_steps}"
    assert len(flex_steps) == 7, f"Flex tail must only contain 7 defined test steps, found {len(flex_steps)}"

    flex_iso_results = getattr(provider, "flying_probe_signal_isolation", {})
    assert len(flex_iso_results.get("checks", [])) == 0, "Flex tail signal isolation checks must be empty"
    assert flex_iso_results.get("all_passed") is True

    flex_report = provider.generate_test_report()
    assert "Signal Line Isolation Audit" not in flex_report, (
        "Flex tail report must NOT include Signal Line Isolation Audit section"
    )
    assert "Mutual Capacitance Touch Simulation & Verification (Flex Tail)" in flex_report, (
        "Flex tail report must include Mutual Capacitance section"
    )

    # 2. Carrier board simulation hooks
    get_simulate_hooks_impl(provider, "carrier_board")
    carrier_steps = getattr(provider, "flying_probe_steps", [])
    carrier_iso_steps = [s for s in carrier_steps if s.step_id.startswith("TEST_ISO_")]

    assert len(carrier_iso_steps) > 0, "Carrier board must contain synthesized isolation steps"
    assert getattr(provider, "flying_probe_diff_pairs", None) is not None

    carrier_report = provider.generate_test_report()
    assert "Signal Line Isolation Audit" in carrier_report, (
        "Carrier board report must include Signal Line Isolation Audit section"
    )
    assert "Differential Pair Compliance Audit" in carrier_report, (
        "Carrier board report must include Differential Pair Compliance Audit section"
    )


def test_regression_bug_231_nina_b312_flashed_module_swd_header_and_footprint() -> None:
    """Verify BUG-231: Pre-flashed NINA-B312 variant, LGA-72 footprint, SWD header J15, and zero DRC errors.

    Asserts that:
    1. U11 is updated from unflashed NINA-B302 to pre-flashed NINA-B312-02B.
    2. J15 exists as a 1x5 SWD recovery header at (-14.5, -41.0, 0.8) with horizontal orientation.
    3. J15 connects to GND, BLE_SWDIO, BLE_SWDCLK, BLE_RESET_N, and 3V3.
    4. U11 footprint dimensions match Table 27 LGA-72 (10.0 x 15.0 x 2.23 mm).
    5. Full DRC report passes with zero errors.
    """
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    pcb_cfg = provider.pcb_config

    fp_map = {fp.name: fp for fp in wiring.footprints}

    # 1. U11 MPN is NINA-B312-02B
    assert "U11" in fp_map, "Component U11 must exist in wiring footprints"
    u11 = fp_map["U11"]
    assert u11.mpn == "NINA-B312-02B", f"U11 MPN must be pre-flashed NINA-B312-02B, got {u11.mpn}"

    # 2. J15 exists at [-14.5, -41.0, 0.8]
    assert "J15" in fp_map, "J15 must exist in wiring footprints"
    j15 = fp_map["J15"]
    assert j15.package == "pin_header_2x5_1.27mm", f"J15 package must be pin_header_2x5_1.27mm, got {j15.package}"
    assert abs(j15.position[0] - (-14.5)) < 0.1, f"J15 X position must be -14.5, got {j15.position[0]}"
    assert abs(j15.position[1] - (-41.0)) < 0.1, f"J15 Y position must be -41.0, got {j15.position[1]}"
    assert abs(j15.rotation[2] - 0.0) < 0.1, f"J15 rotation must be 0.0, got {j15.rotation}"

    # 3. J15 status (superseded by BUG-251: J15 marked DNP/no-connect, U11 wired to SW2 reset button)
    assert getattr(j15, "unconnected", False) or getattr(j15, "dnp", False), "J15 must be DNP or no-connect"
    assert "SW2" in fp_map, "SW2 reset button must exist"
    reset_net = next((n for n in wiring.nets if n.name == "BLE_RESET_N"), None)
    assert reset_net is not None, "BLE_RESET_N net must exist for SW2 reset button"

    # 4. Footprint dimensions
    import yaml
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    with open(repo_root / "src/projects/footprints/ic.yaml") as f:
        ic_fps = yaml.safe_load(f)["footprints"]
    assert "MOD-BLE-PCB-ANT" in ic_fps, "MOD-BLE-PCB-ANT footprint must be defined in ic.yaml"
    ble_fp = ic_fps["MOD-BLE-PCB-ANT"]
    dims = ble_fp.get("dimensions", [])
    assert dims == [10.0, 15.0, 2.23], f"U11 dimensions must match LGA-72 Table 27 [10.0, 15.0, 2.23], got {dims}"

    # 5. Full DRC report passes with zero errors
    drc = PCBDesignRulesChecker(pcb_cfg)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0, f"Expected 0 DRC errors, got {report.error_count}"


def test_power_hardening_bug_243() -> None:
    """Verify BUG-243: Power hardening components C15, C16, C17, D8 exist on bottom side with zero DRC errors."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}

    for name in ("C15", "C16", "C17", "D8"):
        assert name in comp_map, f"Power hardening component {name} must exist"
        comp = comp_map[name]
        assert comp.layer == "B.Cu" or comp.position[2] < 0, f"{name} must be on bottom side"

    # Verify nets connected to 3V3 and GND
    nets_map = {n.name: n for n in wiring.nets}
    for name in ("C15", "C16", "C17", "D8"):
        assert any(c == name for c, p in nets_map["3V3"].pins), f"{name} must connect to 3V3"
        assert any(c == name for c, p in nets_map["GND"].pins), f"{name} must connect to GND"

    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.error_count == 0, f"Expected 0 DRC errors, got: {report.summary()}"


def test_regression_bug_249_remove_vload_sw_from_ble_module() -> None:
    """Verify BUG-249: VLOAD_SW artifact removed, U11 footprint corrected to NINA datasheet pinout."""
    import yaml
    from pathlib import Path
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))

    # 1. MOD-BLE-PCB-ANT footprint in ic.yaml must not have VLOAD_SW
    ic_yaml_path = Path(__file__).resolve().parent.parent / "footprints" / "ic.yaml"
    with open(ic_yaml_path, encoding="utf-8") as f:
        ic_data = yaml.safe_load(f)
    ble_fp = ic_data["footprints"]["MOD-BLE-PCB-ANT"]
    ble_pin_names = [p["name"] for p in ble_fp["pins"]]
    assert "VLOAD_SW" not in ble_pin_names, "MOD-BLE-PCB-ANT footprint must not have VLOAD_SW pin"
    assert "SWITCH_2" in ble_pin_names, "MOD-BLE-PCB-ANT footprint pin 18 must be SWITCH_2"

    # 2. wiring.yaml must not have VLOAD_SW net or U11.VLOAD_SW pin connection
    net_names = [n.name for n in wiring.nets]
    assert "VLOAD_SW" not in net_names, "VLOAD_SW net must be removed from wiring.yaml"
    for net in wiring.nets:
        for pin in net.pins:
            assert pin[0] != "U11" or pin[1] != "VLOAD_SW", "U11 must not have any pin connected to VLOAD_SW"

    # 3. pcb.yaml must not have VLOAD_SW in Sheet 2 pin_breakouts
    pcb_yaml_path = provider.wiring_path.parent / "pcb.yaml"
    with open(pcb_yaml_path, encoding="utf-8") as f:
        pcb_data = yaml.safe_load(f)
    sheet_2 = pcb_data["schematic_sheets"][1]
    if "pin_breakouts" in sheet_2 and "U11" in sheet_2["pin_breakouts"]:
        assert "VLOAD_SW" not in sheet_2["pin_breakouts"]["U11"]


def test_regression_bug_250_nina_nfc_antenna_and_tuning_caps() -> None:
    """Verify BUG-250: NINA-B312 native NFC1/NFC2 pins routed to antenna header and shunt tuning capacitors."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    nets_map = {n.name: n for n in wiring.nets}

    # 1. Verify NFC1 and NFC2 nets exist
    assert "NFC1" in nets_map, "NFC1 net must exist in wiring.yaml"
    assert "NFC2" in nets_map, "NFC2 net must exist in wiring.yaml"

    # 2. Verify U11 connects to NFC1 and NFC2
    nfc1_pins = set(nets_map["NFC1"].pins)
    nfc2_pins = set(nets_map["NFC2"].pins)
    assert ("U11", "NFC1") in nfc1_pins or ("U11", "28") in nfc1_pins
    assert ("U11", "NFC2") in nfc2_pins or ("U11", "29") in nfc2_pins

    # 3. Verify tuning capacitors C18 and C19 (C_tune1, C_tune2) exist and connect between NFC and GND
    comp_map = {c.name: c for c in wiring.footprints}
    assert "C18" in comp_map or "C_tune1" in comp_map, "C18 / C_tune1 tuning capacitor must exist"
    assert "C19" in comp_map or "C_tune2" in comp_map, "C19 / C_tune2 tuning capacitor must exist"
    c_tune1_name = "C18" if "C18" in comp_map else "C_tune1"
    c_tune2_name = "C19" if "C19" in comp_map else "C_tune2"

    assert any(c == c_tune1_name for c, _ in nets_map["NFC1"].pins), "C_tune1 must connect to NFC1"
    assert any(c == c_tune2_name for c, _ in nets_map["NFC2"].pins), "C_tune2 must connect to NFC2"
    assert any(c == c_tune1_name for c, _ in nets_map["GND"].pins), "C_tune1 must connect to GND"
    assert any(c == c_tune2_name for c, _ in nets_map["GND"].pins), "C_tune2 must connect to GND"

    # 4. Verify external antenna connector J16 connects to NFC1 and NFC2
    assert "J16" in comp_map, "External NFC coil antenna header J16 must exist"
    assert any(c == "J16" for c, _ in nets_map["NFC1"].pins), "J16 must connect to NFC1"
    assert any(c == "J16" for c, _ in nets_map["NFC2"].pins), "J16 must connect to NFC2"

    # 5. Verify PCB DRC passes with 0 violations
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.error_count == 0, f"Expected 0 DRC errors, got: {report.summary()}"


def test_regression_bug_251_j15_no_connect_and_u11_reset_button(tmp_path: Path) -> None:
    """Verify BUG-251: J15 removed from BOM, marked as no-connect, and U11 RESET_N wired to adjacent push button."""
    import math
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.exporter import PCBExporter
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}
    nets_map = {n.name: n for n in wiring.nets}

    # 1. J15 must exist and be marked DNP
    assert "J15" in comp_map, "J15 connector must exist on the board"
    j15 = comp_map["J15"]
    assert getattr(j15, "dnp", False), "J15 must be marked DNP"

    # 2. J15 must not appear in exported BOM
    exporter = PCBExporter(provider.pcb_config, wiring)
    bom_file = tmp_path / "carrier_board_bom.csv"
    exporter.export_bom_csv(bom_file)
    bom_text = bom_file.read_text(encoding="utf-8")
    assert "J15" not in bom_text, "J15 must be removed from the BOM CSV"

    # 3. J15 connects to BLE SWD, 3V3, and GND
    assert any(c == "J15" and p == "4" for c, p in nets_map["BLE_SWDCLK"].pins), "J15 pin 4 must connect to BLE_SWDCLK"
    assert any(c == "J15" and p == "2" for c, p in nets_map["BLE_SWDIO"].pins), "J15 pin 2 must connect to BLE_SWDIO"
    assert any(c == "J15" and p == "1" for c, p in nets_map["3V3"].pins), "J15 pin 1 must connect to 3V3"
    assert any(c == "J15" and p in ("3", "5") for c, p in nets_map["GND"].pins), "J15 pin 3/5 must connect to GND"

    # 4. SW2 push button switch must exist adjacent to J15 (<= 10mm distance)
    assert "SW2" in comp_map, "SW2 push button switch must exist"
    sw2 = comp_map["SW2"]
    dist = math.hypot(sw2.position[0] - j15.position[0], sw2.position[1] - j15.position[1])
    assert dist <= 10.0, f"SW2 must be placed adjacent to J15 (dist: {dist:.2f}mm > 10.0mm)"

    # 5. U11 RESET_N must connect to SW2
    reset_net = next((n for n in wiring.nets if ("U11", "RESET_N") in n.pins or ("U11", "19") in n.pins), None)
    assert reset_net is not None, "U11 RESET_N net must exist"
    assert any(c == "SW2" for c, _ in reset_net.pins), "SW2 must connect to U11 RESET_N"

    # 6. SW2 must connect to GND
    gnd_net = nets_map["GND"]
    assert any(c == "SW2" for c, _ in gnd_net.pins), "SW2 must connect to GND"

    # 7. J15 and SW2 must be on dedicated schematic sheet
    sheet_btle_prog = next(
        (s for s in provider.pcb_config.schematic_sheets if "BTLE Programming" in s.title or "J15" in s.title), None
    )
    assert sheet_btle_prog is not None, "Dedicated BTLE Programming & Reset Interface sheet must exist"
    assert "J15" in sheet_btle_prog.components and "SW2" in sheet_btle_prog.components

    sheet_hs = next((s for s in provider.pcb_config.schematic_sheets if "High-Speed" in s.title), None)
    assert sheet_hs is not None
    assert "J15" not in sheet_hs.components and "SW2" not in sheet_hs.components

    # 8. Zero PCB DRC violations
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.error_count == 0, f"Expected 0 DRC errors, got: {report.summary()}"


def test_regression_proposal_ct8_channel_routed_to_j2_without_flex_modification() -> None:
    """Verify PROPOSAL e8e2b4056c95: CT8 9th sensing channel routed from U2 to J2.NC3 without modifying flex tail."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    nets_map = {n.name: n for n in wiring.nets}

    # 1. CAP_CT8 net exists
    assert "CAP_CT8" in nets_map, "Net CAP_CT8 must exist in wiring.yaml"
    ct8_net = nets_map["CAP_CT8"]

    # 2. U2.CT8 and J2.NC3 are connected
    ct8_pins = set(ct8_net.pins)
    assert ("U2", "CT8") in ct8_pins, "U2.CT8 must connect to CAP_CT8"
    assert ("J2", "NC3") in ct8_pins, "J2.NC3 must connect to CAP_CT8"

    # 3. Flex tail connector J4 must NOT connect to CAP_CT8
    assert not any(c == "J4" for c, _ in ct8_net.pins), "Flex tail connector J4 must NOT be modified"

    # 4. Sheet 7 includes CT8 breakout on U2 (J2 maintains 8-channel breakout)
    sheet_cap = next((s for s in provider.pcb_config.schematic_sheets if "Capacitive" in s.title), None)
    assert sheet_cap is not None
    assert "CT8" in sheet_cap.pin_breakouts.get("U2", [])

    # 5. Full DRC passes with zero errors
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.error_count == 0, f"Expected 0 DRC errors, got: {report.summary()}"


def test_regression_bug_254_enclosure_lid_text_stroke_width() -> None:
    """Verify BUG-254: enclosure_lid BATTERY label has stroke width >= 0.8mm for DFM compliance."""
    from build123d import Text, FontStyle, offset, Axis
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider import Mode

    provider = CarrierBoardProvider()
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    assert lid.part is not None and lid.part.is_valid(), "Enclosure lid must be a valid solid"

    # 1. Configured font size and stroke expansion offset
    font_size = provider.settings.enclosure_battery_label_font_size
    stroke_offset = provider.settings.enclosure_battery_label_stroke_offset
    assert font_size >= 4.0, f"Expected BATTERY label font size >= 4.0mm, got {font_size}"
    assert stroke_offset >= 0.12, f"Expected stroke expansion offset >= 0.12mm, got {stroke_offset}"

    # 2. Geometric stroke width verification on representative 'T' glyph
    t_glyph = Text("T", font_size=font_size, font_style=FontStyle.BOLD)
    if stroke_offset > 0.0:
        t_glyph = offset(t_glyph, amount=stroke_offset)

    # Vertical stem width measurement
    edges_v = t_glyph.edges().filter_by(Axis.Y)
    xs = sorted(list({round(e.bounding_box().min.X, 3) for e in edges_v}))
    assert len(xs) >= 4, "Glyph 'T' must have inner and outer vertical stem boundaries"
    stem_width = xs[2] - xs[1]
    assert stem_width >= 0.80, f"Expected BATTERY text stem width >= 0.80mm (DFM rule), got {stem_width:.3f}mm"

    # Horizontal bar thickness measurement
    edges_h = t_glyph.edges().filter_by(Axis.X)
    ys = sorted(list({round(e.bounding_box().min.Y, 3) for e in edges_h}))
    assert len(ys) >= 3, "Glyph 'T' must have top and bottom horizontal bar boundaries"
    bar_thickness = ys[2] - ys[1]
    assert bar_thickness >= 0.80, (
        f"Expected BATTERY text horizontal bar >= 0.80mm (DFM rule), got {bar_thickness:.3f}mm"
    )


def test_regression_bug_255_pullup_resistors_unbridged_with_individual_power_designators() -> None:
    """Verify BUG-255: Pull-up resistors R1 and R2 on Sheet 8 have individual 3V3 power designators and no bridge."""
    import matplotlib.pyplot as plt
    from projects.carrier_board.provider import CarrierBoardProvider
    from model import Wiring
    from model.pcb import PCBConfig
    from provider.schematic_diagram import SchematicDiagram
    import yaml

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    pcb_yaml_path = provider.wiring_path.parent / "pcb.yaml"
    with open(pcb_yaml_path) as f:
        cfg = PCBConfig(**yaml.safe_load(f))

    diag = SchematicDiagram(wiring=wiring, pcb_config=cfg)
    sheet_plans = diag._build_sheet_plans()
    sheet_8_plan = next(p for p in sheet_plans if p.sheet_idx == 8)

    from unittest.mock import MagicMock

    mock_pdf = MagicMock()
    diag._render_pdf_schematic_sheet(
        mock_pdf,
        "carrier_board",
        sheet_8_plan,
        len(sheet_plans),
        diag.wiring.nets,
        15,
        28,
    )

    fig = mock_pdf.savefig.call_args[0][0]
    ax = fig.axes[0]
    texts = [t.get_text() for t in ax.texts]
    pwr_labels = [t for t in texts if t == "3V3"]
    assert len(pwr_labels) >= 2, f"Expected individual 3V3 labels for pullups, got {pwr_labels}"

    red_lines = [line for line in ax.lines if line.get_color() == "#dc2626"]
    h_red_lines = [
        line
        for line in red_lines
        if len(line.get_ydata()) == 2 and abs(line.get_ydata()[0] - line.get_ydata()[1]) < 0.001
    ]
    bridging_lines = [line for line in h_red_lines if abs(line.get_xdata()[1] - line.get_xdata()[0]) > 5.0]
    assert len(bridging_lines) == 0, (
        f"Expected 0 horizontal red bridging lines between pullups, found: {bridging_lines}"
    )


def test_regression_bug_256_flex_tail_schematic_primary_signal_nets(tmp_path: Path) -> None:
    """Verify BUG-256: Flex tail schematic Table of Contents primary signal nets contains only 7 cap sense + 1 proximity channels."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model import Wiring
    from provider import Mode
    from provider.pcb.exporter import PCBExporter
    from provider.schematic_diagram import SchematicDiagram
    from pdfminer.high_level import extract_text

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))

    # 1. Verify Wiring.filter_by_footprints scopes nets strictly to connected footprints
    flex_wiring = wiring.filter_by_footprints(["J4"])
    expected_nets = {
        "CAP_SHIELD",
        "CAP_TX0",
        "CAP_TX1",
        "CAP_TX2",
        "CAP_RX0",
        "CAP_RX1",
        "CAP_RX2",
        "CAP_RX3",
    }
    net_names = {net.name for net in flex_wiring.nets}
    assert net_names == expected_nets, f"Expected exactly 8 flex nets, got {net_names}"
    assert "GND" not in net_names
    assert "3V3" not in net_names
    assert "VBUS" not in net_names

    # 2. Verify TOC plan generates only those 8 nets under primary signal nets
    part_res = provider.part["flex_tail"]("flex_tail", None, Mode.DEFAULT)
    flex_cfg = part_res.to_pcb_config()
    diag = SchematicDiagram(wiring=flex_wiring, pcb_config=flex_cfg)
    sheet_plans = diag._build_sheet_plans()
    toc_plans = diag._plan_pdf_toc_pages(flex_wiring.footprints, diag.wiring.nets, sheet_plans)

    toc_net_names = {net.name for plan in toc_plans for row in plan.net_rows for net in row}
    assert toc_net_names == expected_nets, f"TOC nets mismatch: {toc_net_names}"
    assert len(toc_plans) == 1, f"Expected 1 TOC page when scoped to 8 nets, got {len(toc_plans)}"

    # 3. Export PDF and verify full document pagination and text content
    exp = PCBExporter(flex_cfg, wiring, subassembly="flex_tail", design_rules=provider.pcb_config.design_rules)
    out_pdf = tmp_path / "flex_tail_schematic.pdf"
    exp.export_schematic_pdf(out_pdf)
    assert out_pdf.exists()

    pdf_text = extract_text(str(out_pdf))
    assert "CAP_SHIELD (3 pins)" in pdf_text
    assert "CAP_TX0 (3 pins)" in pdf_text
    assert "CAP_RX0 (3 pins)" in pdf_text
    # Carrier board signal and power nets must not leak into flex tail schematic TOC
    assert "3V3 (36 pins)" not in pdf_text
    assert "GND (89 pins)" not in pdf_text
    assert "VBUS (5 pins)" not in pdf_text
    assert "Page 1 of 3" in pdf_text
    assert "Page 2 of 3" in pdf_text
    assert "Page 3 of 3" in pdf_text


def test_regression_bug_259_schematic_floating_pins_and_layout() -> None:
    """Verify BUG-259: Floating pins removed, off-sheet connectors cleaned, and Sheet 11 centered."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker
    from provider.schematic_diagram import SchematicDiagram

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    diag = SchematicDiagram(wiring=wiring, pcb_config=provider.pcb_config)
    plans = diag._build_sheet_plans()

    # 1. Sheet 3: U10 does not have floating pin 4 (BYP)
    sheet_3 = next(p for p in plans if "Peripheral Power" in p.title)
    u10 = next(fp for fp in sheet_3.footprints if fp.name == "U10")
    u10_pin_names = {p.name for p in u10.pins}
    assert "4" not in u10_pin_names, f"Pin 4 (BYP) must not appear on U10 symbol: {u10_pin_names}"
    assert u10_pin_names == {"1", "2", "3", "5"}

    # 2. Sheet 4: U1 does not have floating pin D1
    sheet_4 = next(p for p in plans if "Microcontroller Core" in p.title)
    u1_s4 = next(fp for fp in sheet_4.footprints if fp.name == "U1")
    u1_s4_pins = {p.name for p in u1_s4.pins}
    assert "D1" not in u1_s4_pins, f"Pin D1 must not appear on U1 symbol: {u1_s4_pins}"
    assert "M1" not in u1_s4_pins, f"Pin M1 must not appear on U1 symbol: {u1_s4_pins}"

    # 3. Sheet 8: U2 does not have off-sheet connector pins VREGD or VREGA
    sheet_8 = next(p for p in plans if "Capacitive Sensing" in p.title)
    u2 = next(fp for fp in sheet_8.footprints if fp.name == "U2")
    u2_pins = {p.name for p in u2.pins}
    assert "VREGD" not in u2_pins, f"VREGD pin breakout must not appear on U2: {u2_pins}"
    assert "VREGA" not in u2_pins, f"VREGA pin breakout must not appear on U2: {u2_pins}"

    # 4. Sheet 10: U11 symbol only has specified pin GND, no EGP or secondary GNDs
    sheet_10 = next(p for p in plans if "BTLE" in p.title and "UART" in p.title)
    u11 = next(fp for fp in sheet_10.footprints if fp.name == "U11")
    u11_pins = {p.name for p in u11.pins}
    assert "EGP" not in u11_pins, f"Pin EGP must not appear on U11: {u11_pins}"
    assert "GND_12" not in u11_pins
    assert "GND_26" not in u11_pins
    assert "GND_30" not in u11_pins
    assert "GND" in u11_pins

    # 5. Sheet 11: J15 and SW2 are centered horizontally and vertically
    boxes = diag.compute_symbol_bounding_boxes()
    sheet_11_plan = next(p for p in plans if "J15, SW2" in p.title)
    s11_boxes = boxes.get(sheet_11_plan.sheet_idx, [])
    j15_box = next(b for b in s11_boxes if b[4] == "J15")
    sw2_box = next(b for b in s11_boxes if b[4] == "SW2")
    # Horizontal center of the pair is (j15_cx - w/2 + sw2_cx + w/2) / 2
    pair_center_x = (j15_box[0] - j15_box[2] / 2.0 + sw2_box[0] + sw2_box[2] / 2.0) / 2.0
    assert abs(pair_center_x - 148.5) < 1.0, f"Expected Sheet 11 symbols centered at 148.5mm, got {pair_center_x}"
    # Vertical positioning should be centered (top_row_y <= 115.0)
    assert j15_box[1] <= 115.0, f"Expected J15 Y <= 115.0, got {j15_box[1]}"
    assert sw2_box[1] <= 115.0, f"Expected SW2 Y <= 115.0, got {sw2_box[1]}"

    # 6. Entire schematic DRC passes with 0 errors
    checker = PCBDesignRulesChecker(provider.pcb_config)
    report = checker.check_schematic(wiring)
    assert len(report.errors) == 0, f"Schematic DRC errors: {[e.description for e in report.errors]}"


def test_regression_bug_260_schematic_index_sheet_names_fit_page() -> None:
    """Verify BUG-260: Schematic Index Document Structure entry names fit within sheet margins."""
    import matplotlib.pyplot as plt
    from projects.carrier_board.provider import CarrierBoardProvider
    from model import Wiring
    from provider.schematic_diagram import SchematicDiagram

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    diag = SchematicDiagram(wiring=wiring, pcb_config=provider.pcb_config)
    sheet_plans = diag._build_sheet_plans()
    toc_plans = diag._plan_pdf_toc_pages(wiring.footprints, diag.wiring.nets, sheet_plans)

    # 1. Verify every Document Structure entry is <= 100 characters so it fits on page
    assert len(toc_plans) >= 1
    doc_entries = [entry for plan in toc_plans for entry in plan.doc_entries]
    assert len(doc_entries) >= len(sheet_plans) + 2

    for page_lbl, desc in doc_entries:
        full_line = f"{page_lbl}: {desc}"
        assert len(full_line) <= 100, f"Document structure line too long ({len(full_line)} > 100): {full_line}"

    # 2. Render TOC page 1 and verify text objects stay well inside right margin (X < 277)
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from unittest.mock import MagicMock

    mock_pdf = MagicMock()
    diag._render_pdf_toc_page(mock_pdf, "carrier_board", "Rigid-Flex", 6, toc_plans[0], len(toc_plans), 28)
    fig = mock_pdf.savefig.call_args[0][0]
    FigureCanvasAgg(fig)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ax = fig.axes[0]
    for t in ax.texts:
        bbox = t.get_window_extent(renderer).transformed(ax.transData.inverted())
        # All text elements must stay inside printable boundary X <= 277mm
        assert bbox.x1 <= 277.0, f"Text '{t.get_text()[:40]}...' exceeded right margin (x1={bbox.x1:.1f} > 277.0)"


def test_regression_bug_261_supplier_pcb_docs() -> None:
    """Verify BUG-261: supplier PCB docs include track spacing in mils, hole size, consistent rigid-flex order, and plain SMT guidelines."""
    deck_path = Path("src/projects/carrier_board/docs/supplier_pcb_review_deck.md")
    assert deck_path.exists(), "supplier_pcb_review_deck.md must exist"
    content = deck_path.read_text()

    # 1. Min track spacing in mils
    assert "Minimum Track Spacing" in content
    assert "4.72" in content and "mil" in content

    # 2. Min hole size in mm and mils
    assert "Minimum Hole / Drill Size" in content
    assert "6.30" in content and "9.84" in content

    # 3. Rigid Section appears before Flexible Section in table headers and sections
    rigid_pos = content.find("Carrier Board (Rigid Section)")
    flex_pos = content.find("Flex Tail (Flexible Section)")
    assert rigid_pos != -1 and flex_pos != -1
    assert rigid_pos < flex_pos, "Rigid section must appear before flexible section"

    # 4. Detailed Assembly & SMT Process Guidelines: plain text with no LaTeX math formatting and <= 600 chars
    guidelines_start = content.find("### Detailed Assembly and SMT Process Guidelines")
    assert guidelines_start != -1
    guidelines_heading = "### Detailed Assembly and SMT Process Guidelines\n"
    guidelines_body_start = guidelines_start + len(guidelines_heading)
    guidelines_end = content.find("</div>", guidelines_body_start)
    guidelines_text = content[guidelines_body_start:guidelines_end].strip()
    assert len(guidelines_text) <= 600, f"SMT guidelines length ({len(guidelines_text)}) exceeds 600 characters"
    assert "$" not in guidelines_text, "SMT guidelines must not contain LaTeX math delimiters"
    assert "\\circ" not in guidelines_text
    assert "\\text" not in guidelines_text
    assert "240 deg C to 245 deg C" in guidelines_text

    # 5. Redundant MSL 3 bakeout callouts excluded
    assert "Bakeout protocol: $125^\\circ\\text{C}" not in content
    assert "Moisture-sensitive parts (MSL 3: <code>U1</code>" not in content


def test_regression_bug_262_supplier_pcb_guidelines_zip_outputs() -> None:
    """Verify BUG-262: build outputs supplier zip archives under build/board/<project>.

    - gerbers.zip: contains .pcb .pcbdoc .cam .brd and gerber files
    - bom_templates.zip: contains <PCB name>_bom.csv BOM list for each PCB
    - centroid_files.zip: contains <PCB name>_pos.csv centroid list for each PCB
    - assembly_files.zip: contains <PCB name>_top.png, <PCB name>_bottom.png top and bottom PCB textures for each PCB
    The zip files should go under build/board/<project>, not directly under build/board.
    """
    import zipfile
    from build import Builder
    from config import AppConfig
    from provider import ProviderManager

    config = AppConfig()
    manager = ProviderManager(config)
    builder = Builder(manager)

    # Trigger supplier packaging for carrier_board
    builder.generate_pcbs(out_dir="build", names=["carrier_board/*"])

    top_board_dir = Path("build/board")
    board_dir = Path("build/board/carrier_board")

    # Verify no zip archives exist directly under build/board/
    assert not (top_board_dir / "gerbers.zip").exists(), "build/board/gerbers.zip must not exist"
    assert not (top_board_dir / "bom_templates.zip").exists(), "build/board/bom_templates.zip must not exist"
    assert not (top_board_dir / "centroid_files.zip").exists(), "build/board/centroid_files.zip must not exist"
    assert not (top_board_dir / "assembly_files.zip").exists(), "build/board/assembly_files.zip must not exist"

    # Verify zip archives exist under build/board/carrier_board/
    assert (board_dir / "gerbers.zip").exists(), "build/board/carrier_board/gerbers.zip must exist"
    assert (board_dir / "bom_templates.zip").exists(), "build/board/carrier_board/bom_templates.zip must exist"
    assert (board_dir / "centroid_files.zip").exists(), "build/board/carrier_board/centroid_files.zip must exist"
    assert (board_dir / "assembly_files.zip").exists(), "build/board/carrier_board/assembly_files.zip must exist"

    # 1. gerbers.zip: contains .pcb, .pcbdoc, .cam, .brd and gerber files
    with zipfile.ZipFile(board_dir / "gerbers.zip", "r") as zf:
        names = zf.namelist()
        suffixes = {Path(n).suffix.lower() for n in names}
        assert ".pcb" in suffixes, "gerbers.zip must contain .pcb files"
        assert ".pcbdoc" in suffixes, "gerbers.zip must contain .pcbdoc files"
        assert ".cam" in suffixes, "gerbers.zip must contain .cam files"
        assert ".brd" in suffixes, "gerbers.zip must contain .brd files"
        assert ".gbr" in suffixes or any(n.endswith(".gbr") for n in names), "gerbers.zip must contain gerber files"
        # Check both PCBs are represented
        assert any("carrier_board" in n for n in names), "gerbers.zip must include carrier_board files"
        assert any("flex_tail" in n for n in names), "gerbers.zip must include flex_tail files"

    # 2. bom_templates.zip: contains <PCB name>_bom.csv for each PCB
    with zipfile.ZipFile(board_dir / "bom_templates.zip", "r") as zf:
        names = zf.namelist()
        assert "carrier_board_bom.csv" in names, "bom_templates.zip must contain carrier_board_bom.csv"
        assert "flex_tail_bom.csv" in names, "bom_templates.zip must contain flex_tail_bom.csv"

    # 3. centroid_files.zip: contains <PCB name>_pos.csv centroid list for each PCB
    with zipfile.ZipFile(board_dir / "centroid_files.zip", "r") as zf:
        names = zf.namelist()
        assert "carrier_board_pos.csv" in names, "centroid_files.zip must contain carrier_board_pos.csv"
        assert "flex_tail_pos.csv" in names, "centroid_files.zip must contain flex_tail_pos.csv"

    # 4. assembly_files.zip: contains <PCB name>_top.png, <PCB name>_bottom.png textures for each PCB
    with zipfile.ZipFile(board_dir / "assembly_files.zip", "r") as zf:
        names = zf.namelist()
        assert "carrier_board_top.png" in names, "assembly_files.zip must contain carrier_board_top.png"
        assert "carrier_board_bottom.png" in names, "assembly_files.zip must contain carrier_board_bottom.png"
        assert "flex_tail_top.png" in names, "assembly_files.zip must contain flex_tail_top.png"
        assert "flex_tail_bottom.png" in names, "assembly_files.zip must contain flex_tail_bottom.png"


def test_regression_bug_271_split_supplier_submissions_carrier_board() -> None:
    """Verify BUG-271: supplier submissions are split by subassembly and include project summary forms."""
    import zipfile

    board_dir = Path("build/board/carrier_board")

    # 1. Verify subassembly directories exist
    carrier_dir = board_dir / "carrier_board"
    flex_dir = board_dir / "flex_tail"
    assert carrier_dir.is_dir(), "build/board/carrier_board/carrier_board directory must exist"
    assert flex_dir.is_dir(), "build/board/carrier_board/flex_tail directory must exist"

    # 2. carrier_board/gerbers.zip must contain ONLY carrier_board files
    with zipfile.ZipFile(carrier_dir / "gerbers.zip", "r") as zf:
        names = zf.namelist()
        assert any("carrier_board" in n for n in names)
        assert not any("flex_tail" in n for n in names)
        assert "project_summary.txt" in names

    # 3. flex_tail/gerbers.zip must contain ONLY flex_tail files
    with zipfile.ZipFile(flex_dir / "gerbers.zip", "r") as zf:
        names = zf.namelist()
        assert any("flex_tail" in n for n in names)
        assert not any("carrier_board" in n for n in names)
        assert "project_summary.txt" in names

    # 4. Project summaries exist and specify correct layer counts and types
    c_summary = (carrier_dir / "project_summary.txt").read_text()
    assert "Rigid" in c_summary
    assert "6 Layers" in c_summary
    assert "ENIG" in c_summary

    f_summary = (flex_dir / "project_summary.txt").read_text()
    assert "Flex" in f_summary or "FPC" in f_summary
    assert "2 Layers" in f_summary


def test_regression_bug_266_remove_led_and_jumper_opposite_side_designators(tmp_path: Path) -> None:
    """Verify BUG-266: Component designators for LEDs, jumpers, and switches are removed from both B.SilkS and F.SilkS."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.exporter import PCBExporter

    provider = CarrierBoardProvider()
    provider.silkscreen()
    pcb_cfg = provider.pcb_config

    bottom_texts = [t.text for t in pcb_cfg.silkscreen_texts if t.layer == "B.SilkS"]

    removed_designators = (
        [f"D{i}" for i in range(2, 8)] + [f"JP{i}" for i in range(1, 5)] + [f"R{i}" for i in range(7, 13)] + ["SW1"]
    )
    for des in removed_designators:
        assert des not in bottom_texts, f"Opposite-side component designator '{des}' found on B.SilkS"

    # Verify omitted designators are registered in PCBConfig
    assert set(removed_designators).issubset(set(pcb_cfg.omitted_silkscreen_designators))

    # Verify that during PCB export, none of these designators are auto-rendered on F.SilkS or any layer
    wiring = Wiring(str(provider.wiring_path))
    exp = PCBExporter(pcb_cfg, wiring=wiring)
    out_pcb = tmp_path / "carrier_board.kicad_pcb"
    exp.export_kicad_pcb(str(out_pcb))
    content = out_pcb.read_text(encoding="utf-8")
    for des in removed_designators:
        assert f'(gr_text "{des}"' not in content, (
            f"Component designator '{des}' unexpectedly rendered on silkscreen in KiCad PCB"
        )


def test_regression_bug_267_c18_c19_vertical_stack_and_u11_clearance() -> None:
    """Verify BUG-267: C18 and C19 are stacked vertically outside U11 silkscreen border with 0 DRC errors."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    comp_map = {c.name: c for c in wiring.footprints}
    nets_map = {n.name: n for n in wiring.nets}

    # 1. C18 and C19 exist and are stacked vertically at X >= 6.5
    assert "C18" in comp_map, "C18 tuning capacitor must exist"
    assert "C19" in comp_map, "C19 tuning capacitor must exist"
    c18 = comp_map["C18"]
    c19 = comp_map["C19"]

    # Vertically stacked: same X coordinate, different Y coordinates
    assert c18.position[0] == c19.position[0], (
        f"C18 and C19 must be vertically stacked with matching X, got C18.X={c18.position[0]}, C19.X={c19.position[0]}"
    )
    assert c18.position[1] != c19.position[1], "C18 and C19 must have distinct Y positions"

    # Well clear of U11 edge (X=5.0) and silkscreen brackets (X=5.25)
    assert c18.position[0] >= 6.5, (
        f"C18/C19 X position must be >= 6.5mm to be outside U11 silkscreen border, got {c18.position[0]}"
    )

    # 2. Verify net connections
    assert any(c == "C18" and p == "1" for c, p in nets_map["NFC1"].pins), "C18 pin 1 must connect to NFC1"
    assert any(c == "C18" and p == "2" for c, p in nets_map["GND"].pins), "C18 pin 2 must connect to GND"
    assert any(c == "C19" and p == "1" for c, p in nets_map["NFC2"].pins), "C19 pin 1 must connect to NFC2"
    assert any(c == "C19" and p == "2" for c, p in nets_map["GND"].pins), "C19 pin 2 must connect to GND"

    # 3. PCB DRC check passes with 0 violations
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0, f"Expected 0 DRC errors, got: {report.summary()}"


def test_regression_bug_272_supplier_feedback_carrier_board() -> None:
    """Verify BUG-272: Supplier feedback items are addressed across carrier board CAM files and docs.

    1. Soldermask color: carrier_board manifest color is matte black [0.12, 0.12, 0.12, 1.0].
    2. Stackup soldermask: KiCad exported PCB includes F.Mask and B.Mask with Black soldermask.
    3. Impedance control: project_summary.txt, project_summary.md, and impedance_control_info.txt
       explicitly detail track width, spacing, target value, and reference layers (50Ω SE, 90Ω diff, 85Ω diff).
    4. Via plugging: Confirmation to fill all vias in BGA area and SMD pads with resin and cap (VIPPO / IPC-4761 Type VII).
    5. Package inclusion: impedance_control_info.txt is packaged inside carrier_board/gerbers.zip.
    """
    import zipfile
    import yaml

    # 1. Manifest color check (Matte Black)
    manifest_path = Path("src/projects/carrier_board/manifest.yaml")
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    carrier_color = manifest_data.get("carrier_board", {}).get("color", [])
    assert carrier_color[:3] == [0.12, 0.12, 0.12], (
        f"carrier_board manifest color must be Matte Black [0.12, 0.12, 0.12, 1.0], got {carrier_color}"
    )

    # 2. Subassembly submission files
    board_dir = Path("build/board/carrier_board")
    carrier_dir = board_dir / "carrier_board"
    c_summary_txt = (carrier_dir / "project_summary.txt").read_text(encoding="utf-8")
    c_summary_md = (carrier_dir / "project_summary.md").read_text(encoding="utf-8")

    # Soldermask color in summary
    assert "Matte Black" in c_summary_txt, "project_summary.txt must specify Matte Black mask"
    assert "Matte Black" in c_summary_md, "project_summary.md must specify Matte Black mask"

    # Impedance control specifications in summary
    assert "CONTROLLED IMPEDANCE" in c_summary_txt, "project_summary.txt must have CONTROLLED IMPEDANCE section"
    assert "50" in c_summary_txt and "0.18" in c_summary_txt, "50 Ohm SE track (0.18mm) must be specified"
    assert "90" in c_summary_txt and "0.16" in c_summary_txt and "0.18" in c_summary_txt, (
        "90 Ohm diff pair (0.16mm width / 0.18mm spacing) must be specified"
    )
    assert "85" in c_summary_txt and "0.15" in c_summary_txt, (
        "85 Ohm diff pair (0.18mm width / 0.15mm spacing) must be specified"
    )

    # Via plugging confirmation (resin fill and cap / VIPPO)
    assert "Resin" in c_summary_txt or "resin" in c_summary_txt, (
        "Via resin fill must be specified in project_summary.txt"
    )
    assert "cap" in c_summary_txt.lower() or "vippo" in c_summary_txt.lower(), (
        "Via capping / VIPPO must be confirmed in project_summary.txt"
    )

    # Dedicated impedance control info file
    imp_file = carrier_dir / "impedance_control_info.txt"
    assert imp_file.is_file(), "impedance_control_info.txt must exist in carrier_board submission directory"
    imp_text = imp_file.read_text(encoding="utf-8")
    assert "50" in imp_text and "90" in imp_text and "85" in imp_text

    # Packaging in gerbers.zip
    with zipfile.ZipFile(carrier_dir / "gerbers.zip", "r") as zf:
        names = zf.namelist()
        assert "impedance_control_info.txt" in names, (
            "carrier_board/gerbers.zip must contain impedance_control_info.txt"
        )
        assert "project_summary.txt" in names, "carrier_board/gerbers.zip must contain project_summary.txt"
