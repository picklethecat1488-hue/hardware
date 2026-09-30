# SPH Fluid Dynamics & Numerical Stability

Guidelines and requirements for Smoothed Particle Hydrodynamics (SPH) simulations in JAX.

## 1. Boundary Representations
* **Analytical Boundaries**: Prefer analytical boundaries (`URDFCollisionType.ANALYTICAL`) over concave meshes (`URDFCollisionType.CONCAVE`) for JAX SPH fluid simulation. This prevents boundary particle tunneling and accelerates collision resolution.
* **Cylinder Cavities**: For cylinder cavity boundary configurations, treat height as infinite along the local Z axis where possible to avoid particle escape at high pressures.
* **Boundary Derivation**: All boundary dimensions must be derived directly from CAD geometries via `URDFBoundary.from_shape` or `URDFBoundary.from_part` rather than hardcoding numeric coordinates.

## 2. Simulation Execution & JIT Compilation
* **JAX-JIT Compilation**: Prefer using `jax.jit` and pure functions during physics computations in JAX to leverage static optimization, compilation speedups, and hardware acceleration.
* **Semantic Coordinate Transforms**: Direct matrix and raw quaternion operations (`q_inv`, `q_mult`, `q_rotate`) are strictly BANNED in JAX simulation and provider production code. All spatial transitions and frame changes MUST use semantic coordinate transformations (`world_to_base_frame`, `base_to_world_frame`, `base_to_local_frame`, `local_to_base_frame`, `base_to_voxel_coord`) and coordinate system conversions (`cartesian_to_cylindrical`, `cylindrical_to_cartesian`, `cartesian_to_spherical`) from `provider.transforms`. This guarantees mathematical consistency across coordinate frames (World, Base Link, Local Link, Voxel Grid) and prevents phantom collision boundaries or force misprojections.
* **Fluid Recycling**: Ensure `fluid.recycle_fluid = True` is used in steady-state flow loops, with boundary coordinates matching physical limits.
* **Numeric Damping**: For long-running simulation validations, enforce stabilization velocity damping (e.g., `0.95`) to prevent numerical velocity buildup.

## 3. Physical Invariants & Numerical Verification
* **Physical Contact & Non-Floating Invariants**: Fluid particles residing in containers under gravity must make direct physical contact with the bottom floor ($\min(Z) \le Z_{\text{floor}} + 2 \cdot r_s + \text{margin}$) and spread to outer containment boundaries ($r \to R_{\text{wall}}$), forming a continuous fluid mass. Fluid tests must explicitly assert these contact invariants to prevent artificial mid-air hovering, floating shells, or disconnected particle clusters.
* **Test Failure Replication**: When unphysical behaviors (such as mid-air hovering, suction traps, or hollow shells) are observed during visual simulation inspection, test cases must be updated with assertions that actively reproduce the failure under flawed dynamics and only pass when the physical dynamics are verified.
