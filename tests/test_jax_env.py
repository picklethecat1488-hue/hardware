"""Regression tests to verify JAX installation and functionality in the Conda environment."""

import pytest
import math
import jax
import jax.numpy as jnp


def test_jax_imports_and_version():
    """Verify that JAX can be imported and has a valid version."""
    assert jax.__version__ is not None
    assert jnp.arange(3) is not None


def test_jax_basic_arithmetic():
    """Verify basic vector arithmetic in JAX numpy."""
    x = jnp.array([1.0, 2.0, 3.0], dtype=jnp.float32)
    y = jnp.array([4.0, 5.0, 6.0], dtype=jnp.float32)
    z = x + y
    assert jnp.allclose(z, jnp.array([5.0, 7.0, 9.0], dtype=jnp.float32))


def test_jax_jit_compilation():
    """Verify that JAX JIT compiler is working correctly."""

    @jax.jit
    def simple_func(a, b):
        return a * b + 2.5

    val_a = jnp.array(3.0, dtype=jnp.float32)
    val_b = jnp.array(4.0, dtype=jnp.float32)
    res = simple_func(val_a, val_b)
    assert math.isclose(float(res), 14.5, rel_tol=1e-5)


def test_initialize_jax_environment_memory_and_preallocation(monkeypatch):
    """Verify initialize_jax_environment sets non-greedy memory fraction and disables preallocation."""
    import os
    from provider.utils import initialize_jax_environment

    monkeypatch.delenv("XLA_PYTHON_CLIENT_PREALLOCATE", raising=False)
    monkeypatch.delenv("XLA_PYTHON_CLIENT_MEM_FRACTION", raising=False)

    initialize_jax_environment()

    assert os.environ.get("XLA_PYTHON_CLIENT_PREALLOCATE") == "false"
    assert os.environ.get("XLA_PYTHON_CLIENT_MEM_FRACTION") == "0.20"


def test_initialize_jax_environment_dynamic_device_id(monkeypatch):
    """Verify initialize_jax_environment dynamically configures CUDA_VISIBLE_DEVICES when specified."""
    import os
    from provider.utils import initialize_jax_environment

    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    initialize_jax_environment(device_id=2)
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "2"

    # Verify that existing CUDA_VISIBLE_DEVICES is preserved dynamically and not clobbered
    initialize_jax_environment(device_id=3)
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "2"
