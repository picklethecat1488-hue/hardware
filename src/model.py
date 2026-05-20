"""Data models and configuration for the exhaust manifolds project."""

from pathlib import Path
from typing import Any
from functools import cached_property
import numpy as np
import yaml
from pydantic_changedetect import ChangeDetectionMixin
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class AppConfig(ChangeDetectionMixin, BaseSettings):
    """Application build configuration."""

    # Project name
    project_name: str = "exhaust_manifolds"

    # Build version
    ver: int = 4

    # The part x boundaries
    x_bounds: list[float] = [145, 950]

    # The part y boundaries
    y_bounds: list[float] = [-32, 390]

    # The part bounds
    z_bounds: list[float] = [145, 530]

    # Wall thickness ~3mm
    wall_thickness: float = 3.0

    # Inlet and outlet diameters, 2.5", inner clamp diameter 3"
    clamp_diameters: list[float] = [63.5, 76.2, 63.5]

    # Inlet and outlet clamp length 2", inner clamp length 1"
    clamp_lengths: list[float] = [50.4, 25.4, 50.4]

    # The clamp positions, each one is a tuple of path offset and angle offset
    clamp_positions: dict[str, list[tuple[float, float] | None]] = {
        "driver": [None, (0.5, 0), None],
        "passenger": [None, (0.5, 0), None],
    }

    # Space between clamps on each side
    clamp_space: float = 15

    # The radius of the circular lap joint features
    joint_radius: float = 1.5

    # The clearance added to the recess side of the lap joint
    joint_space: float = 0.3

    # The part names, driver and passenger
    names: list[Literal["driver", "passenger"]] = ["driver", "passenger"]

    # Private attribute to store raw measurements loaded from file
    _measurements: list[list[float]] = []

    # The logo text arguments
    logo_text_args: dict[str, Any] = {
        "fontsize": 10,
        "distance": 3,
        "fontPath": "Sans",
        "halign": "center",
        "valign": "center",
        "kind": "bold",
    }

    # The logo text offset, pathwise and anglewise
    logo_text_positions: dict[str, tuple[float, float]] = {
        "driver": (0.4, 0),
        "passenger": (0.4, 0),
    }

    # Diagram export options
    diagram_options: dict[str, Any] = {
        "showAxes": False,
        "strokeWidth": 3,
        "strokeColor": (0, 0, 0),
        "projectionDir": (1, 1, 1),
        "width": 1024,
        "height": 1024,
    }

    # Distance between manifold assemblies in the diagram
    diagram_part_offset: int = 60

    # Distance between exploded halves in the diagram
    diagram_part_dist: int = 120

    # Distance of the labels from the parts in the diagram
    diagram_label_dist: int = 120

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="APP_", alias_generator=str.upper, populate_by_name=True
    )

    def __init__(self, **kwargs):
        """Initialize the config and load measurements from YAML."""
        super().__init__(**kwargs)
        yml_path = Path(__file__).parent / "measurements.yml"
        if yml_path.exists():
            with open(yml_path, "r") as f:
                try:
                    self._measurements = yaml.safe_load(f)
                except yaml.YAMLError:
                    raise ValueError("missing or invalid measurements.yml")

    @cached_property
    def measurements(self):
        """Return raw measurement points."""
        p = {}
        for idx, item in enumerate(self._measurements):
            p[idx + 1] = np.array(item)
        return p
