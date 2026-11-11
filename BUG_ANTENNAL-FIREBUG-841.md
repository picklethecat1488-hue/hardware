# 🟢 `[BUG-ANTENNAL-FIREBUG-841]` CAD viewport canvas height does not expand to fill browser window

- **UUID**: `37a3ee75-19a5-428e-a618-b1c71af0f4bd`
- **ID**: `BUG-ANTENNAL-FIREBUG-841`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 13:54:05 UTC`
- **Resolved**: `2026-11-11 21:52:31 UTC`
- **Accepted**: `2026-11-11 21:52:38 UTC`
- **Rejected**: `2026-11-11 18:15:54 UTC`

#### Description

The viewport doesn’t cover the bottom 2/3 of my browser window

#### Reproduction Steps

1. python tools/scope.py cat_fountain/product:cad

#### Attached Commits

- `84e9c3d4`
- `ee8b52fd3cd1cf529815055f78b14816c96e2806`
- `5919a5dd`
- `d3e08b55`
- `7b5bbd30`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:114cb954 --> Verify CAD viewport dynamically expands to fill 100% of browser window upon resize | `python tools/scope.py cat_fountain/product:cad`

#### Resolution Notes

Enforced 100% flex height layout on .tcv_cad_viewer, added null safety in resizeCadView, and triggered post-render viewport resize

#### Rejection Feedback

Added Viewer.resize method to three-cad-viewer.esm.js and wired ResizeObserver auto-fitting in scope.html.j2

- This still doesn’t work. Attaching a screenshot
