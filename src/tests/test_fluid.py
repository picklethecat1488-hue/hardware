"""Unit tests for SPH Fluid simulation class."""

import math
from provider.fluid import Fluid
from provider.bullet import LinkType
from model import FluidConfig


def test_fluid_initialization():
    """Verify that Fluid class initializes with the correct constants."""
    fluid = Fluid(config=FluidConfig(r_s=0.003, rest_density=1000.0, viscosity=0.5, stiffness=2000.0))
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
    fluid = Fluid(config=FluidConfig(r_s=0.003, viscosity=0.1))

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
    fluid = Fluid(config=FluidConfig(r_s=0.003))

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
    fluid = Fluid(config=FluidConfig(r_s=0.003, viscosity=0.5))

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
    fluid = Fluid(config=FluidConfig(r_s=0.003, viscosity=0.5, stiffness=1000.0))

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
    fluid = Fluid(config=FluidConfig(r_s=0.003, stiffness=2000.0, viscosity=0.1))

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
    fluid = Fluid(config=FluidConfig(r_s=0.003))

    positions = [(0.0, 0.0, 0.0)]
    velocities = [(1.0, 2.0, -3.0)]

    forces = fluid.compute_forces(positions, velocities)
    assert len(forces) == 1
    assert forces[0] == [0.0, 0.0, 0.0]


def test_compute_forces_jax_direct():
    """Verify that compute_forces_jax produces the same output as compute_forces but as a JAX array."""
    import jax.numpy as jnp

    fluid = Fluid(config=FluidConfig(r_s=0.003))
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


def test_fluid_spawner_padding_and_jitter():
    """Verify that FluidSpawner spawns batches with jitter and pads arrays correctly."""
    import pybullet as p
    from provider.fluid import FluidSpawner

    physics_client = p.connect(p.DIRECT)
    try:
        spawner = FluidSpawner(
            physics_client=physics_client,
            r_s=0.003,
            n_particles=10,
            particle_mass=0.002,
            particle_color=[0, 0, 1, 1],
            linear_damping=0.05,
            angular_damping=0.05,
            lateral_friction=0.1,
            restitution=0.0,
        )

        # Initial state
        assert spawner.active_count == 0
        assert len(spawner.particle_body_ids) == 0

        # 1. Spawn a batch of 4 particles
        newly_spawned = spawner.spawn_batch(spawn_z=0.100, batch_size=4, spacing=0.008)
        assert newly_spawned == 4
        assert spawner.active_count == 4
        assert len(spawner.particle_body_ids) == 4

        # Verify positions and velocities are padded up to n_particles (10)
        positions, velocities = spawner.get_positions_and_velocities()
        assert len(positions) == 10
        assert len(velocities) == 10

        # First 4 positions should be active particles (z < 100)
        for i in range(4):
            assert positions[i][2] < 100.0
            assert abs(positions[i][0]) <= 0.006
            assert abs(positions[i][1]) <= 0.006

        # Remaining 6 should be padded to 1000.0
        for i in range(4, 10):
            assert math.isclose(positions[i][2], 1000.0)
            assert positions[i][0] == 0.0
            assert positions[i][1] == 0.0

        # Spawn more than n_particles capacity
        newly_spawned_2 = spawner.spawn_batch(spawn_z=0.100, batch_size=10, spacing=0.008)
        assert newly_spawned_2 == 6  # Spawner caps at n_particles (10)
        assert spawner.active_count == 10

    finally:
        p.disconnect(physicsClientId=physics_client)


def test_fluid_simulator_dynamic_properties():
    """Verify that Fluid reads target velocity, force, and offset from shape metadata and PyBullet."""
    from unittest.mock import patch, MagicMock
    from provider.fluid import Fluid
    from provider.room import Room

    # Mock provider
    provider = MagicMock()
    provider.settings.bowl_radius = 80.0
    provider.settings.bowl_thickness = 3.5
    provider.settings.tube_thickness = 1.5
    provider.settings.impeller_shaft_radius = 1.5

    sim = Fluid(
        provider=provider,
        body_id=42,
        physics_client=1,
        link_indices={
            LinkType.OUTLET: 2,
            LinkType.TUBE: 1,
            LinkType.IMPELLER: 0,
        },
    )

    # Mock PyBullet functions
    def mock_get_num_joints(body_id, physicsClientId):
        return 3

    def mock_get_joint_info(body_id, joint_idx, physicsClientId):
        # idx 0: impeller, idx 1: tube, idx 2: spout
        if joint_idx == 0:
            return (
                0,
                b"joint0",
                0,
                0,
                0,
                0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                b"impeller",
                (0, 0, 0),
                (0, 0, 0),
                (0, 0, 0, 1),
                -1,
            )
        elif joint_idx == 1:
            return (
                1,
                b"joint1",
                0,
                0,
                0,
                0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                b"tube",
                (0, 0, 0),
                (0.0, 0.057, 0.0),
                (0, 0, 0, 1),
                -1,
            )
        else:
            return (
                2,
                b"joint2",
                0,
                0,
                0,
                0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                b"spout",
                (0, 0, 0),
                (0, 0, 0),
                (0, 0, 0, 1),
                -1,
            )

    def mock_get_aabb(body_id, link_idx, physicsClientId):
        if link_idx == -1:
            return ((-0.080, -0.080, 0.0), (0.080, 0.080, 0.040))
        elif link_idx == 1:
            return ((-0.008, 0.049, 0.0), (0.008, 0.065, 0.100))
        return ((0, 0, 0), (0, 0, 0))

    def mock_get_link_state(body_id, link_idx, physicsClientId):
        if link_idx == 2:
            return (None, None, None, None, (0.0, 0.0, 0.100), (0.0, 0.0, 0.0, 1.0))
        return (None, None, None, None, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))

    with (
        patch("pybullet.getNumJoints", side_effect=mock_get_num_joints),
        patch("pybullet.getJointInfo", side_effect=mock_get_joint_info),
        patch("pybullet.getAABB", side_effect=mock_get_aabb),
        patch("pybullet.getLinkState", side_effect=mock_get_link_state),
        patch("pybullet.getConnectionInfo", return_value={"isConnected": True}),
    ):
        # Verify dynamic properties using the refactored field names
        assert sim.link_indices == {
            LinkType.OUTLET: 2,
            LinkType.TUBE: 1,
            LinkType.IMPELLER: 0,
        }
        assert sim.motor_config.target_omega == 15.0
        assert sim.motor_config.max_force == 10.0
        assert math.isclose(sim.radii[LinkType.TUBE], 0.008, abs_tol=1e-5)
        assert math.isclose(sim.radii[LinkType.BASE], 0.080, abs_tol=1e-5)
        assert math.isclose(sim.radii[LinkType.IMPELLER], 0.003, abs_tol=1e-5)
        assert math.isclose(sim.radii[LinkType.FALLEN], 0.090, abs_tol=1e-5)
        assert math.isclose(sim.thresholds[LinkType.OUTLET], 0.095, abs_tol=1e-5)
        assert math.isclose(sim.thresholds[LinkType.OUTLET_MAX_Y], 0.005, abs_tol=1e-5)
        assert math.isclose(sim.thresholds[LinkType.TUBE], 15.0, abs_tol=1e-5)


def test_fluid_parameter_overrides():
    """Verify that Fluid correctly accepts parameter overrides via the constructor."""
    from provider.fluid import Fluid

    # Create a dummy settings and provider
    class DummySettings:
        pass

    class DummyProvider:
        def __init__(self):
            self.settings = DummySettings()

    provider = DummyProvider()

    # Set overridable simulation constants
    provider.settings.PARTICLE_RADIUS = 0.0025
    provider.settings.TARGET_VOLUME = 0.001
    provider.settings.VOLUME_THRESHOLD_LITERS = 0.600
    provider.settings.FALLEN_THRESHOLD_LITERS = 0.100
    provider.settings.BOWL_WALL_BUFFER = 0.005

    # Set overridable physical settings
    provider.settings.REST_DENSITY = 800.0
    provider.settings.VISCOSITY = 0.12
    provider.settings.STIFFNESS = 150.0

    # Set overridable SPH constants
    provider.settings.SMOOTHING_FACTOR = 4.0
    provider.settings.SPHERE_VOL_FACTOR = 1.333
    provider.settings.POLY6_COEFF_NUMERATOR = 300.0
    provider.settings.POLY6_COEFF_DENOMINATOR = 50.0
    provider.settings.SPIKY_GRAD_COEFF = -40.0
    provider.settings.VISC_LAP_COEFF = 40.0
    provider.settings.PRESSURE_AVG_FACTOR = 3.0
    provider.settings.MIN_DISTANCE_THRESHOLD = 1e-5

    # Initialize Fluid with custom parameters directly
    fluid = Fluid(
        config=FluidConfig(
            particle_radius=provider.settings.PARTICLE_RADIUS,
            target_volume=provider.settings.TARGET_VOLUME,
            volume_threshold_liters=provider.settings.VOLUME_THRESHOLD_LITERS,
            fallen_threshold_liters=provider.settings.FALLEN_THRESHOLD_LITERS,
            bowl_wall_buffer=provider.settings.BOWL_WALL_BUFFER,
            rest_density=provider.settings.REST_DENSITY,
            viscosity=provider.settings.VISCOSITY,
            stiffness=provider.settings.STIFFNESS,
            smoothing_factor=provider.settings.SMOOTHING_FACTOR,
            sphere_vol_factor=provider.settings.SPHERE_VOL_FACTOR,
            poly6_coeff_numerator=provider.settings.POLY6_COEFF_NUMERATOR,
            poly6_coeff_denominator=provider.settings.POLY6_COEFF_DENOMINATOR,
            spiky_grad_coeff=provider.settings.SPIKY_GRAD_COEFF,
            visc_lap_coeff=provider.settings.VISC_LAP_COEFF,
            pressure_avg_factor=provider.settings.PRESSURE_AVG_FACTOR,
            min_distance_threshold=provider.settings.MIN_DISTANCE_THRESHOLD,
        ),
        provider=provider,
    )

    # Assert Fluid constants are overridden
    assert fluid.particle_radius == 0.0025
    assert fluid.target_volume == 0.001
    assert fluid.volume_threshold_liters == 0.600
    assert fluid.fallen_threshold_liters == 0.100
    assert fluid.bowl_wall_buffer == 0.005
    assert fluid.rest_density == 800.0
    assert fluid.viscosity == 0.12
    assert fluid.stiffness == 150.0
    assert fluid.k == 150.0
    assert fluid.smoothing_factor == 4.0
    assert fluid.sphere_vol_factor == 1.333
    assert fluid.pressure_avg_factor == 3.0
    assert fluid.min_distance_threshold == 1e-5
    assert fluid.r_s == 0.0025

    # Test default constructor arguments
    fluid_default = Fluid(provider=provider)
    assert fluid_default.r_s == 0.003
    assert fluid_default.rest_density == 1000.0


def test_fluid_config_object():
    """Verify that Fluid correctly parses settings from a flat FluidConfig object."""
    from model import FluidConfig

    config = FluidConfig(
        viscosity=0.77,
        rest_density=920.0,
        smoothing_factor=4.5,
        target_volume=0.0008,
        sim_name="config_test",
    )

    # Initialize purely from config
    fluid = Fluid(config=config)
    assert fluid.viscosity == 0.77
    assert fluid.rest_density == 920.0
    assert fluid.smoothing_factor == 4.5
    assert fluid.target_volume == 0.0008
