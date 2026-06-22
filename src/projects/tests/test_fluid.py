"""Unit tests for SPH Fluid simulation class."""

import math
from projects.fluid import Fluid


def test_fluid_initialization():
    """Verify that Fluid class initializes with the correct constants."""
    fluid = Fluid(r_s=0.003, rest_density=1000.0, viscosity=0.5, stiffness=2000.0)
    assert math.isclose(fluid.r_s, 0.003)
    assert math.isclose(fluid.h, 0.009)
    assert fluid.rest_density == 1000.0
    assert fluid.viscosity == 0.5
    assert fluid.k == 2000.0
    assert fluid.mass > 0.0


def test_zero_shear_strength():
    """
    Verify the Zero Shear Strength rule (fluids continuously deform under shear).

    If we apply a sideways force to a block of particles, they should flow and deform.
    """
    fluid = Fluid(r_s=0.003, viscosity=0.1)

    # Place particles in a vertical column to represent a fluid block
    positions = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.006),
        (0.0, 0.0, 0.012),
        (0.0, 0.006, 0.0),
        (0.0, 0.006, 0.006),
    ]
    # Stationary initial velocities
    velocities = [(0.0, 0.0, 0.0)] * 5

    # Step simulation manually by applying a shear (horizontal) force
    # and verify that deformation (change in relative horizontal positions) is continuous.
    forces = fluid.compute_forces(positions, velocities)

    # Ensure SPH forces computed are valid
    assert len(forces) == 5
    for f in forces:
        assert len(f) == 3

    # Apply a constant sideways shear velocity to the top particle and verify viscosity transmits
    # shear to lower particles, causing continuous deformation.
    velocities[2] = (1.0, 0.0, 0.0)  # Top particle moving horizontally
    forces_under_shear = fluid.compute_forces(positions, velocities)

    # Viscosity force should pull neighboring particles in the direction of the shear velocity
    # Particle 1 (neighbor to particle 2 at z=0.006) should experience a positive force in X
    assert forces_under_shear[1][0] > 0.0


def test_knudsen_number():
    """Verify that the fluid acts as a continuous regime with Kn < 0.1."""
    fluid = Fluid(r_s=0.003)

    # Create a dense grid of particles resembling a fluid continuum
    positions = []
    for x in range(5):
        for y in range(5):
            for z in range(5):
                positions.append((x * 0.006, y * 0.006, z * 0.006))

    kn = fluid.compute_knudsen_number(positions, characteristic_length=0.076)

    # For a dense fluid packing, Kn should be strictly less than 0.1
    # demonstrating that it operates in the continuum fluid dynamics regime.
    assert kn < 0.1
    assert kn > 0.0


def test_newtonian_viscosity():
    """Verify that viscosity force acts to reduce relative velocity linearly (Newtonian)."""
    fluid = Fluid(r_s=0.003, viscosity=0.5)

    # Two adjacent particles with relative velocity
    positions = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.005),
    ]

    # Newtonian viscosity: force should scale linearly with relative velocity
    vel_1 = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    forces_1 = fluid.compute_forces(positions, vel_1)

    vel_2 = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    forces_2 = fluid.compute_forces(positions, vel_2)

    # The viscosity force on particle 0 in X should be positive (dragged by particle 1)
    assert forces_1[0][0] > 0.0
    assert forces_2[0][0] > 0.0

    # Viscosity force should be approximately doubled when velocity difference is doubled
    ratio = forces_2[0][0] / forces_1[0][0]
    assert math.isclose(ratio, 2.0, rel_tol=1e-2)


def test_momentum_conservation():
    """Verify Newton's Third Law (action/reaction forces sum to zero)."""
    fluid = Fluid(r_s=0.003, viscosity=0.5, stiffness=1000.0)

    # 3 asymmetric particles to create complex internal forces
    positions = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.004),
        (0.0, 0.003, 0.003),
    ]
    velocities = [
        (0.1, -0.2, 0.0),
        (-0.3, 0.1, 0.2),
        (0.0, 0.1, -0.1),
    ]

    forces = fluid.compute_forces(positions, velocities)

    # Sum of all internal forces must be extremely close to 0.0 (momentum conservation)
    sum_x = sum(f[0] for f in forces)
    sum_y = sum(f[1] for f in forces)
    sum_z = sum(f[2] for f in forces)

    # Using 5e-4 tolerance to account for float32 precision
    assert math.isclose(sum_x, 0.0, abs_tol=5e-4)
    assert math.isclose(sum_y, 0.0, abs_tol=5e-4)
    assert math.isclose(sum_z, 0.0, abs_tol=5e-4)


def test_incompressibility_repulsion():
    """Verify that compressed particles experience repulsive pressure forces."""
    fluid = Fluid(r_s=0.003, stiffness=2000.0, viscosity=0.1)

    # Place 16 particles in two tight clusters separated along the Z-axis
    positions = []
    # Cluster A (centered around z = 0.0)
    for x in (-0.001, 0.001):
        for y in (-0.001, 0.001):
            for z in (-0.001, 0.001):
                positions.append((x, y, z))
    # Cluster B (centered around z = 0.005)
    for x in (-0.001, 0.001):
        for y in (-0.001, 0.001):
            for z in (0.004, 0.006):
                positions.append((x, y, z))

    velocities = [(0.0, 0.0, 0.0)] * 16
    forces = fluid.compute_forces(positions, velocities)

    # Average force on Cluster A should have negative Z (pushed away from B)
    avg_f_a_z = sum(forces[i][2] for i in range(8)) / 8.0
    # Average force on Cluster B should have positive Z (pushed away from A)
    avg_f_b_z = sum(forces[i][2] for i in range(8, 16)) / 8.0

    assert avg_f_a_z < 0.0
    assert avg_f_b_z > 0.0


def test_single_particle_forces():
    """Verify that a single isolated particle experiences zero internal force."""
    fluid = Fluid(r_s=0.003)

    positions = [(0.0, 0.0, 0.0)]
    velocities = [(1.0, 2.0, -3.0)]

    forces = fluid.compute_forces(positions, velocities)
    assert len(forces) == 1
    assert forces[0] == [0.0, 0.0, 0.0]


def test_compute_forces_jax_direct():
    """Verify that compute_forces_jax produces the same output as compute_forces but as a JAX array."""
    import jax.numpy as jnp

    fluid = Fluid(r_s=0.003)
    positions = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.004),
        (0.0, 0.003, 0.003),
    ]
    velocities = [
        (0.1, -0.2, 0.0),
        (-0.3, 0.1, 0.2),
        (0.0, 0.1, -0.1),
    ]
    pos_jax = jnp.array(positions, dtype=jnp.float32)
    vel_jax = jnp.array(velocities, dtype=jnp.float32)

    forces_list = fluid.compute_forces(positions, velocities)
    forces_jax = fluid.compute_forces_jax(pos_jax, vel_jax)

    assert isinstance(forces_jax, jnp.ndarray)
    assert forces_jax.shape == (3, 3)
    for i in range(len(positions)):
        for j in range(3):
            assert math.isclose(float(forces_jax[i, j]), forces_list[i][j], abs_tol=1e-4)
