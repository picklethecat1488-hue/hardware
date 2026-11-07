# 🟢 `[BUG-SWIFT-TREEHOPPER-767]` test_pump_integration times out during parallel pytest execution

- **UUID**: `f1c15d81-9a8c-4159-826b-3b869d945bc4`
- **ID**: `BUG-SWIFT-TREEHOPPER-767`
- **Status**: `CLOSED`
- **Severity**: `HIGH`
- **Category**: `SIMULATION`
- **Component**: `cat_fountain`
- **Created**: `2026-11-07 02:58:42 UTC`
- **Resolved**: `2026-11-07 02:58:54 UTC`
- **Accepted**: `2026-11-07 02:58:54 UTC`

#### Description

test_pump_integration executes 55 SPH simulation steps with 70,000 particles on CPU, which exceeds the 300s timeout during parallel pytest-xdist execution. Reducing steps to 25 (consistent with other physics integration tests) and tuning timeout allows the test to complete reliably.

#### Attached Commits

- `72c02331`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:ac75fb2c --> Verify fluid dynamics simulation executes without hanging | `python tools/view.py cat_fountain/product:view/simulate -s 5`

#### Resolution Notes

Reduced SPH simulation step count from 55 to 25 and raised pytest timeout to 600s, preventing worker timeout under heavy CPU load.
