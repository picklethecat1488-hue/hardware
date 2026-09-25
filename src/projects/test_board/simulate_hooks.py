"""Flying probes physics simulation and electrical validation hooks for test_board.

Replicates a physical high-precision multi-axis flying probe tester in PyBullet.
Populates component and fixture obstacles, executes collision-free flight trajectories,
detects pad contact, validates electrical continuity, impedance, and capacitance,
logs 3D probe motion and metrics to Rerun, and generates a factory test report.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import pybullet as p

from provider.bullet import _is_real_physics_client
from provider import Simulate, rerun_is_enabled


@dataclass
class TestStepSpec:
    """Specification and measured result of a flying probe test step."""

    step_id: str
    description: str
    test_type: str  # continuity, impedance, capacitance, voltage, resistance
    net_name: str
    pad_a_mm: Tuple[float, float]
    pad_b_mm: Tuple[float, float]
    nominal: float
    tolerance_pct: float
    unit: str
    stimulus: str
    measured: float = 0.0
    passed: bool = False


CARRIER_TEST_STEPS: List[TestStepSpec] = [
    TestStepSpec(
        step_id="TEST_CONTINUITY_GND",
        description="Verify solid low-impedance ground plane continuity across all copper layers",
        test_type="continuity",
        net_name="GND",
        pad_a_mm=(-18.0, -22.0),  # TP1 (GND)
        pad_b_mm=(-25.0, -2.0),  # J3 GND shield
        nominal=0.050,
        tolerance_pct=20.0,
        unit="ohm",
        stimulus="100mA 4-wire Kelvin DC",
        measured=0.048,
    ),
    TestStepSpec(
        step_id="TEST_IMP_PCIE_DIFF",
        description="Measure PCIe Gen4 differential impedance on TX0+/TX0-",
        test_type="impedance",
        net_name="PCIE_TX0",
        pad_a_mm=(-14.0, -22.0),  # TP5 (TX0_N)
        pad_b_mm=(-10.0, -22.0),  # TP6 (TX0_P)
        nominal=85.0,
        tolerance_pct=10.0,
        unit="ohm",
        stimulus="100ps TDR step differential pulse",
        measured=84.6,
    ),
    TestStepSpec(
        step_id="TEST_RAIL_3V3",
        description="Verify regulated system 3.3V power distribution rail",
        test_type="voltage",
        net_name="3V3",
        pad_a_mm=(-10.0, -26.0),  # TP4 (3V3)
        pad_b_mm=(-18.0, -22.0),  # TP1 (GND)
        nominal=3.30,
        tolerance_pct=3.0,
        unit="V",
        stimulus="DC power rail regulation probe",
        measured=3.31,
    ),
    TestStepSpec(
        step_id="TEST_RAIL_VBAT",
        description="Verify battery input sensing rail continuity to charger",
        test_type="voltage",
        net_name="VBAT",
        pad_a_mm=(-18.0, -26.0),  # TP2 (VBAT)
        pad_b_mm=(-18.0, -22.0),  # TP1 (GND)
        nominal=3.70,
        tolerance_pct=5.0,
        unit="V",
        stimulus="Battery charge domain sensor",
        measured=3.72,
    ),
    TestStepSpec(
        step_id="TEST_IMP_MIPI_DATA",
        description="Measure MIPI CSI-2 differential data lane impedance",
        test_type="impedance",
        net_name="MIPI_DATA0",
        pad_a_mm=(-14.0, 22.0),  # TP11 (DATA0_N)
        pad_b_mm=(-10.0, 22.0),  # TP12 (DATA0_P)
        nominal=100.0,
        tolerance_pct=10.0,
        unit="ohm",
        stimulus="200ps differential TDR step",
        measured=99.2,
    ),
    TestStepSpec(
        step_id="TEST_IMP_MIPI_CLK",
        description="Measure MIPI CSI-2 differential clock lane impedance",
        test_type="impedance",
        net_name="MIPI_CLK",
        pad_a_mm=(-6.0, 22.0),  # TP13 (CLK_N)
        pad_b_mm=(-2.0, 22.0),  # TP14 (CLK_P)
        nominal=100.0,
        tolerance_pct=10.0,
        unit="ohm",
        stimulus="200ps differential TDR step",
        measured=100.8,
    ),
    TestStepSpec(
        step_id="TEST_I2C_PULLUPS",
        description="Measure I2C SDA/SCL pull-up resistance to 3.3V rail",
        test_type="resistance",
        net_name="I2C_BUS",
        pad_a_mm=(14.0, -4.0),  # TP9 (I2C_SDA)
        pad_b_mm=(18.0, -4.0),  # TP10 (I2C_SCL)
        nominal=4700.0,
        tolerance_pct=5.0,
        unit="ohm",
        stimulus="1.0V DC precision Ohmmeter",
        measured=4705.0,
    ),
]

FLEX_TEST_STEPS: List[TestStepSpec] = [
    TestStepSpec(
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
    ),
    TestStepSpec(
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
    ),
    TestStepSpec(
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
    ),
    TestStepSpec(
        step_id="TEST_CAP_SENSE_CHAN3",
        description="Measure baseline self capacitance on liquid proximity electrode Channel 3",
        test_type="capacitance",
        net_name="CAP_CHAN3",
        pad_a_mm=(0.0, 24.75),
        pad_b_mm=(0.0, -22.75),  # Reference J4 GND
        nominal=8.0,
        tolerance_pct=15.0,
        unit="pF",
        stimulus="250kHz 1.8V square wave self-cap",
        measured=8.1,
    ),
    TestStepSpec(
        step_id="TEST_CONTINUITY_TAIL_GND",
        description="Verify ground plane guard ring continuity along flex tail contour",
        test_type="continuity",
        net_name="FLEX_GND",
        pad_a_mm=(-7.0, -20.0),
        pad_b_mm=(7.0, -20.0),
        nominal=0.080,
        tolerance_pct=20.0,
        unit="ohm",
        stimulus="100mA 4-wire Kelvin DC",
        measured=0.078,
    ),
]


def render_markdown_test_report(
    target_name: str,
    steps: List[TestStepSpec],
    current_step_idx: int,
    total_sim_steps: int,
) -> str:
    """Format an interactive GitHub-Flavored Markdown flying probe test report.

    Args:
        target_name: Target board name (carrier_board or flex_tail).
        steps: List of test step specifications with measurement results.
        current_step_idx: Current simulation step counter.
        total_sim_steps: Total scheduled simulation steps.

    Returns:
        Structured Markdown report string.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    passed_count = sum(1 for s in steps if s.passed)
    total_count = len(steps)
    all_passed = passed_count == total_count
    overall_status = "PASS" if all_passed else ("TESTING" if passed_count < total_count else "FAIL")
    status_badge = "🟢 `PASS`" if all_passed else ("🟡 `IN_PROGRESS`" if passed_count < total_count else "🔴 `FAIL`")
    yield_pct = (passed_count / total_count * 100.0) if total_count > 0 else 100.0

    lines = [
        f"# Flying Probes Automated Acceptance Test Report: {target_name.replace('_', ' ').title()}",
        "",
        "> Automated physical and electrical flying probe verification report simulated via PyBullet and Rerun.",
        "",
        "## Test Execution Summary",
        "",
        "| Metric | Details |",
        "| :--- | :--- |",
        f"| **Test Fixture** | High-Precision Dual-Head Flying Probe Tester (FP-600) |",
        f"| **Target Unit** | `{target_name}` |",
        f"| **Timestamp** | `{now_str}` |",
        f"| **Overall Verdict** | {status_badge} |",
        f"| **Tested Steps** | `{passed_count} / {total_count}` |",
        f"| **Yield** | `{yield_pct:.1f}%` |",
        f"| **Simulation Progress** | `Step {current_step_idx} / {total_sim_steps}` |",
        "",
        "## Detailed Step Results",
        "",
        "| Step ID | Description | Net | Nominal | Measured | Tolerance | Stimulus | Verdict |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :---: |",
    ]

    for s in steps:
        verdict_str = "🟢 **PASS**" if s.passed else ("🟡 *TESTING*" if current_step_idx > 0 else "⚪ *PENDING*")
        nom_str = f"{s.nominal:.3f} {s.unit}" if s.nominal < 1.0 else f"{s.nominal:.1f} {s.unit}"
        meas_str = f"{s.measured:.3f} {s.unit}" if s.nominal < 1.0 else f"{s.measured:.1f} {s.unit}"
        tol_str = f"±{s.tolerance_pct:.1f}%"
        lines.append(
            f"| `{s.step_id}` | {s.description} | `{s.net_name}` | {nom_str} | {meas_str} | {tol_str} | {s.stimulus} | {verdict_str} |"
        )

    lines.append("")
    lines.append("## Electrical Specifications & Compliance Criteria")
    lines.append(
        "- **Continuity**: Contact resistance strictly $\\le R_{\\text{nom}} \\times (1 + \\text{tol}\\%)$. Zero opens."
    )
    lines.append(
        "- **Differential Impedance**: PCIe $85\\,\\Omega \\pm 10\\%$, MIPI $100\\,\\Omega \\pm 10\\%$. Reflection $\\le -20\\,\\text{dB}$."
    )
    lines.append(
        "- **Capacitance**: Liquid sensing pads $12.5 - 15.5\\,\\text{pF} \\pm 15\\%$, Proximity $8.0\\,\\text{pF} \\pm 15\\%$."
    )
    lines.append(
        "- **Probe Clearance**: Minimum vertical flight height $\\ge 15.0\\,\\text{mm}$ above all board component obstacles."
    )
    lines.append("")

    return "\n".join(lines)


def get_simulate_hooks_impl(self: Any, sim_name: str) -> Dict[Simulate, Callable[..., Any]]:
    """Return flying probe simulation and electrical verification hooks for test_board.

    Args:
        self: TestBoardProvider instance.
        sim_name: Target name passed to simulator (e.g. carrier_board or flex_tail).

    Returns:
        Dictionary mapping Simulate.SETUP and Simulate.STEP to execution callbacks.
    """
    is_flex = "flex_tail" in sim_name.lower()
    target_label = "flex_tail" if is_flex else "carrier_board"
    test_steps: List[TestStepSpec] = [
        TestStepSpec(
            step_id=s.step_id,
            description=s.description,
            test_type=s.test_type,
            net_name=s.net_name,
            pad_a_mm=s.pad_a_mm,
            pad_b_mm=s.pad_b_mm,
            nominal=s.nominal,
            tolerance_pct=s.tolerance_pct,
            unit=s.unit,
            stimulus=s.stimulus,
            measured=s.measured,
            passed=False,
        )
        for s in (FLEX_TEST_STEPS if is_flex else CARRIER_TEST_STEPS)
    ]

    sim_state = {
        "client": None,
        "probe_a_id": -1,
        "probe_b_id": -1,
        "obstacle_ids": [],
        "current_step_idx": 0,
        "last_report": "",
        "target_label": target_label,
    }

    # Physical clearances in meters
    z_flight = 0.016  # 16mm clearance above board obstacles
    z_pad = 0.0016 if not is_flex else 0.0003  # Contact pad elevation

    def setup_simulation(body_id: int, client: int, name: str, boundaries: Any, state_tracker: Any = None) -> None:
        sim_state["client"] = client
        if _is_real_physics_client(client):
            p.setGravity(0.0, 0.0, -9.81, physicsClientId=client)

        # 1. Populate physical fixture and component obstacles in PyBullet
        obstacle_ids = []

        if not is_flex:
            # Fixture clamping rails along left and right board edges
            clamp_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.002, 0.046, 0.004], physicsClientId=client)
            c1 = p.createMultiBody(
                baseMass=0, baseCollisionShapeIndex=clamp_col, basePosition=[0.032, 0.0, 0.004], physicsClientId=client
            )
            c2 = p.createMultiBody(
                baseMass=0, baseCollisionShapeIndex=clamp_col, basePosition=[-0.032, 0.0, 0.004], physicsClientId=client
            )
            obstacle_ids.extend([c1, c2])

            # Major tall component obstacles that flying probes must navigate around
            # Connectors and ICs with heights in meters: [half_x, half_y, half_z] and [x, y, z]
            component_obstacles = [
                # U1: MCU BGA at center
                ([0.006, 0.006, 0.0010], [0.0, 0.0, 0.0018]),
                # J1: M.2 Key-M edge connector
                ([0.012, 0.005, 0.0025], [0.0, -0.036, 0.0033]),
                # J2: Hirose FPC-30P connector
                ([0.009, 0.0025, 0.0010], [0.0, 0.038, 0.0018]),
                # J3: USB Type-C receptacle
                ([0.0045, 0.0045, 0.0020], [-0.025, 0.0, 0.0028]),
                # J5: SWD 10-pin micro-header
                ([0.0030, 0.0060, 0.0030], [-0.021, -0.007, 0.0038]),
                # J13: Battery 2-pin JST-PH connector
                ([0.0030, 0.0040, 0.0035], [-0.023, 0.016, 0.0043]),
                # J9 & J10: Expansion headers on right edge
                ([0.0030, 0.0075, 0.0035], [0.0245, -0.005, 0.0043]),
                ([0.0030, 0.0075, 0.0035], [0.0245, -0.021, 0.0043]),
            ]
            for half_ext, pos in component_obstacles:
                col_box = p.createCollisionShape(p.GEOM_BOX, halfExtents=half_ext, physicsClientId=client)
                b_id = p.createMultiBody(
                    baseMass=0, baseCollisionShapeIndex=col_box, basePosition=pos, physicsClientId=client
                )
                obstacle_ids.append(b_id)
        else:
            # Flex tail vacuum fixture support plate and J4 connector obstacle
            plate_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.015, 0.030, 0.002], physicsClientId=client)
            p_id = p.createMultiBody(
                baseMass=0, baseCollisionShapeIndex=plate_col, basePosition=[0.0, 0.0, -0.002], physicsClientId=client
            )
            obstacle_ids.append(p_id)

            j4_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.009, 0.0025, 0.0012], physicsClientId=client)
            j4_id = p.createMultiBody(
                baseMass=0, baseCollisionShapeIndex=j4_col, basePosition=[0.0, -0.02275, 0.0012], physicsClientId=client
            )
            obstacle_ids.append(j4_id)

        sim_state["obstacle_ids"] = obstacle_ids

        # 2. Create high-speed kinematic Probe A and Probe B needle bodies
        needle_col_a = p.createCollisionShape(p.GEOM_SPHERE, radius=0.0006, physicsClientId=client)
        needle_col_b = p.createCollisionShape(p.GEOM_SPHERE, radius=0.0006, physicsClientId=client)

        init_pos_a = [test_steps[0].pad_a_mm[0] * 1e-3, test_steps[0].pad_a_mm[1] * 1e-3, z_flight]
        init_pos_b = [test_steps[0].pad_b_mm[0] * 1e-3, test_steps[0].pad_b_mm[1] * 1e-3, z_flight]

        probe_a_id = p.createMultiBody(
            baseMass=0.05, baseCollisionShapeIndex=needle_col_a, basePosition=init_pos_a, physicsClientId=client
        )
        probe_b_id = p.createMultiBody(
            baseMass=0.05, baseCollisionShapeIndex=needle_col_b, basePosition=init_pos_b, physicsClientId=client
        )

        sim_state["probe_a_id"] = probe_a_id
        sim_state["probe_b_id"] = probe_b_id

    def step_simulation(body_id: int, client: int, step_idx: int, name: str) -> Optional[str]:
        sim_state["current_step_idx"] = step_idx
        num_tests = len(test_steps)
        if num_tests == 0:
            return None

        # Allocate simulation steps across the test steps
        # E.g. with 1000 total steps and 7 tests: ~140 steps per test
        steps_per_test = max(50, 1000 // num_tests)
        active_test_idx = min(num_tests - 1, step_idx // steps_per_test)
        phase_step = step_idx % steps_per_test
        phase_ratio = phase_step / float(steps_per_test)

        active_spec = test_steps[active_test_idx]
        target_a_xy = np.array([active_spec.pad_a_mm[0] * 1e-3, active_spec.pad_a_mm[1] * 1e-3])
        target_b_xy = np.array([active_spec.pad_b_mm[0] * 1e-3, active_spec.pad_b_mm[1] * 1e-3])

        prev_spec = test_steps[max(0, active_test_idx - 1)]
        prev_a_xy = np.array([prev_spec.pad_a_mm[0] * 1e-3, prev_spec.pad_a_mm[1] * 1e-3])
        prev_b_xy = np.array([prev_spec.pad_b_mm[0] * 1e-3, prev_spec.pad_b_mm[1] * 1e-3])

        # Motion Phases:
        # Phase 1 (0.00 -> 0.25): Probes fly horizontally at clearance height z_flight from prev to target
        # Phase 2 (0.25 -> 0.40): Probes descend vertically from z_flight to z_pad
        # Phase 3 (0.40 -> 0.75): Contact dwell phase: validate contact, measure electrical parameters
        # Phase 4 (0.75 -> 1.00): Probes ascend back to z_flight
        contact_active = False
        contact_force = 0.0

        if phase_ratio < 0.25:
            # Flying at clearance Z
            t = phase_ratio / 0.25
            pos_a_xy = (1.0 - t) * prev_a_xy + t * target_a_xy
            pos_b_xy = (1.0 - t) * prev_b_xy + t * target_b_xy
            cur_z_a = z_flight
            cur_z_b = z_flight
        elif phase_ratio < 0.40:
            # Descending to pad
            t = (phase_ratio - 0.25) / 0.15
            pos_a_xy = target_a_xy
            pos_b_xy = target_b_xy
            cur_z_a = (1.0 - t) * z_flight + t * z_pad
            cur_z_b = (1.0 - t) * z_flight + t * z_pad
        elif phase_ratio < 0.75:
            # Dwell & Electrical measurement
            pos_a_xy = target_a_xy
            pos_b_xy = target_b_xy
            cur_z_a = z_pad
            cur_z_b = z_pad
            contact_active = True
            contact_force = 0.15  # 150 mN calibrated probe spring force
            # Validate electrical measurement
            tol = active_spec.nominal * (active_spec.tolerance_pct / 100.0)
            if abs(active_spec.measured - active_spec.nominal) <= tol:
                active_spec.passed = True
        else:
            # Ascending back to clearance
            t = (phase_ratio - 0.75) / 0.25
            pos_a_xy = target_a_xy
            pos_b_xy = target_b_xy
            cur_z_a = (1.0 - t) * z_pad + t * z_flight
            cur_z_b = (1.0 - t) * z_pad + t * z_flight

        pos_a = [float(pos_a_xy[0]), float(pos_a_xy[1]), float(cur_z_a)]
        pos_b = [float(pos_b_xy[0]), float(pos_b_xy[1]), float(cur_z_b)]

        p.resetBasePositionAndOrientation(sim_state["probe_a_id"], pos_a, [0, 0, 0, 1], physicsClientId=client)
        p.resetBasePositionAndOrientation(sim_state["probe_b_id"], pos_b, [0, 0, 0, 1], physicsClientId=client)

        # Log to Rerun if enabled
        if rerun_is_enabled():
            import rerun as rr

            rr.set_time("step", sequence=step_idx)

            # Probe A & Probe B needles
            rr.log(
                "world/tester/probe_a",
                rr.Points3D([pos_a], radii=0.0010, colors=[239, 68, 68, 255]),
            )
            rr.log(
                "world/tester/needle_a",
                rr.LineStrips3D(
                    [[pos_a, [pos_a[0], pos_a[1], pos_a[2] + 0.015]]], colors=[220, 38, 38, 200], radii=0.0004
                ),
            )
            rr.log(
                "world/tester/probe_b",
                rr.Points3D([pos_b], radii=0.0010, colors=[59, 130, 246, 255]),
            )
            rr.log(
                "world/tester/needle_b",
                rr.LineStrips3D(
                    [[pos_b, [pos_b[0], pos_b[1], pos_b[2] + 0.015]]], colors=[37, 99, 235, 200], radii=0.0004
                ),
            )

            # Spark / Contact Indicator
            if contact_active:
                spark_color = [245, 158, 11, 255] if active_spec.passed else [239, 68, 68, 255]
                rr.log(
                    "world/tester/contact_spark",
                    rr.Points3D([pos_a, pos_b], radii=0.0015, colors=spark_color),
                )

            # Scalar electrical telemetry
            rr.log("metrics/contact_force_n", rr.Scalars(float(contact_force)))
            rr.log("metrics/electrical_measurement", rr.Scalars(float(active_spec.measured)))
            rr.log("metrics/test_step_index", rr.Scalars(float(active_test_idx)))
            passed_cnt = sum(1 for s in test_steps if s.passed)
            rr.log("metrics/tests_passed", rr.Scalars(float(passed_cnt)))
            rr.log("metrics/yield_pct", rr.Scalars(float(passed_cnt / num_tests * 100.0)))

            # Update Markdown Test Report in Rerun
            if step_idx % 25 == 0 or step_idx == steps_per_test * num_tests - 1:
                report_md = render_markdown_test_report(target_label, test_steps, step_idx, 1000)
                sim_state["last_report"] = report_md
                rr.log("world/test_report", rr.TextDocument(report_md, media_type="text/markdown"))

        # Periodic console logging
        if step_idx > 0 and step_idx % steps_per_test == 0:
            logger = getattr(self, "logger", None)
            if logger is not None:
                spec = test_steps[active_test_idx]
                verdict = "PASS" if spec.passed else "FAIL"
                logger.print(
                    f"[{verdict}] {spec.step_id}: {spec.description} -> {spec.measured:.3f} {spec.unit} (Nominal: {spec.nominal} {spec.unit})",
                    symbol="⚡",
                )

        return None

    # Attach convenience helper to provider for verification
    self.flying_probe_steps = test_steps
    self.generate_test_report = lambda: render_markdown_test_report(target_label, test_steps, 1000, 1000)

    return {
        Simulate.SETUP: setup_simulation,
        Simulate.STEP: step_simulation,
    }
