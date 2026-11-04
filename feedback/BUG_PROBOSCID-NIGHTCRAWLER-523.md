# 🟢 `[BUG-PROBOSCID-NIGHTCRAWLER-523]` Some overlaps still visible on the wiring diagram

- **UUID**: `5908e663-093a-415d-903a-0140e610a6d9`
- **ID**: `BUG-PROBOSCID-NIGHTCRAWLER-523`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `PCB`
- **Component**: `cat_fountain`
- **Created**: `2026-10-11 00:15:58 UTC`
- **Resolved**: `2026-10-11 00:35:15 UTC`

#### Description

Can you please resolve the remaining wiring diagram overlaps? Attached

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [Untitled 3.png](attachments/BUG-PROBOSCID-NIGHTCRAWLER-523/Untitled 3.png) | Uploaded screenshot Untitled 3.png |
| `screenshot` | [Untitled 1.png](attachments/BUG-PROBOSCID-NIGHTCRAWLER-523/Untitled 1.png) | Uploaded screenshot Untitled 1.png |
| `screenshot` | [Untitled 2.png](attachments/BUG-PROBOSCID-NIGHTCRAWLER-523/Untitled 2.png) | Uploaded screenshot Untitled 2.png |

#### Resolution Notes

Fixed component label positions in WiringDiagram to honor footprint label.position and label.align from wiring.yaml (resolving RGB LED overlapping DIN and BQ25185 overlapping BAT-/GND), simplified Pico power/GND pin labels to GND/VSYS/3V3 to eliminate 3(GND)/38(GND) collisions across the package, and re-exported SVGs.
