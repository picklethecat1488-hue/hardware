# 🟢 `[BUG-CLICKING-LARVA-354]` The engineering questions of your 3D print order#C-E71W908185A_bottom_cover.stl

- **UUID**: `d4d28107-f07e-4d7a-ac51-9a7aee11c17c`
- **ID**: `BUG-CLICKING-LARVA-354`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-09 18:20:44 UTC`
- **Resolved**: `2026-11-09 23:00:42 UTC`
- **Accepted**: `2026-11-09 23:00:47 UTC`

#### Description

The height of the protruding feature is too small to print.

—This looks like a defect introduced by conversion of BREP CAD objects into STL meshes. Can you take a look/fix this?

#### Attached Commits

- `89249441`

#### Review Tasks & Functional Checklist

- [x] <!-- task:3b7fdaad --> Compile bottom cover STL to verify smooth annular snap ridge and absence of unprintable horizontal shelf steps | `python tools/build.py cat_fountain/bottom_cover`

#### Resolution Notes

Replace stepped annular snap ring with continuous smooth Torus ridge on bottom cover
