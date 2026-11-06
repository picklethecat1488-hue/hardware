# 🟢 `[BUG-LUSTROUS-COCOON-669]` Motor base design is way too complicated

- **UUID**: `13875eb9-23cd-4e48-8250-856f02d7bfa1`
- **ID**: `BUG-LUSTROUS-COCOON-669`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-05 14:54:50 UTC`
- **Resolved**: `2026-11-06 00:24:42 UTC`
- **Rejected**: `2026-11-06 00:16:51 UTC`

#### Description

The design of the motor base is way too complicated. The overall design should be a circle unioned with a rectangle to mount the hall sensor on. The hall sensor mount should fit into a gap in the motor wall to prevent rotation during spinning. 

There should be a total of 3 mounting holes on the bottom. All cabling can be routed through the opening on the side of the motor wall created for the hall sensor.

Additionally, there’s latent cuts in the bottom of the bowl from when the drive hub had to slide in from the side that need to be removed, as well as an extra box above the hall sensor mounting point.

Defects circled in red.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1793924149979_7f535.png](attachments/BUG-LUSTROUS-COCOON-669/screenshot_paste_1793924149979_7f535.png) | Pasted screenshot screenshot_paste_1793924149979_7f535.png |
| `screenshot` | [screenshot_paste_1793890911006_wvg54.png](attachments/BUG-LUSTROUS-COCOON-669/screenshot_paste_1793890911006_wvg54.png) | Pasted screenshot screenshot_paste_1793890911006_wvg54.png |
| `screenshot` | [screenshot_paste_1793890876309_0c9ae.png](attachments/BUG-LUSTROUS-COCOON-669/screenshot_paste_1793890876309_0c9ae.png) | Pasted screenshot screenshot_paste_1793890876309_0c9ae.png |

#### Attached Commits

- `7185e819`
- `8a440bce`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:aae67eb7 --> Inspect simplified circular motor base geometry with 3-screw pattern | `python tools/view.py cat_fountain/motor_hub`
- [ ] <!-- task:09c39078 --> Inspect bowl socket wall to verify clean hall sensor keyway cutout with no thin slivers | `python tools/view.py cat_fountain/bowl`

#### Resolution Notes

Simplified motor base to circle unioned with hall sensor rectangular tongue; eliminated thin sliver walls under hall sensor cutout by extending socket keyway cut from inner bore.
