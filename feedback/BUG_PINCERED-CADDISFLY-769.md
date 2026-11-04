# 🟢 `[BUG-PINCERED-CADDISFLY-769]` Add clip on mount for SWD header

- **UUID**: `39e27e43-1d69-4cde-9de4-819864d10df9`
- **ID**: `BUG-PINCERED-CADDISFLY-769`
- **Status**: `RESOLVED`
- **Severity**: `LOW`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-10-23 23:10:52 UTC`
- **Resolved**: `2026-10-23 23:48:48 UTC`

#### Description

Can we please add a clip on mounting boss for the SWD PCB I’m using:

Treedix JTAG Breakout Board Adapter

https://www.amazon.com/dp/B09DKDG7XN?ref=ppx_yo2ov_dt_b_fed_asin_title

Right now, I just have it taped in place.

#### Resolution Notes

Added clip-on mounting boss for Treedix JTAG/SWD Breakout Board Adapter (19.1x13.7mm) at (-50.0, -45.0) in cat fountain dry compartment. Added swd_adapter footprint to wiring.yaml. Added dedicated regression unit test test_regression_bug_pincered_caddisfly_769_swd_clip_mount.
