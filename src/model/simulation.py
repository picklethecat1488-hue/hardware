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
