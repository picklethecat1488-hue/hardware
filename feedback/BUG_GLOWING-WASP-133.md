# 🔴 `[BUG-GLOWING-WASP-133]` Cat fountain-refactor and simplify code

- **UUID**: `3b92ccaf-1e89-42b4-b7fb-384d898c6e9e`
- **ID**: `BUG-GLOWING-WASP-133`
- **Status**: `OPEN`
- **Severity**: `LOW`
- **Category**: `GENERAL`
- **Component**: `cat_fountain`
- **Created**: `2026-11-06 04:30:54 UTC`

#### Description

Right now, some of the cat fountain code contains repeated patterns, particularly for creating the snap-fit ring mounts:

```
            # Add the snap-fit annular Torus ridge
            with Locations((0, 0, self.settings.snap_ridge_z)):
                Torus(
                    major_radius=lid_r + self.settings.snap_ridge_major_offset,
                    minor_radius=self.settings.snap_ridge_minor,
                )

            with BuildPart() as pocket_tool:
                Cylinder(radius=80.0, height=6.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                bottom_edge = pocket_tool.edges().filter_by(GeomType.CIRCLE).sort_by(Axis.Z)[0]
                fillet(bottom_edge, radius=1.5)
            with Locations((0.0, 0.0, 3.0)):
                add(pocket_tool, mode=Mode.SUBTRACT)
```

Can we clean up and optimize this code?
