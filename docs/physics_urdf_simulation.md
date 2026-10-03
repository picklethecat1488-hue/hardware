# Physics & URDF Simulation Guidelines

Guidelines for physical simulation models, URDF metadata derivation, and PyBullet kinematics.

## 1. URDF Metadata Specification
* Attach URDF and simulation attributes to shape geometries for all components participating in physics simulations (PyBullet, JAX fluids).
* Wrap geometries using `URDFMetadata` blocks providing:
  - `urdf_label` (`str`): Unique link/joint identifier.
  - `urdf_material` (`str`): Material name (e.g., `"petg"`, `"acrylic"`).
  - `urdf_density` (`float`): Density in $\text{kg/m}^3$.
  - `urdf_collision_type` (`URDFCollisionType`): Convex, concave, compound, analytical, or none.
  - Kinematic joint constraints (`urdf_joint_type`, `urdf_joint_axis`, limits) and motor properties (`urdf_motor_type`, target, force).

## 2. Direct CAD Boundary Derivation
* **Mandated `URDFBoundary.from_shape`**: ALL simulation boundaries (`URDFBoundary`)—across all collision types (`ANALYTICAL`, `CONVEX`, `CONCAVE`, `COMPOUND`, etc.) and physical bodies—MUST be derived directly from build123d shapes, solids, compounds, or attached joint ports using `URDFBoundary.from_shape(shape_geom, ...)` or `URDFBoundary.from_part(part, ...)`.
* **Zero Duplicate Numeric Literals**: Do NOT manually duplicate numeric literals or re-compute geometric scalars (`radius`, `height`, `thickness`, `xyz`, `intake_pos`, `drain_pos`, etc.) in python source code. B-Rep face dimensions, bounding envelopes, and fluid port coordinates must be extracted automatically from CAD geometry and `RigidJoint` markers to eliminate the dual single-source-of-truth problem.
* **Physics Parameters Definition**: All physical properties and simulation parameters—including magnetic coupling attraction forces, joint constraints, kinematics, and physical barriers—MUST be defined in the URDF metadata or settings schema rather than being hardcoded in python source code.
* **Dynamic Physics via URDF & CAD Geometry**: Physics and simulation code (e.g. in `provider/fluid.py`, `provider/boundary.py`, `model/fluid_body.py`, and `provider/bullet.py`) MUST construct CAD context features, fluid bodies, and physics constraints dynamically using values read from URDF metadata, `BoundaryConfig`, PyBullet joint information, or build123d CAD shapes.
* **Coordination of CAD & URDF**: When modifying physical CAD geometries (such as heights, pockets, snouts, or slots), you MUST update the corresponding `URDFMetadata`, joints, and analytical `URDFBoundary` offsets (`xyz` translations) to ensure physical simulation models remain accurate and zero-intersection constraints are preserved.

## 3. PyBullet & Kinematics Bug Reproduction Mandate
* When investigating, debugging, or fixing issues in PyBullet physics, kinematics, collision boundaries, or fluid dynamics, you MUST create a reproducible test case or isolated reproduction script BEFORE implementing any fix.
* Actively assert the failing invariant or flawed dynamics in the reproduction to verify the issue. If reproduction is not possible (due to underspecified initial conditions, missing physical parameters, or ambiguous visual artifacts), pause and ask the user for clarification before modifying production code.
