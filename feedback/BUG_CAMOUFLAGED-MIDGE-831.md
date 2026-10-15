# 🟢 `[BUG-CAMOUFLAGED-MIDGE-831]` I don’t have a cyan wire color

- **UUID**: `bc1f616f-c211-4848-ad74-0eb516692200`
- **ID**: `BUG-CAMOUFLAGED-MIDGE-831`
- **Status**: `RESOLVED`
- **Severity**: `LOW`
- **Category**: `PCB`
- **Component**: `cat_fountain`
- **Created**: `2026-10-15 21:21:16 UTC`
- **Resolved**: `2026-10-15 21:29:02 UTC`

#### Description

Somehow, a cyan wire color has gotten into the cat fountain wiring diagram. I don’t have that color in my loom. Can we please remove it?

#### Resolution Notes

Removed cyan wire color from cat fountain wiring diagram by changing ctrl_uh net color to brown. Added regression test test_regression_bug_camouflaged_midge_831_no_cyan_wire_in_cat_fountain_wiring verifying zero nets use cyan and ctrl_uh uses brown.
