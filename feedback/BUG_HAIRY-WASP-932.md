# 🟢 `[BUG-HAIRY-WASP-932]` Update TMC6300 wiring to 6-PWM GPIO control and decouple SEN pin (WORM-GLIDING-BRISTLE-252)

- **UUID**: `146f6268-0981-4761-ad81-d040b71ecedb`
- **ID**: `BUG-HAIRY-WASP-932`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `PCB`
- **Component**: `cat_fountain`
- **Created**: `2026-10-15 21:12:56 UTC`
- **Resolved**: `2026-10-15 21:22:37 UTC`

#### Description

TMC6300 3-phase BLDC driver in cat_fountain requires 6 independent PWM/GPIO inputs (UH, UL, VH, VL, WH, WL) for proper 3-phase commutation. Disconnect the bridged inputs (IN1, IN2, IN3) and allocate GP16..GP21 for 6-PWM control (UH=GP16, UL=GP17, VH=GP18, VL=GP19, WH=GP20, WL=GP21) with DIAG on GP22. The TMC6300 breakout SEN pin (intended for attaching an analog current monitor) is left disconnected from MCU GPIO/ADC in favor of dedicated INA219 current monitoring on the 5V boost rail. Preserve the AH3577 Hall speed sensor on GP26 for contactless impeller rotation speed monitoring.

#### Resolution Notes

Reconfigured TMC6300 motor driver wiring to 6-PWM GPIO control across GP16..GP21 (UH, UL, VH, VL, WH, WL) with DIAG on GP22. Left the breakout's SEN pin decoupled from MCU GPIO/ADC as motor current monitoring is performed over I2C by the INA219 sensor. Preserved the AH3577 Hall speed sensor and speed_sense net on GP26. Updated RP2040 GPIO key and TMC6300 pin key definitions, and added regression test coverage.
