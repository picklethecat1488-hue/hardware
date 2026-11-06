# 🟢 `[BUG-THORACIC-HARVESTMAN-529]` Add grooves for triangular motor struts to drive hub

- **UUID**: `cdda94d6-e538-437c-9940-01516226d9ab`
- **ID**: `BUG-THORACIC-HARVESTMAN-529`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-05 15:06:09 UTC`
- **Resolved**: `2026-11-05 17:14:12 UTC`
- **Accepted**: `2026-11-06 00:15:08 UTC`

#### Description

As indicated on the mechanical drawing for the 1102 18000kv motor, there are 3 struts on the top of the motor frame which connect to the drive shaft. Can we add a triangular groove pattern with central hole to the bottom of the drive hub so that the struts can be fit into the drive hub bottom to prevent torque slippage without gluing. Additionally, can we revise the design of the drive hub to be a convex hull with minimum 1.5mm wall thickness around all magnets, grooves, and mounting holes. Desired shape outlined in green on the existing drive hub in one of the attached screenshots.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1793891547400_gyg0h.png](attachments/BUG-THORACIC-HARVESTMAN-529/screenshot_paste_1793891547400_gyg0h.png) | Pasted screenshot screenshot_paste_1793891547400_gyg0h.png |
| `screenshot` | [screenshot_paste_1793891379527_mc2d2.png](attachments/BUG-THORACIC-HARVESTMAN-529/screenshot_paste_1793891379527_mc2d2.png) | Pasted screenshot screenshot_paste_1793891379527_mc2d2.png |

#### Attached Commits

- `3768254b`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:705f2746 --> Inspect drive hub bottom face to verify triangular motor strut clearance grooves | `python tools/view.py cat_fountain/drive_hub`

#### Resolution Notes

Add triangular motor strut grooves to drive hub bottom and refactor drive hub body to a 3-lobed convex hull with >=1.5mm wall thickness around all magnets, grooves, and shaft hole.
