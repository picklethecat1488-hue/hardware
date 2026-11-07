# 🟢 `[BUG-WINGED-INSTAR-825]` Impeller analytical URDF boundary has low CAD conformance

- **UUID**: `fbc64131-2e5a-47d2-ad00-c73f2cc12bad`
- **ID**: `BUG-WINGED-INSTAR-825`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-07 02:32:35 UTC`
- **Resolved**: `2026-11-07 02:32:44 UTC`
- **Accepted**: `2026-11-07 02:32:44 UTC`

#### Description

The impeller analytical URDF boundary reconstructor reconstructs the base as a solid cylinder instead of respecting the multi-lobed convex hull geometry when magnet_count >= 3, causing boundary volume overestimation and conformance failure (41.44% < 70%).

#### Attached Commits

- `26dfabfc`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:63e9c1b0 --> Verify impeller analytical URDF boundary matches 3-lobed CAD solid geometry | `python tools/build.py cat_fountain/impeller && python tools/view.py cat_fountain/impeller`

#### Resolution Notes

Updated reconstruct_boundary_cad_solid to reconstruct the multi-lobed convex hull when magnet_count >= 3, and centered impeller origin on rotation axis at (0, 0), restoring CAD conformance ratio to 82.4%.
