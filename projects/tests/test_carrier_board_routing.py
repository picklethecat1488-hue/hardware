"""Tests for carrier_board rigid-flex PCB and protective enclosure CAD geometry."""

from pathlib import Path
import pytest
from build123d import Location
from projects.carrier_board.provider import CarrierBoardProvider
from model.wiring import Wiring
from provider import Mode


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
    wiring = provider.wiring
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
    1. Flying probe simulation hooks for flex_tail only synthesize steps defined in declarative test models.
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
    wiring = provider.wiring
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
    from provider.footprints import get_shared_footprints

    ic_fps = get_shared_footprints()
    assert "MOD-BLE-PCB-ANT" in ic_fps, "MOD-BLE-PCB-ANT footprint must be defined in provider.footprints"
    ble_fp = ic_fps["MOD-BLE-PCB-ANT"]
    dims = ble_fp.get("dimensions", [])
    assert dims == [10.0, 15.0, 2.23], f"U11 dimensions must match LGA-72 Table 27 [10.0, 15.0, 2.23], got {dims}"

    # 5. Full DRC report passes with zero errors
    drc = PCBDesignRulesChecker(pcb_cfg)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0, f"Expected 0 DRC errors, got {report.error_count}"


def test_power_hardening_bug_243() -> None:
    """Verify BUG-243 superseded by BUG-JUMPING-SILVERFISH-144: C15..D8 purged and DRC passes."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    comp_map = {c.name: c for c in wiring.footprints}

    for name in ("C15", "C16", "C17", "D8"):
        assert name not in comp_map, f"{name} must be removed to eliminate parasitic antenna stubs"

    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.error_count == 0, f"Expected 0 DRC errors, got: {report.summary()}"


def test_regression_bug_jumping_silverfish_144_unnecessary_vias_removed() -> None:
    """Verify BUG-JUMPING-SILVERFISH-144: 8 unnecessary vias and dangling B.Cu stubs removed from carrier board."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    cfg = provider.pcb_config

    unnecessary_via_positions = {
        (12.2, 29.6),
        (15.2, 29.6),
        (12.5, 32.6),
        (14.6, 32.8),
        (13.8, 29.6),
        (16.8, 29.6),
        (13.5, 32.6),
        (17.4, 32.8),
    }

    via_positions = {(round(v.position_mm[0], 2), round(v.position_mm[1], 2)) for v in cfg.vias}
    for pos in unnecessary_via_positions:
        assert pos not in via_positions, f"Unnecessary via at {pos} must be removed"

    dangling_stubs = {
        ((12.2, 29.0), (12.2, 29.6)),
        ((15.2, 29.0), (15.2, 29.6)),
        ((12.5, 32.0), (12.5, 32.6)),
        ((14.6, 32.0), (14.6, 32.8)),
        ((13.8, 29.0), (13.8, 29.6)),
        ((16.8, 29.0), (16.8, 29.6)),
        ((13.5, 32.0), (13.5, 32.6)),
        ((17.4, 32.0), (17.4, 32.8)),
    }
    trace_segments = {
        (
            (round(t.start_mm[0], 2), round(t.start_mm[1], 2)),
            (round(t.end_mm[0], 2), round(t.end_mm[1], 2)),
        )
        for t in cfg.traces
    }
    for stub in dangling_stubs:
        assert stub not in trace_segments, f"Dangling stub {stub} must be removed"

    comp_names = {c.name for c in provider.wiring.footprints}
    for name in ("C15", "C16", "C17", "D8"):
        assert name not in comp_names, f"{name} must not be present in carrier board wiring"

    drc = PCBDesignRulesChecker(cfg)
    report = drc.check_all(wiring=provider.wiring)
    assert report.error_count == 0, f"Expected 0 DRC errors after via removal, got: {report.summary()}"


def test_regression_bug_249_remove_vload_sw_from_ble_module() -> None:
    """Verify BUG-249: VLOAD_SW artifact removed, U11 footprint corrected to NINA datasheet pinout."""
    import yaml
    from pathlib import Path
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring

    provider = CarrierBoardProvider()
    wiring = provider.wiring

    # 1. MOD-BLE-PCB-ANT footprint in provider.footprints must not have VLOAD_SW
    from provider.footprints import get_shared_footprints

    shared_fps = get_shared_footprints()
    ble_fp = shared_fps["MOD-BLE-PCB-ANT"]
    ble_pin_names = [p["name"] for p in ble_fp["pins"]]
    assert "VLOAD_SW" not in ble_pin_names, "MOD-BLE-PCB-ANT footprint must not have VLOAD_SW pin"
    assert "SWITCH_2" in ble_pin_names, "MOD-BLE-PCB-ANT footprint pin 18 must be SWITCH_2"

    # 2. wiring.yaml must not have VLOAD_SW net or U11.VLOAD_SW pin connection
    net_names = [n.name for n in wiring.nets]
    assert "VLOAD_SW" not in net_names, "VLOAD_SW net must be removed from wiring.yaml"
    for net in wiring.nets:
        for pin in net.pins:
            assert pin[0] != "U11" or pin[1] != "VLOAD_SW", "U11 must not have any pin connected to VLOAD_SW"

    # 3. pcb_config must not have VLOAD_SW in Sheet 2 pin_breakouts
    sheet_2 = provider.pcb_config.schematic_sheets[1]
    if sheet_2.pin_breakouts and "U11" in sheet_2.pin_breakouts:
        assert "VLOAD_SW" not in sheet_2.pin_breakouts["U11"]


def test_regression_bug_250_nina_nfc_antenna_and_tuning_caps() -> None:
    """Verify BUG-250: NINA-B312 native NFC1/NFC2 pins routed to antenna header and shunt tuning capacitors."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = provider.wiring
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
    wiring = provider.wiring
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
    wiring = provider.wiring
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
    wiring = provider.wiring
    cfg = provider.pcb_config

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
    wiring = provider.wiring

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
    wiring = provider.wiring
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
    wiring = provider.wiring
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
    deck_path = Path("projects/carrier_board/docs/supplier_pcb_review_deck.md")
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

    # 1. gerbers.zip: contains standard Gerber and drill files only per BUG-OPEN-003
    with zipfile.ZipFile(board_dir / "gerbers.zip", "r") as zf:
        names = zf.namelist()
        suffixes = {Path(n).suffix.lower() for n in names}
        assert ".pcb" not in suffixes, "gerbers.zip must not contain .pcb companion files"
        assert ".pcbdoc" not in suffixes, "gerbers.zip must not contain .pcbdoc companion files"
        assert ".cam" not in suffixes, "gerbers.zip must not contain .cam companion files"
        assert ".brd" not in suffixes, "gerbers.zip must not contain .brd companion files"
        assert ".kicad_pcb" not in suffixes, "gerbers.zip must not contain .kicad_pcb files"
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
