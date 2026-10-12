# 🟢 `[BUG-TRANSLUCENT-LARVA-792]` Motor clip interferes with the 1102 motor base

- **UUID**: `2b7ef56e-6d35-4c8a-9c8e-6f586aea730f`
- **ID**: `BUG-TRANSLUCENT-LARVA-792`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-10-10 23:00:34 UTC`
- **Resolved**: `2026-10-11 00:28:20 UTC`

#### Description

The motor clip interferes with the 1102 motor base; it is not possible to rotate the wiring connector into the correct position to install the motor base to the clip without cutting the motor clip. The motor clip needs to have more of an “Ṟ” shape. On my motor clip, I had to cut at the red lines to install the motor base into the clip properly on my bowl.

— Reopened this one. Can you please add some extra support where I indicated in the newly attached screenshot?

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [image.png](attachments/BUG-TRANSLUCENT-LARVA-792/image.png) | Uploaded screenshot image.png |
| `screenshot` | [Untitled 4.png](attachments/BUG-TRANSLUCENT-LARVA-792/Untitled 4.png) | Uploaded screenshot Untitled 4.png |

#### Resolution Notes

Added curved support web connecting the 10mm guide stub to the continuous right arm along the indicated radius curve (radius 15mm, rising 6mm from Y=-16 to Y=-10), providing solid mechanical bracing while keeping the side connector cutout open for motor base installation.
