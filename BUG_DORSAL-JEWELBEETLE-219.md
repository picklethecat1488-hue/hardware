# 🟢 `[BUG-DORSAL-JEWELBEETLE-219]` Viewport snapshot not capturing 3D model and rotation render performance is slow

- **UUID**: `e6ee3e8d-ecd1-45ff-bbef-04322be48dc3`
- **ID**: `BUG-DORSAL-JEWELBEETLE-219`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 14:02:00 UTC`
- **Resolved**: `2026-11-11 18:54:10 UTC`
- **Rejected**: `2026-11-11 18:23:29 UTC`

#### Description

The viewport snapshot is not showing the model. Rotating the model is also noticably slower than in vscode.

#### Reproduction Steps

1. python tools/scope.py cat_fountain/product:cad

#### Attached Commits

- `84e9c3d4`
- `677eb23a64cabdba0bb411d5f072ff29c4d78916`
- `5919a5dd`
- `d3e08b55`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:db38baf2 --> Verify Target Bug snapshot captures rendered 3D model and rotation responds with 60 FPS fluidity | `python tools/scope.py cat_fountain/product:cad`

#### Resolution Notes

Rendered Three.js scene camera directly in snapshot capture, enabled powerPreference high-performance, capped devicePixelRatio, and suppressed GPU readback stalls during orbit

#### Rejection Feedback

Enabled preserveDrawingBuffer in Three.js renderer and throttled rotation events via RAF to eliminate GPU readback stalls

-Rejected. Can u check if there’s any other way to increase rendfer speed in the widget?
