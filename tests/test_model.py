"""Unit tests for the model caching utilities."""

import math
import yaml
import numpy as np
import pytest
from pathlib import Path
from model import method_cache, AppConfig, load_measurements
from provider import ProviderManager


class MockService:
    """Helper class to test the method_cache decorator."""

    def __init__(self):
        """Initialize the mock service."""
        self.call_count = 0

    @method_cache(maxsize=2)
    def compute(self, *args, **kwargs):
        """Track how many times the method is executed."""
        self.call_count += 1
        return args, kwargs


class TestModel:
    """Test suite for the model caching utilities."""

    @pytest.fixture(scope="class")
    def config(self):
        """Return the app config fixture."""
        config = AppConfig()
        # Bootstrapping the manager populates the 'exhaust_manifolds' attribute on the config instance
        ProviderManager(config)
        return config

    def test_measurements(self, config):
        """Validate key manifold measurement relationships."""

        def dist(p1, p2):
            """Compute the 2D distance between two points."""
            x1, y1, _ = p1
            x2, y2, _ = p2
            return round(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))

        def get_end_points(name):
            """Return the inlet and outlet endpoint locations for a part."""
            inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
            return (
                # Inlet start
                config.exhaust_manifolds.P[inlet_key],
                # Inlet end
                config.exhaust_manifolds.P[inlet_key]
                + config.exhaust_manifolds.V[inlet_key] * config.exhaust_manifolds.clamp_lengths[0],
                # Outlet start
                config.exhaust_manifolds.P[outlet_key],
                # Outlet end
                config.exhaust_manifolds.P[outlet_key]
                + config.exhaust_manifolds.V[outlet_key] * config.exhaust_manifolds.clamp_lengths[-1],
            )

        driver_inlet_start, driver_inlet_end, driver_outlet_start, _ = get_end_points("driver")
        (
            passenger_inlet_start,
            passenger_inlet_end,
            passenger_outlet_start,
            _,
        ) = get_end_points("passenger")

        # Check dist between inlets
        assert dist(passenger_inlet_start, driver_inlet_start) == pytest.approx(231)
        assert round(driver_inlet_end.Z - driver_inlet_start.Z) == pytest.approx(12)

        # Check dist between outlets
        assert dist(driver_outlet_start, passenger_outlet_start) == pytest.approx(695)
        assert abs(round(passenger_inlet_end.Z - passenger_inlet_start.Z)) == pytest.approx(0)

        # Check dist between driver inlet and outlet
        assert dist(driver_inlet_start, driver_outlet_start) == pytest.approx(315)
        assert round(driver_outlet_start.Z - driver_inlet_start.Z) == pytest.approx(140)

        # Check dist between passenger inlet and outlet
        assert dist(passenger_inlet_start, passenger_outlet_start) == pytest.approx(485)
        assert round(passenger_outlet_start.Z - passenger_inlet_start.Z) == pytest.approx(170)

    def test_method_cache_basic_hit(self):
        """Verify that multiple calls with the same arguments return a cached result."""
        service = MockService()

        # First call: cache miss
        result1 = service.compute(1, 2, key="value")
        assert service.call_count == 1

        # Second call: cache hit
        result2 = service.compute(1, 2, key="value")
        assert service.call_count == 1
        assert result1 == result2

    def test_method_cache_per_instance_isolation(self):
        """Verify that caches are unique to each instance to prevent state leakage."""
        s1 = MockService()
        s2 = MockService()

        s1.compute("data")
        s2.compute("data")

        assert s1.call_count == 1
        assert s2.call_count == 1

    def test_method_cache_lru_eviction(self):
        """Verify that the cache respects maxsize and evicts the least recently used item."""
        service = MockService()

        service.compute(1)  # Cache: [1]
        service.compute(2)  # Cache: [1, 2]
        service.compute(3)  # Cache: [2, 3], (1 evicted)

        assert service.call_count == 3

        # Calling 1 again should be a miss because it was the oldest
        service.compute(1)
        assert service.call_count == 4

        # Calling 3 again should be a hit
        service.compute(3)
        assert service.call_count == 4

    def test_method_cache_kwargs_sorting(self):
        """Verify that keyword argument order does not affect the cache key."""
        service = MockService()

        service.compute(a=1, b=2)
        service.compute(b=2, a=1)

        assert service.call_count == 1

    def test_load_measurements_from_file(self, tmp_path):
        """Verify basic measurement loading from a YAML file."""
        data = {"point_a": [10.0, 20.0, 30.0]}
        yml_file = tmp_path / "measurements.yml"
        with open(yml_file, "w") as f:
            yaml.dump(data, f)

        measurements = load_measurements(str(yml_file))
        assert "point_a" in measurements
        assert np.array_equal(measurements["point_a"], np.array([10.0, 20.0, 30.0]))

    def test_measurements_list_format_conversion(self, tmp_path):
        """Verify that list-formatted measurements are converted to 1-based integer keys."""
        data = [[10, 10, 10], [20, 20, 20]]
        yml_file = tmp_path / "list.yml"
        with open(yml_file, "w") as f:
            yaml.dump(data, f)

        measurements = load_measurements(str(yml_file))
        assert measurements[1][0] == 10
        assert measurements[2][0] == 20

    def test_load_signed_float_measurements(self, tmp_path):
        """Verify that signed floating point measurements are loaded correctly."""
        data = {"offset": -15.5, "scale": 1.2}
        yml_file = tmp_path / "floats.yml"
        with open(yml_file, "w") as f:
            yaml.dump(data, f)

        measurements = load_measurements(str(yml_file))
        assert measurements["offset"] == -15.5
        assert measurements["scale"] == 1.2

    def test_load_2d_point_measurements(self, tmp_path):
        """Verify that 2D point measurements are loaded correctly."""
        data = {"point_2d": [1.5, 2.5]}
        yml_file = tmp_path / "points2d.yml"
        with open(yml_file, "w") as f:
            yaml.dump(data, f)

        measurements = load_measurements(str(yml_file))
        assert "point_2d" in measurements
        assert np.array_equal(measurements["point_2d"], np.array([1.5, 2.5]))
