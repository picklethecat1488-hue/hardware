"""Unit tests for dynamic fluid body primitives (move, split, merge) and shape recomputation."""

import numpy as np
from model.fluid_body import FluidBody, FluidBodyTracker, FluidBodyType


def test_fluid_body_shape_recomputation():
    """Test recomputing geometric bounds, centroid, volume, and velocity for a fluid body."""
    positions = np.array(
        [
            [0.0, 0.0, 0.040],
            [0.010, 0.0, 0.040],
            [0.0, 0.010, 0.040],
            [0.010, 0.010, 0.050],
        ],
        dtype=np.float32,
    )
    velocities = np.array(
        [
            [0.0, 0.0, 0.1],
            [0.1, 0.0, 0.1],
            [0.0, 0.1, 0.1],
            [0.1, 0.1, 0.2],
        ],
        dtype=np.float32,
    )
    r_s = 0.0025

    body = FluidBody(
        body_id=1,
        body_type=FluidBodyType.POOL,
        particle_indices=np.array([0, 1, 2, 3]),
    )
    body.recompute_shape(positions, velocities, r_s)

    assert body.particle_count == 4
    assert np.isclose(body.centroid[0], 0.005)
    assert np.isclose(body.centroid[1], 0.005)
    assert np.isclose(body.centroid[2], 0.0425)
    assert body.bounds_min[2] <= 0.040
    assert body.bounds_max[2] >= 0.050
    assert body.volume > 0.0


def test_fluid_body_move_primitive():
    """Test translating a fluid body by a 3D displacement vector."""
    body = FluidBody(
        body_id=1,
        body_type=FluidBodyType.POOL,
        particle_indices=np.array([0, 1]),
        centroid=(0.0, 0.0, 0.050),
        bounds_min=(-0.010, -0.010, 0.040),
        bounds_max=(0.010, 0.010, 0.060),
    )

    body.move((0.005, -0.002, 0.010))

    assert np.isclose(body.centroid[0], 0.005)
    assert np.isclose(body.centroid[1], -0.002)
    assert np.isclose(body.centroid[2], 0.060)
    assert np.isclose(body.bounds_min[0], -0.005)
    assert np.isclose(body.bounds_max[2], 0.070)


def test_fluid_body_split_primitive():
    """Test splitting a fluid body into distinct child bodies."""
    positions = np.array(
        [
            # Cluster A (Pool)
            [0.0, 0.0, 0.040],
            [0.005, 0.0, 0.040],
            # Cluster B (Stream)
            [0.0, 0.028, 0.080],
            [0.0, 0.028, 0.090],
        ],
        dtype=np.float32,
    )
    velocities = np.zeros((4, 3), dtype=np.float32)
    r_s = 0.0025

    parent = FluidBody(
        body_id=10,
        body_type=FluidBodyType.POOL,
        particle_indices=np.array([0, 1, 2, 3]),
    )

    counter = [11]

    def next_id():
        nid = counter[0]
        counter[0] += 1
        return nid

    children = parent.split(
        [np.array([0, 1]), np.array([2, 3])],
        positions,
        velocities,
        r_s,
        next_id_fn=next_id,
    )

    assert len(children) == 2
    assert children[0].body_id == 11
    assert children[0].particle_count == 2
    assert np.isclose(children[0].centroid[2], 0.040)

    assert children[1].body_id == 12
    assert children[1].particle_count == 2
    assert np.isclose(children[1].centroid[2], 0.085)


def test_fluid_body_merge_primitive():
    """Test merging two fluid bodies into a unified physical body."""
    positions = np.array(
        [
            [0.0, 0.0, 0.040],
            [0.010, 0.0, 0.040],
            [0.020, 0.0, 0.040],
        ],
        dtype=np.float32,
    )
    velocities = np.zeros((3, 3), dtype=np.float32)
    r_s = 0.0025

    body1 = FluidBody(
        body_id=1,
        body_type=FluidBodyType.POOL,
        particle_indices=np.array([0, 1]),
    )
    body1.recompute_shape(positions, velocities, r_s)

    body2 = FluidBody(
        body_id=2,
        body_type=FluidBodyType.CLUSTER,
        particle_indices=np.array([2]),
    )
    body2.recompute_shape(positions, velocities, r_s)

    merged = body1.merge(body2, positions, velocities, r_s)

    assert merged.body_id == 1
    assert merged.particle_count == 3
    assert np.array_equal(merged.particle_indices, np.array([0, 1, 2]))
    assert np.isclose(merged.centroid[0], 0.010)


def test_fluid_body_tracker():
    """Test dynamic classification and updating of fluid bodies across reservoir, tube, and lid."""
    positions = np.array(
        [
            # Pool particle
            [0.0, 0.0, 0.050],
            # Stream particle (in tube at Y=0.028)
            [0.0, 0.028, 0.060],
            # Sheet particle on lid (Z=0.100)
            [0.030, 0.0, 0.100],
            # Falling cluster in air
            [0.060, 0.0, 0.085],
        ],
        dtype=np.float32,
    )
    velocities = np.zeros((4, 3), dtype=np.float32)

    tracker = FluidBodyTracker(r_s=0.0025)
    bodies = tracker.update_bodies(
        positions,
        velocities,
        z_floor=0.041,
        z_lid=0.098,
        tube_y=0.028,
        tube_r=0.010,
    )

    types = {b.body_type for b in bodies}
    assert FluidBodyType.POOL in types
    assert FluidBodyType.STREAM in types
    assert FluidBodyType.SHEET in types
    assert FluidBodyType.CLUSTER in types
    assert len(bodies) == 4
