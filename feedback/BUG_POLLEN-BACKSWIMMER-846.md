# 🟢 `[BUG-POLLEN-BACKSWIMMER-846]` TMC6300-clip on mounts are too big

- **UUID**: `0424b68a-c813-4d2e-95c4-52985f5e20fb`
- **ID**: `BUG-POLLEN-BACKSWIMMER-846`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-10-23 23:05:10 UTC`
- **Resolved**: `2026-10-23 23:34:19 UTC`

#### Description

The clip on mounts of the TMC6300 are too big for the board to clip into. The board measures approx 20mm by 15mm. Additionally, the “TMC6300” text should be moved to the opposite side of the board so it isnt too close to the “CURRENT” text.

#### Resolution Notes

Updated TMC6300 board dimensions and clip mount spacing to 20.0x15.0mm in measurements.yaml and wiring.yaml. Moved engraved TMC6300 text to positive Y side of board to eliminate proximity to CURRENT text. Added dedicated regression unit test test_regression_bug_pollen_backswimmer_846_tmc6300_clip_mount_dimensions_and_text.
