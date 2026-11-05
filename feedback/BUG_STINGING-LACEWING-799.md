# 🟢 `[BUG-STINGING-LACEWING-799]` Mounting system for hole-less PCBs is too complicated

- **UUID**: `1843fe5a-0485-4e4c-a4e0-f555e9af7e1a`
- **ID**: `BUG-STINGING-LACEWING-799`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-05 14:49:40 UTC`
- **Resolved**: `2026-11-05 17:04:16 UTC`

#### Description

Giving the TMC6300 mounting system as an example below, there are micro-gaps between the mounting rales, inner shells, and the rail system will not work if a current sensor is already installed. Can we simplify this design, and switch to a snap ring system (assuming the sides of the PCB function as the inner ring) similar to the bowl to lid and bowl to bottom connections? The defects are marked with red.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1793890436150_8301p.png](attachments/BUG-STINGING-LACEWING-799/screenshot_paste_1793890436150_8301p.png) | Pasted screenshot screenshot_paste_1793890436150_8301p.png |

#### Resolution Notes

Replaced slide-in guide rail system for hole-less PCBs with axial snap-socket frame featuring an internal perimeter snap groove and entrance lead-in chamfer, eliminating micro-gaps and assembly collision with current sensor.
