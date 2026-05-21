"""Contains Configurator unit tests."""

from __future__ import annotations

import pytest
from typing import Any
import threading
import config
from config import Configurator


class VectorStub:
    """Simple 3D vector stub used for build123d test replacement."""

    def __init__(self, X: float, Y: float, Z: float):
        """Initialize a vector stub with coordinates."""
        self.X = float(X)
        self.Y = float(Y)
        self.Z = float(Z)

    @property
    def length(self) -> float:
        """Return the Euclidean length of the vector."""
        return (self.X**2 + self.Y**2 + self.Z**2) ** 0.5

    def __add__(self, other: VectorStub) -> VectorStub:
        """Add two vector stubs."""
        return VectorStub(self.X + other.X, self.Y + other.Y, self.Z + other.Z)

    def __sub__(self, other: VectorStub) -> VectorStub:
        """Subtract another vector stub."""
        return VectorStub(self.X - other.X, self.Y - other.Y, self.Z - other.Z)

    def __mul__(self, other: float | VectorStub) -> VectorStub:
        """Multiply vector stub by a scalar or transform a vector."""
        if isinstance(other, (int, float)):
            return VectorStub(self.X * other, self.Y * other, self.Z * other)
        # Treating multiplication by a location stub as a simple translation for tests
        return VectorStub(self.X + other.X, self.Y + other.Y, self.Z + other.Z)

    def add(self, other: VectorStub) -> VectorStub:
        """Add two vector stubs (method version)."""
        return self.__add__(other)

    def sub(self, other: VectorStub) -> VectorStub:
        """Subtract another vector stub (method version)."""
        return self.__sub__(other)

    def normalized(self) -> VectorStub:
        """Return a normalized vector stub."""
        l = self.length
        return VectorStub(self.X / l, self.Y / l, self.Z / l) if l > 0 else self

    def cross(self, other: VectorStub) -> VectorStub:
        """Return the cross product of two vector stubs."""
        return VectorStub(
            self.Y * other.Z - self.Z * other.Y,
            self.Z * other.X - self.X * other.Z,
            self.X * other.Y - self.Y * other.X,
        )

    def dot(self, other: VectorStub) -> float:
        """Return the dot product of two vector stubs."""
        return self.X * other.X + self.Y * other.Y + self.Z * other.Z

    def get_angle(self, other: VectorStub) -> float:
        """Return a stub angle."""
        return 0.0

    def __eq__(self, other: object) -> bool:
        """Compare two vector stubs for equality."""
        if not isinstance(other, VectorStub):
            return False
        return (self.X, self.Y, self.Z) == (other.X, other.Y, other.Z)

    def __repr__(self) -> str:
        """Return a repr string for the vector stub."""
        return f"VectorStub({self.X}, {self.Y}, {self.Z})"


class StubBoundBox:
    """Stub for build123d BoundBox."""

    def __init__(self, min_vec: VectorStub, max_vec: VectorStub):
        """Initialize a stub bounding box with bounds."""
        self.min = min_vec
        self.max = max_vec


class StubPart:
    """Minimal stub entity that mimics a build123d Part for test purposes."""

    def __init__(self, center: VectorStub, volume: float = 0.0):
        """Initialize a stub entity with center and volume."""
        self._center = center
        self._volume = float(volume)

    def center(self) -> VectorStub:
        """Return the stored center vector."""
        return self._center

    def volume(self) -> float:
        """Return the stored volume."""
        return self._volume

    def bounding_box(self) -> StubBoundBox:
        """Return a stub bounding box."""
        return StubBoundBox(VectorStub(-1, -1, -1), VectorStub(1, 1, 1))

    def __and__(self, other: StubPart):
        """Mimic algebraic intersection."""
        return self

    def solids(self) -> list[StubPart]:
        """Return a list of solid stubs."""
        return [self] if self._volume > 0 else []


class StubWire:
    """Stub wire object that provides a fixed position for testing."""

    def __init__(self, position: VectorStub, length: float = 0.0):
        """Initialize the stub path with a fixed position and length."""
        self._position = position
        self.length = float(length)

    def position_at(self, off):
        """Return the fixed position regardless of offset."""
        return self._position

    def location_at(self, off):
        """Return a stub location."""
        return self._position


class DummyConfig:
    """Dummy configuration object used by configurator tests."""

    def __init__(self):
        """Initialize the dummy configuration values."""
        self.names = ["driver", "passenger"]
        self.clamp_positions = {"driver": [None, (0.5, 10.0), None], "passenger": [None, (0.5, 10.0), None]}
        self.logo_text_positions = {"driver": (0.4, 10.0), "passenger": (0.4, 10.0)}
        self.clamp_diameters = [6.0, 6.0, 6.0]

    def model_dump(self, by_alias=True):
        """Return an empty model dump for the dummy config."""
        return {}


class StubBuilder:
    """Stub builder used by configurator tests to capture call parameters."""

    def __init__(self, config_obj):
        """Initialize the stub builder with a dummy config object."""
        self.config = config_obj
        self.clamp_calls = []
        self.text_calls = []
        self._lock = threading.Lock()

    def build_part(self, name, right=False, tube_only=False) -> Any:
        """Return a stub entity representing a built part."""
        center = VectorStub(0, 0, 2) if not right else VectorStub(10, 0, 2)
        return StubPart(center=center)

    def create_wire(self, name) -> Any:
        """Return a stub path for the named part."""
        return StubWire(VectorStub(0, 0, 0), length=400.0)

    def build_clamp_bed(self, name, idx, offset_deg=0.0, joint_space=0) -> Any:
        """Capture clamp bed angle candidates and return a stub entity."""
        with self._lock:
            self.clamp_calls.append(offset_deg)
        return StubPart(center=VectorStub(offset_deg, 0, 0), volume=0)

    def build_text(self, name, text=None, right=False, offset_deg=0.0, font_path=None) -> Any:
        """Capture text placement angle candidates and return a stub entity."""
        with self._lock:
            self.text_calls.append(offset_deg)
        return StubPart(center=VectorStub(offset_deg, 0, 0), volume=0)


class TestConfig:
    """Configurator unit tests."""

    @pytest.fixture(autouse=True)
    def patch_build123d(self, monkeypatch):
        """Patch build123d components with stubs during tests."""
        monkeypatch.setattr(config, "Vector", VectorStub)
        monkeypatch.setattr(config, "Part", StubPart)
        monkeypatch.setattr(config, "Wire", StubWire)
        monkeypatch.setattr(config, "BoundBox", StubBoundBox)
        yield

    def test_get_part_position_prefers_closer_midpoint(self):
        """Verify get_part_position identifies the arc peak via local frame transformation."""
        dummy_config = DummyConfig()
        builder = StubBuilder(dummy_config)
        configurator = Configurator(builder=builder, config=dummy_config, logger=None)
        path: Any = StubWire(VectorStub(0, 0, 0))
        tube: Any = builder.build_part("driver")

        result = configurator.get_part_position(tube, path, 0.4)

        assert result == VectorStub(0, 0, 3.0)

    def test_config_clamp_updates_offset_for_best_angle(self, monkeypatch):
        """Ensure clamp configuration chooses the best angle offset."""
        dummy_config = DummyConfig()
        builder = StubBuilder(dummy_config)
        configurator = Configurator(builder=builder, config=dummy_config, logger=None)

        monkeypatch.setattr(configurator, "angle_window", lambda angle, radius, step: [0.0, 90.0, 180.0])

        configurator.config_clamp("driver")

        assert dummy_config.clamp_positions["driver"][1][1] == 0.0
        # Verify that the coarse scan (range(0, 360, 10)) and fine scan (mocked) were executed.
        assert len(builder.clamp_calls) > 30
        assert 0.0 in builder.clamp_calls

    def test_config_text_logo_updates_offset_for_best_angle(self, monkeypatch):
        """Ensure text logo configuration chooses the best angle offset."""
        dummy_config = DummyConfig()
        builder = StubBuilder(dummy_config)
        configurator = Configurator(builder=builder, config=dummy_config, logger=None)

        monkeypatch.setattr(configurator, "angle_window", lambda angle, radius, step: [0.0, 90.0, 180.0])

        configurator.config_text_logo("driver")

        assert dummy_config.logo_text_positions["driver"][1] == 0.0
        # Verify that the coarse scan (range(0, 360, 10)) and fine scan (mocked) were executed.
        assert len(builder.text_calls) > 30
        assert 0.0 in builder.text_calls
