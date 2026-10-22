"""Simulation models for flying probe automated acceptance testing and telemetry."""

from typing import List
from pydantic import BaseModel, Field


class FlyingProbeStepReportModel(BaseModel):
    """Rendered step result for flying probe verification report."""

    step_id: str = Field(description="Step identifier (e.g. FP-STEP-01)")
    description: str = Field(description="Step test description")
    net_name: str = Field(description="Tested net name")
    nominal_str: str = Field(description="Formatted nominal value with units")
    measured_str: str = Field(description="Formatted measured value with units")
    tolerance_str: str = Field(description="Formatted tolerance string")
    stimulus: str = Field(description="Applied stimulus and test method")
    verdict_str: str = Field(description="Rendered markdown verdict badge")


class FlyingProbeIsolationCheckModel(BaseModel):
    """Result of signal line isolation check against power and ground networks."""

    signal_net: str = Field(description="Signal net name")
    isolated_against: List[str] = Field(default_factory=list, description="Power and ground nets audited")
    passed: bool = Field(default=True, description="Whether signal is fully isolated from all power/ground")
    isolation_resistance_str: str = Field(default="> 100 MΩ", description="Measured isolation resistance")
    verdict_str: str = Field(default="🟢 **PASS**", description="Markdown verdict badge")


class FlyingProbeDiffPairCheckModel(BaseModel):
    """Result of differential pair compliance testing (USB, PCIe impedance, skew, and continuity)."""

    pair_name: str = Field(description="Differential pair name (e.g. USB, PCIE_TX0, PCIE_RX0)")
    positive_net: str = Field(description="Positive signal net name")
    negative_net: str = Field(description="Negative signal net name")
    target_diff_impedance_ohm: float = Field(description="Target differential impedance in Ohms")
    measured_diff_impedance_ohm: float = Field(description="Measured differential impedance in Ohms")
    tolerance_pct: float = Field(default=10.0, description="Allowed impedance tolerance percentage")
    skew_ps: float = Field(default=0.0, description="Measured intra-pair skew in picoseconds")
    max_skew_ps: float = Field(default=5.0, description="Maximum allowed intra-pair skew in picoseconds")
    passed: bool = Field(default=True, description="Whether differential pair meets compliance specifications")
    verdict_str: str = Field(default="🟢 **PASS**", description="Markdown verdict badge")


class FlyingProbeMutualCapCheckModel(BaseModel):
    """Result of mutual capacitance compliance testing simulating finger touch response."""

    channel_name: str = Field(description="Touch sensor channel identifier (e.g., CAP_CHAN0)")
    baseline_pf: float = Field(description="Baseline electrode mutual capacitance in pF")
    finger_touch_pf: float = Field(description="Capacitance under simulated finger proximity in pF")
    delta_c_pf: float = Field(description="Touch delta capacitance (touch - baseline) in pF")
    min_delta_c_pf: float = Field(default=1.5, description="Minimum detectable touch delta capacitance in pF")
    touch_detected: bool = Field(default=True, description="Whether touch threshold was crossed")
    passed: bool = Field(default=True, description="Whether capacitive touch channel configuration is compliant")
    verdict_str: str = Field(default="🟢 **PASS**", description="Markdown verdict badge")


class FlyingProbeReportModel(BaseModel):
    """Top-level report model passed to Jinja2 template for flying probe acceptance testing."""

    target_name: str = Field(description="Target board identifier")
    target_title: str = Field(description="Human-readable board title")
    timestamp: str = Field(description="UTC timestamp of execution")
    status_badge: str = Field(description="Overall verdict badge")
    passed_count: int = Field(description="Number of passed test steps")
    total_count: int = Field(description="Total number of test steps")
    yield_pct: float = Field(description="Acceptance yield percentage")
    current_step_idx: int = Field(description="Current completed test step index")
    total_sim_steps: int = Field(description="Total simulation time steps executed")
    steps: List[FlyingProbeStepReportModel] = Field(default_factory=list, description="Step results")
    signal_isolation_checks: List[FlyingProbeIsolationCheckModel] = Field(
        default_factory=list, description="Signal line power/ground isolation verification results"
    )
    all_signals_isolated: bool = Field(
        default=True, description="Whether all signal lines are verified non-shorted to power or ground"
    )
    diff_pair_checks: List[FlyingProbeDiffPairCheckModel] = Field(
        default_factory=list, description="Differential pair compliance audit results"
    )
    mutual_cap_checks: List[FlyingProbeMutualCapCheckModel] = Field(
        default_factory=list, description="Mutual capacitance touch simulation verification results"
    )
    all_diff_pairs_compliant: bool = Field(default=True, description="Whether all diff pairs meet compliance specs")
    all_mutual_caps_compliant: bool = Field(
        default=True, description="Whether all touch channels meet compliance specs"
    )
