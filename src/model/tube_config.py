"""Tube geometry configuration and measurement processing logic."""

from typing import Any, Literal, cast, Optional
from functools import cached_property
from pathlib import Path
import numpy as np
from pydantic import BaseModel, Field
from build123d import Vector
from .text_args import TextArgs
from .utils import load_measurements


class TubeConfig(BaseModel):
    """Tube and part configuration."""

    measurements_path: Optional[str] = Field(
        default=None,
        description="Optional override for the measurements YAML file path. Defaults to AppConfig.measurements_path.",
    )

    wall_thickness: float = Field(default=3.0, description="Wall thickness ~3mm", gt=0)
    clamp_diameters: list[float] = Field(
        default_factory=lambda: [63.5, 76.2, 63.5],
        description='Inlet and outlet diameters, 2.5", inner clamp diameter 3"',
        min_length=3,
    )
    clamp_lengths: list[float] = Field(
        default_factory=lambda: [50.4, 25.4, 50.4],
        description='Inlet and outlet clamp length 2", inner clamp length 1"',
        min_length=3,
    )
    clamp_positions: dict[str, list[tuple[float, float] | None]] = Field(
        default_factory=lambda: {"driver": [None, (0.5, 0), None], "passenger": [None, (0.5, 0), None]},
        description="The clamp positions, each one is a tuple of path offset and angle offset",
    )
    clamp_space: float = Field(default=15, description="Space between clamps on each side", ge=0)
    joint_radius: float = Field(default=1.5, description="The radius of the circular lap joint features", gt=0)
    joint_space: float = Field(default=0.3, description="The clearance added to the recess side of the lap joint", ge=0)
    names: list[Literal["driver", "passenger"]] = Field(
        default_factory=lambda: ["driver", "passenger"],
        description="The part names, driver and passenger",
    )
    logo_text_args: TextArgs = Field(
        default_factory=TextArgs,
        description="The logo text arguments",
    )
    logo_text_positions: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {"driver": (0.4, 0), "passenger": (0.4, 0)},
        description="The logo text offset, pathwise and anglewise",
    )

    @cached_property
    def measurements(self) -> dict[int, np.ndarray]:
        """Return raw measurement points with Z-axis corrections applied."""
        if self.measurements_path is None:
            raise ValueError("measurements_path is not set.")

        raw = load_measurements(cast(str, self.measurements_path))
        p = {int(k): v for k, v in raw.items() if isinstance(k, int) or (isinstance(k, str) and k.isdigit())}

        for idx in [3, 6, 9, 10]:
            if idx in p:
                p[idx][2] = p[idx][2] - min(self.clamp_diameters) / 2
        return cast(dict[int, np.ndarray], p)

    def _ndarray2vec(self, arr: np.ndarray) -> Vector:
        """Convert a numpy array to a build123d Vector."""
        return Vector(X=float(arr[0]), Y=float(arr[1]), Z=float(arr[2]))

    @cached_property
    def P(self) -> dict[str, Vector]:
        """Get position vectors for all manifold endpoints."""
        return {
            "driver_inlet": self._ndarray2vec(self.measurements[6]),
            "driver_outlet": self._ndarray2vec(self.measurements[9]),
            "passenger_inlet": self._ndarray2vec(self.measurements[3]),
            "passenger_outlet": self._ndarray2vec(self.measurements[10]),
        }

    @cached_property
    def V(self) -> dict[str, Vector]:
        """Get direction vectors for all manifold endpoints."""

        def dir_vector(start, end):
            v = np.array(end) - np.array(start)
            return v / np.linalg.norm(v)

        return {
            "driver_inlet": self._ndarray2vec(dir_vector(self.measurements[7], self.measurements[8])),
            "driver_outlet": Vector(X=-1, Y=0, Z=0),
            "passenger_inlet": self._ndarray2vec(dir_vector(self.measurements[5], self.measurements[4])),
            "passenger_outlet": Vector(X=1, Y=0, Z=0),
        }
