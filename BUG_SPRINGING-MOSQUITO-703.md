# 🟢 `[BUG-SPRINGING-MOSQUITO-703]` Extend inner wall to surface of ToF sensor PCB

- **UUID**: `c78f3b26-9aa7-4944-bc63-66740f0ef2db`
- **ID**: `BUG-SPRINGING-MOSQUITO-703`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-10-23 23:00:18 UTC`
- **Resolved**: `2026-10-23 23:55:57 UTC`
- **Accepted**: `2026-10-23 23:55:57 UTC`

#### Description

Can we please extend the inner wall of the proximity sensor openings down another 3mm to interface with the top of the ToF sensor PCB in order to compensate for ambient light leakage from the top of the PCB?

#### Resolution Notes

Extended inner wall of proximity sensor openings down 3mm to interface with top of ToF sensor PCB to prevent ambient light leakage; parameterized proximity_sensor_inner_wall_extension in measurements.yaml and config.
