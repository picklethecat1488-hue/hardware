"""Pure JAX vectorized coordinate transformations and quaternion kinematics."""

import jax
import jax.numpy as jnp


@jax.jit
def _q_mult(q1: jnp.ndarray, q2: jnp.ndarray) -> jnp.ndarray:
    """Multiply two quaternions q1 and q2 in (x, y, z, w) format."""
    x1, y1, z1, w1 = q1[0], q1[1], q1[2], q1[3]
    x2, y2, z2, w2 = q2[0], q2[1], q2[2], q2[3]
    return jnp.array(
        [
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        ],
        dtype=jnp.float32,
    )


@jax.jit
def _q_rotate(q: jnp.ndarray, v: jnp.ndarray) -> jnp.ndarray:
    """Rotate 3D vector v by quaternion q in (x, y, z, w) format."""
    q_xyz = q[:3]
    w = q[3]
    cross1 = jnp.cross(q_xyz, v) + w * v
    return v + 2.0 * jnp.cross(q_xyz, cross1)


@jax.jit
def invert_orientation(orn: jnp.ndarray) -> jnp.ndarray:
    """Calculate the inverse (conjugate) of an orientation quaternion in (x, y, z, w) format."""
    return jnp.array([-orn[0], -orn[1], -orn[2], orn[3]], dtype=jnp.float32)


@jax.jit
def world_to_base_orientation(child_world_orn: jnp.ndarray, base_world_orn: jnp.ndarray) -> jnp.ndarray:
    """Calculate the relative orientation of a child frame with respect to the base frame (base_orn^-1 * child_orn)."""
    base_inv = invert_orientation(base_world_orn)
    rel_q = _q_mult(base_inv, child_world_orn)
    norm = jnp.linalg.norm(rel_q)
    return jnp.where(norm > 1e-6, rel_q / norm, rel_q)


# ==============================================================================
# Coordinate Space Position Transformations (World, Base Link, Local Link, Voxel Grid)
# ==============================================================================


@jax.jit
def world_to_base_frame(
    pos_world: jnp.ndarray,
    base_pos: jnp.ndarray,
    base_orn_inv: jnp.ndarray,
) -> jnp.ndarray:
    """Transform 3D position vector from World Space to Base Link Space."""
    return _q_rotate(base_orn_inv, pos_world - base_pos)


@jax.jit
def base_to_world_frame(
    pos_base: jnp.ndarray,
    base_pos: jnp.ndarray,
    base_orn: jnp.ndarray,
) -> jnp.ndarray:
    """Transform 3D position vector from Base Link Space to World Space."""
    return _q_rotate(base_orn, pos_base) + base_pos


@jax.jit
def base_to_local_frame(
    pos_base: jnp.ndarray,
    b_pos_loc: jnp.ndarray,
    b_orn_loc_inv: jnp.ndarray,
) -> jnp.ndarray:
    """Transform 3D position vector from Base Link Space to specific Local Boundary Frame."""
    return _q_rotate(b_orn_loc_inv, pos_base - b_pos_loc)


@jax.jit
def local_to_base_frame(
    pos_local: jnp.ndarray,
    b_pos_loc: jnp.ndarray,
    b_orn_loc: jnp.ndarray,
) -> jnp.ndarray:
    """Transform 3D position vector from Local Boundary Frame to Base Link Space."""
    return _q_rotate(b_orn_loc, pos_local) + b_pos_loc


@jax.jit
def world_to_local_frame(
    pos_world: jnp.ndarray,
    link_pos_world: jnp.ndarray,
    link_orn_world_inv: jnp.ndarray,
) -> jnp.ndarray:
    """Transform 3D position vector from World Space to Link Local Frame."""
    return _q_rotate(link_orn_world_inv, pos_world - link_pos_world)


@jax.jit
def local_to_world_frame(
    pos_local: jnp.ndarray,
    link_pos_world: jnp.ndarray,
    link_orn_world: jnp.ndarray,
) -> jnp.ndarray:
    """Transform 3D position vector from Link Local Frame to World Space."""
    return _q_rotate(link_orn_world, pos_local) + link_pos_world


@jax.jit
def base_to_voxel_coord(
    pos_base: jnp.ndarray,
    origin_base: jnp.ndarray,
    dx: float,
) -> jnp.ndarray:
    """Convert Base Link metric coordinates (x, y, z) into fractional voxel lattice coordinates."""
    return (pos_base - origin_base) / dx


@jax.jit
def voxel_to_base_coord(
    coord_vox: jnp.ndarray,
    origin_base: jnp.ndarray,
    dx: float,
) -> jnp.ndarray:
    """Convert fractional voxel lattice coordinates into Base Link metric coordinates (x, y, z)."""
    return origin_base + coord_vox * dx


# ==============================================================================
# Coordinate Space Directional Vector Transformations (Velocities, Forces, Normals)
# ==============================================================================


@jax.jit
def world_to_base_vector(
    vec_world: jnp.ndarray,
    base_orn_inv: jnp.ndarray,
) -> jnp.ndarray:
    """Transform directional 3D vector (velocity, force, normal) from World Space to Base Link Space."""
    return _q_rotate(base_orn_inv, vec_world)


@jax.jit
def base_to_world_vector(
    vec_base: jnp.ndarray,
    base_orn: jnp.ndarray,
) -> jnp.ndarray:
    """Transform directional 3D vector (velocity, force, normal) from Base Link Space to World Space."""
    return _q_rotate(base_orn, vec_base)


@jax.jit
def world_to_local_vector(
    vec_world: jnp.ndarray,
    link_orn_world_inv: jnp.ndarray,
) -> jnp.ndarray:
    """Transform directional 3D vector from World Space to Link Local Space."""
    return _q_rotate(link_orn_world_inv, vec_world)


@jax.jit
def local_to_world_vector(
    vec_local: jnp.ndarray,
    link_orn_world: jnp.ndarray,
) -> jnp.ndarray:
    """Transform directional 3D vector from Link Local Space to World Space."""
    return _q_rotate(link_orn_world, vec_local)


@jax.jit
def local_to_base_vector(
    vec_local: jnp.ndarray,
    b_orn_loc: jnp.ndarray,
) -> jnp.ndarray:
    """Transform directional 3D vector from Local Boundary Space to Base Link Space."""
    return _q_rotate(b_orn_loc, vec_local)


@jax.jit
def base_to_local_vector(
    vec_base: jnp.ndarray,
    b_orn_loc_inv: jnp.ndarray,
) -> jnp.ndarray:
    """Transform directional 3D vector from Base Link Space to Local Boundary Space."""
    return _q_rotate(b_orn_loc_inv, vec_base)


# ==============================================================================
# Coordinate System Conversions (Cartesian, Cylindrical/Polar, Spherical)
# ==============================================================================


@jax.jit
def cartesian_to_cylindrical(
    pos: jnp.ndarray,
) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    """Convert 3D Cartesian coordinates (x, y, z) to Cylindrical (r, theta, z).

    Returns:
        tuple containing:
            - r: Radial distance in the xy-plane (meters)
            - theta: Azimuthal angle in radians [-pi, pi]
            - z: Height along the z-axis (meters)
    """
    r = jnp.sqrt(pos[..., 0] ** 2 + pos[..., 1] ** 2)
    theta = jnp.arctan2(pos[..., 1], pos[..., 0])
    z = pos[..., 2]
    return r, theta, z


@jax.jit
def cylindrical_to_cartesian(
    r: jnp.ndarray,
    theta: jnp.ndarray,
    z: jnp.ndarray,
) -> jnp.ndarray:
    """Convert Cylindrical coordinates (r, theta, z) to 3D Cartesian (x, y, z)."""
    x = r * jnp.cos(theta)
    y = r * jnp.sin(theta)
    return jnp.stack([x, y, z], axis=-1)


@jax.jit
def cartesian_to_polar_2d(
    pos_xy: jnp.ndarray,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Convert 2D Cartesian coordinates (x, y) to Polar (r, theta)."""
    r = jnp.sqrt(pos_xy[..., 0] ** 2 + pos_xy[..., 1] ** 2)
    theta = jnp.arctan2(pos_xy[..., 1], pos_xy[..., 0])
    return r, theta


@jax.jit
def polar_to_cartesian_2d(
    r: jnp.ndarray,
    theta: jnp.ndarray,
) -> jnp.ndarray:
    """Convert 2D Polar coordinates (r, theta) to Cartesian (x, y)."""
    x = r * jnp.cos(theta)
    y = r * jnp.sin(theta)
    return jnp.stack([x, y], axis=-1)


@jax.jit
def cartesian_to_spherical(
    pos: jnp.ndarray,
) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    """Convert 3D Cartesian coordinates (x, y, z) to Spherical (r, theta, phi).

    Returns:
        tuple containing:
            - r: Radial distance from the origin (meters)
            - theta: Azimuthal angle in the xy-plane in radians [-pi, pi]
            - phi: Polar angle (inclination from the +z axis) in radians [0, pi]
    """
    r = jnp.sqrt(jnp.sum(pos**2, axis=-1) + 1e-8)
    theta = jnp.arctan2(pos[..., 1], pos[..., 0])
    phi = jnp.arccos(jnp.clip(pos[..., 2] / r, -1.0, 1.0))
    return r, theta, phi


@jax.jit
def spherical_to_cartesian(
    r: jnp.ndarray,
    theta: jnp.ndarray,
    phi: jnp.ndarray,
) -> jnp.ndarray:
    """Convert Spherical coordinates (r, theta, phi) to 3D Cartesian (x, y, z)."""
    x = r * jnp.sin(phi) * jnp.cos(theta)
    y = r * jnp.sin(phi) * jnp.sin(theta)
    z = r * jnp.cos(phi)
    return jnp.stack([x, y, z], axis=-1)
