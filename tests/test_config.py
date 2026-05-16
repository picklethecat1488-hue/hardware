"""Contains Configurator unit tests."""

from __future__ import annotations

import pytest
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

    def add(self, other: VectorStub) -> VectorStub:
        """Add two vector stubs (method version)."""
        return self.__add__(other)

    def sub(self, other: VectorStub) -> VectorStub:
        """Subtract another vector stub (method version)."""
        return self.__sub__(other)

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


class StubPath:
    """Stub path object that provides a fixed position for testing."""

    def __init__(self, position: VectorStub):
        """Initialize the stub path with a fixed position."""
        self._position = position

    def val(self):
        """Return itself as a value wrapper."""
        return self

    def positionAt(self, off):
        """Return the fixed position regardless of offset."""
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

    def build_part(self, name, right=False, tube_only=False):
        """Return a stub entity representing a built part."""
        center = VectorStub(0, 0, 2) if not right else VectorStub(10, 0, 2)
        return StubEntity(center=center)

    def create_wire(self, name):
        """Return a stub path for the named part."""
        return StubPath(VectorStub(0, 0, 0))

    def build_clamp_bed(self, name, idx, offset_deg=0.0):
        """Capture clamp bed angle candidates and return a stub entity."""
        self.clamp_calls.append(offset_deg)
        return StubEntity(center=VectorStub(offset_deg, 0, 0), volume=0)

    def build_text(self, name, right=False, offset_deg=0.0, font_path=None):
        """Capture text placement angle candidates and return a stub entity."""
        self.text_calls.append(offset_deg)
        return StubEntity(center=VectorStub(offset_deg, 0, 0), volume=0)


class TestConfig:
    """Configurator unit tests."""

    @pytest.fixture(autouse=True)
    def patch_cq_vector(self, monkeypatch):
        """Patch CadQuery Vector with a stub vector during tests."""
        monkeypatch.setattr(config.cq, "Vector", VectorStub)
        yield

    def test_get_part_position_prefers_closer_midpoint(self):
        """Verify get_part_position chooses the closer midpoint position."""
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

        monkeypatch.setattr(config.np, "arange", lambda start, stop, step: [0.0, 90.0, 180.0])

        configurator.config_clamp("driver")

        assert dummy_config.clamp_positions["driver"][1][1] == 0.0
        assert builder.clamp_calls[:3] == [0.0, 90.0, 180.0]

    def test_config_text_logo_updates_offset_for_best_angle(self, monkeypatch):
        """Ensure text logo configuration chooses the best angle offset."""
        dummy_config = DummyConfig()
        builder = StubBuilder(dummy_config)
        configurator = Configurator(builder=builder, config=dummy_config, logger=None)

        monkeypatch.setattr(config.np, "arange", lambda start, stop, step: [0.0, 90.0, 180.0])

        configurator.config_text_logo("driver")

        assert dummy_config.logo_text_positions["driver"][1] == 0.0
        assert builder.text_calls[:3] == [0.0, 90.0, 180.0]
