# 🟢 `[BUG-FOSSORIAL-BRISTLE-291]` RP2040 pinout-uynreadible mess

- **UUID**: `7edf7011-55ec-4e80-ac60-eb39ab7bdb30`
- **ID**: `BUG-FOSSORIAL-BRISTLE-291`
- **Status**: `RESOLVED`
- **Severity**: `CRITICAL`
- **Category**: `PCB`
- **Component**: `cat_fountain`
- **Created**: `2026-10-10 23:13:31 UTC`
- **Resolved**: `2026-10-10 23:47:06 UTC`

#### Description

The RP2040 pinout on the wiring diagram is total unreadable garbage (see attached) I propose the following solution: name all the pins on the board according to their GPIO PIN numbers, then keep VSYS, 3V3, and GND intact. Create a separate key in one of the diagram corners mapping the RP2040 GPIOs to net names; keeping the same orientation and color coding of nets on the key as on the wiring diagram.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [image.png](attachments/BUG-FOSSORIAL-BRISTLE-291/image.png) | Uploaded screenshot image.png |

#### Resolution Notes

Simplified RP2040 pin labels on the board to just GPIO numbers (GPx) while keeping power/GND pins intact, and added a dedicated RP2040 GPIO pinout key in the bottom-left corner of the wiring diagram preserving left/right column orientation and net color coding.
