# 🟢 `[BUG-SPECKLED-ROVEBEETLE-352]` Sensor shield design on inner bowl wall is too complicated

- **UUID**: `e4f40739-f0ba-495c-9426-ad99f73a67d0`
- **ID**: `BUG-SPECKLED-ROVEBEETLE-352`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-05 14:44:07 UTC`
- **Resolved**: `2026-11-05 16:25:54 UTC`
- **Accepted**: `2026-11-06 00:18:37 UTC`

#### Description

The sensor shield on the inner bowl wall is too complicated. The shape should be an extruded, hollow rectangle. Right now, there is an inner lip on the inside ofthe bowl wall, as well as two tails. See screenshot below. The red lines mark defects in the shape, while the green line marks the desired shape.

#### Attached Commits

- `5821d84e`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:ddd2df40 --> Inspect simplified sensor shield and verify clear clearance with bottom cover | `python tools/view.py cat_fountain/bottom_cover`

#### Resolution Notes

Simplify proximity sensor shield on inner bowl wall to an extruded hollow rectangle centered on pocket opening, eliminating inner lip and protruding tails.
