"""Fluid motor configuration data model."""

from pydantic import BaseModel, Field


class FluidMotorConfig(BaseModel):
    """Pydantic model representing fluid motor configuration."""

    target_omega: float = Field(default=15.0, description="Target motor speed/angular velocity")
    max_force: float = Field(default=10.0, description="Maximum motor force/torque limit")
