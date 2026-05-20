"""Unit tests for the model caching utilities."""

import pytest
from model import method_cache


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
