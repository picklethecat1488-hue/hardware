"""Contains Configurator unit tests."""

from __future__ import annotations

import pytest
import config
from config import Configurator


class VectorStub:
    def __init__(self, x: float, y: float, z: float):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    @property
    def Length(self) -> float:
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5

    def __add__(self, other: VectorStub) -> VectorStub:
        return VectorStub(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: VectorStub) -> VectorStub:
        return VectorStub(self.x - other.x, self.y - other.y, self.z - other.z)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VectorStub):
            return False
        return (self.x, self.y, self.z) == (other.x, other.y, other.z)

    def __repr__(self) -> str:
        return f"VectorStub({self.x}, {self.y}, {self.z})"


class StubEntity:
    def __init__(self, center: VectorStub, volume: float = 0.0):
        self._center = center
        self._volume = float(volume)

    def val(self) -> StubEntity:
        return self

    def Center(self) -> VectorStub:
        return self._center

    def Volume(self) -> float:
        return self._volume

    def intersect(self, other):
        return StubEntity(center=self._center, volume=self._volume)


class StubPath:
    def __init__(self, position: VectorStub):
        self._position = position

    def val(self):
        return self

    def positionAt(self, off):
        return self._position


class DummyConfig:
    def __init__(self):
        self.names = ["driver", "passenger"]
        self.clamp_positions = {"driver": [None, (0.5, 10.0), None], "passenger": [None, (0.5, 10.0), None]}
        self.logo_text_positions = {"driver": (0.4, 10.0), "passenger": (0.4, 10.0)}

    def model_dump(self, by_alias=True):
        return {}


class StubBuilder:
    def __init__(self, config_obj):
        self.config = config_obj
        self.clamp_calls = []
        self.text_calls = []

    def build_part(self, name, right=False, tube_only=False):
        center = VectorStub(0, 0, 2) if not right else VectorStub(10, 0, 2)
        return StubEntity(center=center)

    def create_wire(self, name):
        return StubPath(VectorStub(0, 0, 0))

    def build_clamp_bed(self, name, idx, offset_deg=0.0):
        self.clamp_calls.append(offset_deg)
        return StubEntity(center=VectorStub(offset_deg, 0, 0), volume=0)

    def build_text(self, name, right=False, offset_deg=0.0):
        self.text_calls.append(offset_deg)
        return StubEntity(center=VectorStub(offset_deg, 0, 0), volume=0)


@pytest.fixture(autouse=True)
def patch_cq_vector(monkeypatch):
    monkeypatch.setattr(config.cq, "Vector", VectorStub)
    yield


def test_get_part_position_prefers_closer_midpoint():
    dummy_config = DummyConfig()
    builder = StubBuilder(dummy_config)
    configurator = Configurator(builder=builder, config=dummy_config, logger=None)
    path = StubPath(VectorStub(0, 0, 0))

    result = configurator.get_part_position("driver", path, 0.4)

    assert result == VectorStub(0, 0, 3.0)


def test_config_clamp_updates_offset_for_best_angle(monkeypatch):
    dummy_config = DummyConfig()
    builder = StubBuilder(dummy_config)
    configurator = Configurator(builder=builder, config=dummy_config, logger=None)

    monkeypatch.setattr(config.np, "arange", lambda start, stop, step: [0.0, 90.0, 180.0])

    configurator.config_clamp("driver")

    assert dummy_config.clamp_positions["driver"][1][1] == 0.0
    assert builder.clamp_calls == [0.0, 90.0, 180.0]


def test_config_text_logo_updates_offset_for_best_angle(monkeypatch):
    dummy_config = DummyConfig()
    builder = StubBuilder(dummy_config)
    configurator = Configurator(builder=builder, config=dummy_config, logger=None)

    monkeypatch.setattr(config.np, "arange", lambda start, stop, step: [0.0, 90.0, 180.0])

    configurator.config_text_logo("driver")

    assert dummy_config.logo_text_positions["driver"][1] == 0.0
    assert builder.text_calls == [0.0, 90.0, 180.0]
