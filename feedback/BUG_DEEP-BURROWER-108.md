# 🟢 `[BUG-DEEP-BURROWER-108]` Wiring diagram- pin discrepancy on TMC 6300

- **UUID**: `4067b6ef-8bec-42fe-9c9c-680966c0b020`
- **ID**: `BUG-DEEP-BURROWER-108`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `cat_fountain`
- **Created**: `2026-10-10 23:07:44 UTC`
- **Resolved**: `2026-10-11 00:07:45 UTC`

#### Description

There is a pinout discrepency on the TMC6300 part I’m using from Sparkfun. The wiring diagram has different signal names for the input and output lines than the actual board. Since we are bridging high and low signals; can you create a key mapping the input bridges to UL, UH, VL, VH, and WL WH on the board and place it in the top right of the wiring diagram, and rename the output signals to U, V, and H. See screenshots below for comparison.w

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [image.png](attachments/BUG-DEEP-BURROWER-108/image.png) | Uploaded screenshot image.png |
| `screenshot` | [Untitled.png](attachments/BUG-DEEP-BURROWER-108/Untitled.png) | Uploaded screenshot Untitled.png |

#### Resolution Notes

Renamed TMC6300 motor_driver output pins and wire endpoints from OUT1, OUT2, OUT3 to U, V, W to match the SparkFun breakout silkscreen, added a dedicated TMC6300 pin key in the top-right corner of the wiring diagram mapping input bridges (IN1->UL/UH, IN2->VL/VH, IN3->WL/WH) and motor phase outputs, re-exported SVGs, and added regression tests.
