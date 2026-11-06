# 🟢 `[BUG-FIERCE-LONGHORN-849]` SWD and TMC6300 mounts- unsufficient snap ring overlap

- **UUID**: `04ef79bc-f57b-442f-8969-9dba1c94909f`
- **ID**: `BUG-FIERCE-LONGHORN-849`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-06 06:40:24 UTC`
- **Resolved**: `2026-11-06 17:19:36 UTC`

#### Description

There is insufficient snap ring overlap to hold the SWD and TMC6300 boards in place. The width and height of the cutout surrounding the boards should be the width and height of the boards - some very small margin (.1mm-.5mm). Attached screenshot showing the defects in red.

Additionally, we should add holes on each wall to allow a small tool such as an allen wrench to be inserted beneath the boards to pop them out. Attached a second screenshow showing the desired hole locations in green (TMC6300).

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1793948449522_d1ck8.png](attachments/BUG-FIERCE-LONGHORN-849/screenshot_paste_1793948449522_d1ck8.png) | Pasted screenshot screenshot_paste_1793948449522_d1ck8.png |
| `screenshot` | [screenshot_paste_1793947358948_g28nw.png](attachments/BUG-FIERCE-LONGHORN-849/screenshot_paste_1793947358948_g28nw.png) | Pasted screenshot screenshot_paste_1793947358948_g28nw.png |

#### Attached Commits

- `4f468fef`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:142f51c1 --> Inspect SWD and TMC6300 snap sockets in 3D viewer | `python tools/view.py cat_fountain/product:view`

#### Resolution Notes

Configured pcb_snap_socket_cutout_margin to 0.4mm for positive snap ring overlap holding SWD and TMC6300 boards

Rejected— the side openings for inserting a board removal tool into the mount are missing from the design.
