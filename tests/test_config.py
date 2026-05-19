"""Contains Configurator unit tests."""

from __future__ import annotations

import pytest
import threading
import config
from config import Configurator


class VectorStub:
    """Simple 3D vector stub used for CadQuery test replacement."""

    def __init__(self, x: float, y: float, z: float):
        """Initialize a vector stub with coordinates."""
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    @property
    def Length(self) -> float:
        """Return the Euclidean length of the vector."""
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5

    def __add__(self, other: VectorStub) -> VectorStub:
        """Add two vector stubs."""
        return VectorStub(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: VectorStub) -> VectorStub:
        """Subtract another vector stub."""
        return VectorStub(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, other: float | VectorStub) -> VectorStub:
        """Multiply vector stub by a scalar or transform a vector."""
        if isinstance(other, (int, float)):
            return VectorStub(self.x * other, self.y * other, self.z * other)
        # Treating multiplication by a location stub as a simple translation for tests
        return VectorStub(self.x + other.x, self.y + other.y, self.z + other.z)

    def add(self, other: VectorStub) -> VectorStub:
        """Add two vector stubs (method version)."""
        return self.__add__(other)

    def sub(self, other: VectorStub) -> VectorStub:
        """Subtract another vector stub (method version)."""
        return self.__sub__(other)

    def normalized(self) -> VectorStub:
        """Return a normalized vector stub."""
        length = self.Length
        return VectorStub(self.x / length, self.y / length, self.z / length) if length > 0 else self

    def cross(self, other: VectorStub) -> VectorStub:
        """Return the cross product of two vector stubs."""
        return VectorStub(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def dot(self, other: VectorStub) -> float:
        """Return the dot product of two vector stubs."""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def getAngle(self, other: VectorStub) -> float:
        """Return a stub angle."""
        return 0.0

    def __eq__(self, other: object) -> bool:
        """Compare two vector stubs for equality."""
        if not isinstance(other, VectorStub):
            return False
        return (self.x, self.y, self.z) == (other.x, other.y, other.z)

    def __repr__(self) -> str:
        """Return a repr string for the vector stub."""
        return f"VectorStub({self.x}, {self.y}, {self.z})"


class StubBoundingBox:
    """Stub for CadQuery BoundingBox."""

    def __init__(
        self,
        xmin: float = -1.0,
        xmax: float = 1.0,
        ymin: float = -1.0,
        ymax: float = 1.0,
        zmin: float = -1.0,
        zmax: float = 1.0,
    ):
        """Initialize a stub bounding box with bounds."""
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax
        self.zmin = zmin
        self.zmax = zmax


class StubEntity:
    """Minimal stub entity that mimics a CadQuery part for test purposes."""

    def __init__(self, center: VectorStub, volume: float = 0.0):
        """Initialize a stub entity with center and volume."""
        self._center = center
        self._volume = float(volume)

    def val(self) -> StubEntity:
        """Return itself as a value wrapper."""
        return self

    def Center(self) -> VectorStub:
        """Return the stored center vector."""
        return self._center

    def Volume(self) -> float:
        """Return the stored volume."""
        return self._volume

    def BoundingBox(self) -> StubBoundingBox:
        """Return a stub bounding box."""
        return StubBoundingBox()

    def intersect(self, other):
        """Return a new stub entity representing an intersection result."""
        return StubEntity(center=self._center, volume=self._volume)

    def isInside(self, point: VectorStub) -> bool:
        """Stub for geometric containment check."""
        return True

    def Solids(self) -> list[StubEntity]:
        """Return a list of solid stubs."""
        return [self] if self._volume > 0 else []

    def distance(self, other):
        """Compute the distance between two objects."""
        return (self._center - other._center).Length


class StubPath:
    """Stub path object that provides a fixed position for testing."""

    def __init__(self, position: VectorStub, length: float = 0.0):
        """Initialize the stub path with a fixed position and length."""
        self._position = position
        self._length = float(length)

    def val(self):
        """Return itself as a value wrapper."""
        return self

    def positionAt(self, off):
        """Return the fixed position regardless of offset."""
        return self._position

    def locationAt(self, off):
        """Return a stub location (identity translation)."""
        return VectorStub(0, 0, 0)

    def tangentAt(self, off):
        """Return a fixed tangent vector."""
        return VectorStub(0, 1, 0)

    def Length(self):
        """Return a fixed length."""
        return self._length


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

    def build_part(self, name, right=False, tube_only=False):
        """Return a stub entity representing a built part."""
        center = VectorStub(0, 0, 2) if not right else VectorStub(10, 0, 2)
        return StubEntity(center=center)

    def create_wire(self, name):
        """Return a stub path for the named part."""
        return StubPath(VectorStub(0, 0, 0), length=400.0)

    def build_clamp_bed(self, name, idx, offset_deg=0.0, joint_space=0):
        """Capture clamp bed angle candidates and return a stub entity."""
        with self._lock:
            self.clamp_calls.append(offset_deg)
        return StubEntity(center=VectorStub(offset_deg, 0, 0), volume=0)

    def build_text(self, name, text=None, right=False, offset_deg=0.0, font_path=None):
        """Capture text placement angle candidates and return a stub entity."""
        with self._lock:
            self.text_calls.append(offset_deg)
        return StubEntity(center=VectorStub(offset_deg, 0, 0), volume=0)


class TestConfig:
    """Configurator unit tests."""

    @pytest.fixture(autouse=True)
    def patch_cq_vector(self, monkeypatch):
        """Patch CadQuery Vector with a stub vector during tests."""
        monkeypatch.setattr(config.cq, "Vector", VectorStub)
        monkeypatch.setattr(config.cq, "Location", lambda x=VectorStub(0, 0, 0): x)
        monkeypatch.setattr(config.cq, "Plane", lambda **k: None)
        yield

    def test_get_part_position_prefers_closer_midpoint(self):
        """Verify get_part_position identifies the arc peak via local frame transformation."""
        dummy_config = DummyConfig()
        builder = StubBuilder(dummy_config)
        configurator = Configurator(builder=builder, config=dummy_config, logger=None)
        path = StubPath(VectorStub(0, 0, 0))
        tube = builder.build_part("driver")

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
