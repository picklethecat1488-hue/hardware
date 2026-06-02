"""Valve actuator limiter configuration and measurement logic."""

from typing import Optional

from pydantic import BaseModel, Field


class ValveActuatorLimiterConfig(BaseModel):
    """Configuration settings for the valve actuator limiter."""

    measurements_path: Optional[str] = Field(
        default=None,
        description="Optional override for the measurements YAML file path.",
    )

    base_thickness: float = Field(default=5.0, description="The thickness of the limiter plate base.", gt=0)
