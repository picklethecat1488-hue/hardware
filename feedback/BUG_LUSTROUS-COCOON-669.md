# 🟢 `[BUG-LUSTROUS-COCOON-669]` Motor base design is way too complicated

- **UUID**: `13875eb9-23cd-4e48-8250-856f02d7bfa1`
- **ID**: `BUG-LUSTROUS-COCOON-669`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-05 14:54:50 UTC`
- **Resolved**: `2026-11-05 17:09:52 UTC`

#### Description

The design of the motor base is way too complicated. The overall design should be a circle unioned with a rectangle to mount the hall sensor on. The hall sensor mount should fit into a gap in the motor wall to prevent rotation during spinning. 

There should be a total of 3 mounting holes on the bottom. All cabling can be routed through the opening on the side of the motor wall created for the hall sensor.

Additionally, there’s latent cuts in the bottom of the bowl from when the drive hub had to slide in from the side that need to be removed, as well as an extra box above the hall sensor mounting point.

Defects circled in red.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1793890911006_wvg54.png](attachments/BUG-LUSTROUS-COCOON-669/screenshot_paste_1793890911006_wvg54.png) | Pasted screenshot screenshot_paste_1793890911006_wvg54.png |
| `screenshot` | [screenshot_paste_1793890876309_0c9ae.png](attachments/BUG-LUSTROUS-COCOON-669/screenshot_paste_1793890876309_0c9ae.png) | Pasted screenshot screenshot_paste_1793890876309_0c9ae.png |

#### Attached Commits

- `7185e819`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:aae67eb7 --> Inspect simplified circular motor base geometry with 3-screw pattern | `python tools/view.py cat_fountain/motor_hub`

#### Resolution Notes

Simplify motor base to a circle unioned with a hall sensor mounting rectangle fitting into socket wall keyway gap; ensure 3 mounting holes on bottom; remove latent south slide cut and extra box above hall sensor in bowl.
