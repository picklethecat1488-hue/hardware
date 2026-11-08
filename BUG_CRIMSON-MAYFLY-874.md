# 🟢 `[BUG-CRIMSON-MAYFLY-874]` Drive hub-insufficient clearance for hall sensor board

- **UUID**: `692f0251-d8f8-40be-b255-5414be49c8de`
- **ID**: `BUG-CRIMSON-MAYFLY-874`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Created**: `2026-11-07 00:23:00 UTC`
- **Resolved**: `2026-11-07 01:23:47 UTC`
- **Accepted**: `2026-11-07 01:23:50 UTC`

#### Description

The drive hub has insufficient clearance for the hall sensor board; the opening is too narrow for the sensor to fit thru. There is also an unexpected second opening opposite the hall sensor. Defects highlighted in red on the attached screenshot, and desired sensor clearance in green.

#### Attached Commits

- `b1d14ba5b2740f295c23320db2e2d82bebccd03b`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:10c182f6 --> Inspect 3D CAD view of cat_fountain motor_hub to verify wide Hall sensor collar opening and solid South collar wall | `python tools/view.py cat_fountain/motor_hub:part`

#### Resolution Notes

Widened motor hub collar opening to 16.0mm across Hall sensor tongue and eliminated accidental opposite slit at South wall
