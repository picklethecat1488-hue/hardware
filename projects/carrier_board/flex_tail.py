"""Declarative flexible polyimide sensing tail PCB layout, routing, and assembly tests for Carrier Board."""

from typing import Optional, List
from build123d import (
    BuildLine,
    BuildSketch,
    Line,
    Locations,
    Polygon,
    Polyline,
    extrude,
    fillet,
)
from provider import Room, Mode
from model.pcb import (
    TraceSegmentModel,
    ViaModel,
    FlexType,
    CapacitiveElectrodeModel,
    ElectrodeType,
    ElectrodeShape,
    PCBObstacleModel,
)
from provider.pcb import (
    BuildFlexPCB,
    BuildSilkscreen,
    SilkscreenText,
    SilkscreenLine,
    BuildTraces,
    make_trace,
    BuildAssemblyTests,
    BuildCapacitiveSensors,
    BuildObstacles,
    TestStep,
)


def get_flex_tail_traces() -> List[TraceSegmentModel]:
    """Return pre-routed copper trace segments on F.Cu for the flexible polyimide tail."""
    with BuildTraces(default_layer="F.Cu", default_width_mm=0.15) as bt:
        # Net CAP_TX2 (Left outermost sensing drive line & button taps)
        with BuildLine():
            Polyline(
                (1.0, -22.75),
                (1.0, -24.2),
                (-7.5, -24.2),
                (-7.5, -19.5),
                (-6.6, -18.6),
                (-6.6, 7.0),
                (-6.6, 18.0),
            )
            Line((-6.6, 7.0), (-5.0, 7.0))
            Line((-6.6, 18.0), (-4.0, 18.0))
            make_trace("CAP_TX2")

        # Net CAP_TX1 (Left intermediate sensing drive line & slider taps)
        with BuildLine():
            Polyline(
                (2.0, -22.75),
                (2.0, -22.0),
                (1.8, -21.8),
                (-6.5, -21.8),
                (-6.5, -19.5),
                (-6.0, -19.0),
                (-6.0, -3.0),
                (-6.0, 2.0),
            )
            Line((-6.0, -3.0), (-5.0, -3.0))
            Line((-6.0, 2.0), (-5.0, 2.0))
            make_trace("CAP_TX1")

        # Net CAP_TX0 (Left innermost sensing drive line & slider taps)
        with BuildLine():
            Polyline(
                (3.0, -22.75),
                (3.0, -22.0),
                (3.5, -21.5),
                (3.5, -20.5),
                (-5.4, -20.5),
                (-5.4, -13.0),
                (-5.4, -8.0),
            )
            Line((-5.4, -13.0), (-5.0, -13.0))
            Line((-5.4, -8.0), (-5.0, -8.0))
            make_trace("CAP_TX0")

        # Net CAP_RX0 (Right innermost sensing receive line & slider tap)
        with BuildLine():
            Polyline(
                (5.0, -22.75),
                (5.0, -22.0),
                (5.4, -21.6),
                (5.4, -13.0),
                (5.0, -13.0),
            )
            make_trace("CAP_RX0")

        # Net CAP_RX1 (Right intermediate sensing receive line & slider taps)
        with BuildLine():
            Polyline(
                (6.0, -22.75),
                (6.0, -22.0),
                (6.45, -21.55),
                (6.45, -19.5),
                (6.0, -19.0),
                (6.0, -8.0),
                (6.0, -3.0),
            )
            Line((6.0, -8.0), (5.0, -8.0))
            Line((6.0, -3.0), (5.0, -3.0))
            make_trace("CAP_RX1")

        # Net CAP_RX2 (Right outermost sensing receive line & button taps)
        with BuildLine():
            Polyline(
                (7.0, -22.75),
                (7.0, -21.7),
                (6.8, -21.5),
                (6.8, -19.5),
                (6.6, -19.0),
                (6.6, 2.0),
                (6.6, 7.0),
                (6.6, 18.0),
            )
            Line((6.6, 2.0), (5.0, 2.0))
            Line((6.6, 7.0), (5.0, 7.0))
            Line((6.6, 18.0), (4.0, 18.0))
            make_trace("CAP_RX2")

        # Net CAP_RX3 (Perimeter guard / proximity loop enclosing sensing tail)
        with BuildLine():
            Polyline(
                (4.0, -22.75),
                (4.0, -24.2),
                (7.4, -24.2),
                (7.4, -18.5),
                (7.1, -18.1),
                (7.1, 24.5),
                (-7.1, 24.5),
                (-7.1, -17.5),
            )
            make_trace("CAP_RX3")

    return list(bt.traces)


def get_flex_tail_vias() -> List[ViaModel]:
    """Return interlayer vias for the flexible sensing tail."""
    return []


class FlexTailPCBListing:
    """PCB substrate builders, capacitive sensor electrodes, and assembly tests for Flex Tail."""

    FLEX_TAIL_COVERLAY_COLOR: tuple[float, float, float] = (0.12, 0.12, 0.12)

    def flex_tail(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildFlexPCB:
        """Build the flexible polyimide sensing tail extending from the carrier board edge."""
        w_tail = self.settings.flex_tail_width
        l_tail = self.settings.flex_tail_length
        t_tail = self.settings.flex_tail_thickness

        pts = [
            (-w_tail / 2.0, -l_tail / 2.0),
            (w_tail / 2.0, -l_tail / 2.0),
            (w_tail / 2.0, -l_tail / 2.0 + 7.0),
            (7.5, -l_tail / 2.0 + 9.0),
            (7.5, l_tail / 2.0 - 1.5),
            (5.0, l_tail / 2.0),
            (-5.0, l_tail / 2.0),
            (-7.5, l_tail / 2.0 - 1.5),
            (-7.5, -l_tail / 2.0 + 9.0),
            (-w_tail / 2.0, -l_tail / 2.0 + 7.0),
        ]

        cap_sensors = [
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_1",
                channel_id=0,
                electrode_type=ElectrodeType.MUTUAL,
                shape=ElectrodeShape.INTERDIGITAL,
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, -13.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX0",
                rx_pin="CAP_RX0",
                threshold_raw=2200,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_2",
                channel_id=1,
                electrode_type=ElectrodeType.MUTUAL,
                shape=ElectrodeShape.INTERDIGITAL,
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, -8.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX0",
                rx_pin="CAP_RX1",
                threshold_raw=2200,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_3",
                channel_id=2,
                electrode_type=ElectrodeType.MUTUAL,
                shape=ElectrodeShape.INTERDIGITAL,
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, -3.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX1",
                rx_pin="CAP_RX1",
                threshold_raw=2500,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_4",
                channel_id=3,
                electrode_type=ElectrodeType.MUTUAL,
                shape=ElectrodeShape.INTERDIGITAL,
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, 2.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX1",
                rx_pin="CAP_RX2",
                threshold_raw=2500,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_5",
                channel_id=4,
                electrode_type=ElectrodeType.MUTUAL,
                shape=ElectrodeShape.INTERDIGITAL,
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, 7.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX2",
                rx_pin="CAP_RX2",
                threshold_raw=2800,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="ACTION_BUTTON",
                channel_id=5,
                electrode_type=ElectrodeType.MUTUAL,
                shape=ElectrodeShape.INTERDIGITAL,
                area_mm=(8.0, 6.0),
                center_mm=(0.0, 18.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX2",
                rx_pin="CAP_RX2",
                threshold_raw=2000,
                shape_ref="flex_tail",
                pitch_mm=1.2,
                gap_mm=0.3,
            ),
            CapacitiveElectrodeModel(
                name="PROXIMITY_SENSOR",
                channel_id=6,
                electrode_type=ElectrodeType.SELF,
                shape=ElectrodeShape.LOOP,
                area_mm=(14.2, 42.0),
                center_mm=(0.0, 3.5),
                drive_shield=False,
                hatch_ground_pour=False,
                rx_pin="CAP_RX3",
                threshold_raw=1500,
                shape_ref="flex_tail",
            ),
        ]

        tail_obstacles = [
            PCBObstacleModel(
                name="flex_vacuum_plate",
                shape="box",
                dimensions_mm=(30.0, 60.0, 4.0),
                position_mm=(0.0, 0.0, -2.0),
                description="Flex tail vacuum fixture support plate",
            ),
            PCBObstacleModel(
                name="J4",
                shape="box",
                dimensions_mm=(18.0, 5.0, 2.4),
                position_mm=(0.0, -22.75, 1.2),
                description="FPC-30P interface connector on flex tail",
            ),
        ]

        with BuildFlexPCB(
            name="flex_tail",
            flex_type=FlexType.CAPACITIVE,
            coverlay_color="black",
        ) as tail:
            tail.outline_polygon = pts
            with BuildCapacitiveSensors() as bcs:
                bcs.add(cap_sensors)
            with BuildObstacles() as bo:
                bo.add(tail_obstacles)
            # Manifold hull enclosing connector and sensing channels with minimal wasted space
            with BuildSketch() as s:
                Polygon(*pts)
                r_corner = self.settings.flex_tail_corner_radius
                fillet(s.vertices(), radius=r_corner)
            extrude(s.sketch, amount=t_tail)

            with BuildSilkscreen() as silk:
                with Locations((0.0, -22.75)):
                    SilkscreenText(
                        "FLEX TAIL SENSOR REV 1.0", layer="B.SilkS", font_size=0.6, thickness=0.09, mirror=True
                    )
                with Locations((-7.5, -21.0)):
                    SilkscreenText("• Pin 1", layer="F.SilkS", font_size=0.5, thickness=0.08)

                # BUG-275: Fabrication notes and panelization specifications on Dwgs.User
                with Locations((0.0, -24.5)):
                    SilkscreenText(
                        "FAB: 2-LAYER POLYIMIDE FPC (0.20mm) | SMT ONLY: 0 DRILL HOLES / 0 VIAS",
                        layer="Dwgs.User",
                        font_size=0.5,
                        thickness=0.08,
                    )
                with Locations((0.0, -25.5)):
                    SilkscreenText(
                        "PANEL: 1*2 PANEL IN 64x64mm ACCEPTED WITH X-OUT BOARD ACCEPTED",
                        layer="Dwgs.User",
                        font_size=0.5,
                        thickness=0.08,
                    )

                # Inner Touch Sensing Region Outline (enclosing slider and action button without intersecting traces)
                SilkscreenLine((-6.85, -15.5), (-6.85, 21.8), layer="F.SilkS", thickness=0.15)
                SilkscreenLine((6.85, -15.5), (6.85, 21.8), layer="F.SilkS", thickness=0.15)
                SilkscreenLine((-6.85, 21.8), (6.85, 21.8), layer="F.SilkS", thickness=0.15)

                # 5-Button Slider Region Labels (BUG-147, BUG-155)
                with Locations((0.0, 11.5)):
                    SilkscreenText("SLIDER", layer="F.SilkS", font_size=0.8, thickness=0.12)
                for idx, dy in enumerate([-10.0, -5.0, 0.0, 5.0, 10.0], start=1):
                    with Locations((0.0, -3.0 + dy)):
                        SilkscreenText(f"S{idx}", layer="F.SilkS", font_size=0.55, thickness=0.08)

                # Action Button Region Label (centered) (BUG-147, BUG-157, BUG-158)
                with Locations((0.0, 18.0)):
                    SilkscreenText("ACTION", layer="F.SilkS", font_size=0.6, thickness=0.09)

                # Perimeter Proximity Sensor Loop Outline & Annotation (BUG-158, open at bottom)
                SilkscreenLine((-7.35, -16.5), (-7.35, 24.8), layer="F.SilkS", thickness=0.15)
                SilkscreenLine((7.35, -16.5), (7.35, 24.8), layer="F.SilkS", thickness=0.15)
                SilkscreenLine((-7.35, 24.8), (7.35, 24.8), layer="F.SilkS", thickness=0.15)
                with Locations((0.0, 23.2)):
                    SilkscreenText("PROX LOOP", layer="F.SilkS", font_size=0.6, thickness=0.09)

            # Manual traces and sensor routing on flexible polyimide substrate
            get_flex_tail_traces()

            with BuildAssemblyTests(
                test_fixture="flying_probe", pass_criteria="all_steps_within_tolerance", subassembly="flex_tail"
            ) as tests:
                TestStep(
                    step_id="TEST_CAP_SENSE_CHAN0",
                    description="Measure baseline mutual capacitance on liquid level electrode Channel 0",
                    test_type="capacitance",
                    net_name="CAP_CHAN0",
                    pad_a_mm=(0.0, -6.25),
                    pad_b_mm=(-3.0, -6.25),
                    nominal=12.5,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="250kHz 1.8V square wave",
                    measured=12.6,
                )
                TestStep(
                    step_id="TEST_CAP_SENSE_CHAN1",
                    description="Measure baseline mutual capacitance on liquid level electrode Channel 1",
                    test_type="capacitance",
                    net_name="CAP_CHAN1",
                    pad_a_mm=(0.0, 5.25),
                    pad_b_mm=(-3.0, 5.25),
                    nominal=14.0,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="250kHz 1.8V square wave",
                    measured=14.1,
                )
                TestStep(
                    step_id="TEST_CAP_SENSE_CHAN2",
                    description="Measure baseline mutual capacitance on liquid level electrode Channel 2",
                    test_type="capacitance",
                    net_name="CAP_CHAN2",
                    pad_a_mm=(0.0, 16.75),
                    pad_b_mm=(-3.0, 16.75),
                    nominal=15.5,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="250kHz 1.8V square wave",
                    measured=15.4,
                )
                TestStep(
                    step_id="TEST_CAP_SENSE_CHAN3",
                    description="Measure baseline self capacitance on liquid proximity electrode Channel 3",
                    test_type="capacitance",
                    net_name="CAP_CHAN3",
                    pad_a_mm=(0.0, 24.75),
                    pad_b_mm=(0.0, -22.75),
                    nominal=8.0,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="250kHz 1.8V square wave self-cap",
                    measured=8.1,
                )
                TestStep(
                    step_id="TEST_CONTINUITY_TAIL_GND",
                    description="Verify ground plane guard ring continuity along flex tail contour",
                    test_type="continuity",
                    net_name="FLEX_GND",
                    pad_a_mm=(-7.0, -20.0),
                    pad_b_mm=(7.0, -20.0),
                    nominal=0.08,
                    tolerance_pct=20.0,
                    unit="ohm",
                    stimulus="100mA 4-wire Kelvin DC",
                    measured=0.078,
                )
                TestStep(
                    step_id="TEST_CAP_MUTUAL_TOUCH_CHAN0",
                    description="Simulate human finger touch proximity on liquid level Channel 0 mutual capacitance electrode",
                    test_type="mutual_cap",
                    net_name="CAP_CHAN0",
                    pad_a_mm=(0.0, -6.25),
                    pad_b_mm=(-3.0, -6.25),
                    nominal=15.8,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="Simulated finger proximity 250kHz 1.8V dielectric perturb",
                    measured=15.9,
                )
                TestStep(
                    step_id="TEST_CAP_MUTUAL_TOUCH_CHAN1",
                    description="Simulate human finger touch proximity on liquid level Channel 1 mutual capacitance electrode",
                    test_type="mutual_cap",
                    net_name="CAP_CHAN1",
                    pad_a_mm=(0.0, 5.25),
                    pad_b_mm=(-3.0, 5.25),
                    nominal=17.5,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="Simulated finger proximity 250kHz 1.8V dielectric perturb",
                    measured=17.6,
                )

        return tail

    def view_flex_tail(self, room: Room, mode: Mode) -> None:
        """Assemble flex tail PCB with sensor pads and test points for inspection and simulation."""
        tail = self.flex_tail("flex_tail", None, mode)
        coverlay_col = getattr(self, "FLEX_TAIL_COVERLAY_COLOR", (0.12, 0.12, 0.12))
        room.add("flex_tail", tail.part, color=coverlay_col, alpha=0.9)


__all__ = [
    "FlexTailPCBListing",
    "get_flex_tail_traces",
    "get_flex_tail_vias",
]
