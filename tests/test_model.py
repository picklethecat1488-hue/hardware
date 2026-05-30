"""Unit tests for the model caching utilities."""

import math
import yaml
import numpy as np
import pytest
from pathlib import Path
from model import method_cache, AppConfig, TubeConfig, load_measurements


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
        return AppConfig()

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
                config.tube.P[inlet_key],
                # Inlet end
                config.tube.P[inlet_key] + config.tube.V[inlet_key] * config.tube.clamp_lengths[0],
                # Outlet start
                config.tube.P[outlet_key],
                # Outlet end
                config.tube.P[outlet_key] + config.tube.V[outlet_key] * config.tube.clamp_lengths[-1],
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

    def test_bounding_box(self, config):
        """Test the bounding box part."""
        bound_box = config.bound_box
        assert bound_box.volume == pytest.approx(129926381.75)

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

    def test_load_measurements_with_subkey(self, tmp_path):
        """Verify loading measurements using the 'path:key' syntax."""
        data = {"v1": {"p1": [1, 1, 1]}, "v2": {"p1": [2, 2, 2]}}
        yml_file = tmp_path / "multi_model.yml"
        with open(yml_file, "w") as f:
            yaml.dump(data, f)

        measurements = load_measurements(f"{yml_file}:v2")
        assert measurements["p1"][0] == 2

    def test_measurements_list_format_conversion(self, tmp_path):
        """Verify that list-formatted measurements are converted to 1-based integer keys."""
        data = [[10, 10, 10], [20, 20, 20]]
        yml_file = tmp_path / "list.yml"
        with open(yml_file, "w") as f:
            yaml.dump(data, f)

        measurements = load_measurements(str(yml_file))
        assert measurements[1][0] == 10
        assert measurements[2][0] == 20

    def test_z_correction_with_mixed_keys(self, tmp_path):
        """Verify Z-correction applies to both numeric and string keys."""
        data = {1: [0, 0, 100], 6: [0, 0, 100]}
        yml_file = tmp_path / "corr.yml"
        with open(yml_file, "w") as f:
            yaml.dump(data, f)

        # Default min diameter is 63.5, so correction is -31.75
        # Test override in tube config
        config = AppConfig(tube={"measurements_path": str(yml_file)}, _env_file=None)  # type: ignore
        measurements = config.tube.measurements
        assert measurements[1][2] == pytest.approx(100)
        assert measurements[6][2] == pytest.approx(100 - 31.75)

        # Test fallback to AppConfig default
        config_fallback = AppConfig(measurements_path=str(yml_file), _env_file=None)  # type: ignore
        assert config_fallback.tube.measurements_path == str(yml_file)
        assert config_fallback.tube.measurements[6][2] == pytest.approx(100 - 31.75)
