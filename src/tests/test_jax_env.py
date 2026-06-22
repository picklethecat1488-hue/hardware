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
