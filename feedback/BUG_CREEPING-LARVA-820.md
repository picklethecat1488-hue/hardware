# 🟢 `[WORM-CREEPING-LARVA-820]` Regression tests are not useful

- **UUID**: `c9679ffa-7211-4f3f-bea5-a57be3bc91a4`
- **ID**: `WORM-CREEPING-LARVA-820`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `GENERAL`
- **Created**: `2026-10-23 00:51:04 UTC`
- **Resolved**: `2026-10-23 01:03:28 UTC`

#### Description

I noticed some regression tests are silly and not useful, and only wrap other test cases. If a test case that a bug is meant to fix does not check for the bug, can we instead update the original test case directly if possible? If not possible to unit test a regression fix, it is preferable to omit a regression test if it does not do anything new. Can we please remove these types of useless regression tests in both hardware and firmware repos, as well as update learnings about regression test best practices.

#### Execution / Console Logs

```text
42
+
def test_worm_organic_fireworm_553_short_protection_and_diag():
43
+
    """Verify short protection pulse bounds and DIAG fault handling in integration test suites."""
44
+
    cmd_pulse = [
45
+
        "cargo",
46
+
        "test",
47
+
        "--package",
48
+
        "peripheral",
49
+
        "--test",
50
+
        "integration",
51
+
        "test_worm_slithering_lumbricus_809_tmc6300_short_protection_pulse_invariants",
52
+
        "--",
53
+
        "--nocapture",
54
+
    ]
55
+
    proc_pulse = subprocess.run(cmd_pulse, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
56
+
    assert proc_pulse.returncode == 0, f"peripheral pulse test failed:\n{proc_pulse.stdout}\n{proc_pulse.stderr}"
57
+
58
+
    cmd_fault = [
59
+
        "cargo",
60
+
        "test",
61
+
        "--package",
62
+
        "controller",
63
+
        "--test",
64
+
        "controller_tests",
65
+
        "test_worm_peaty_bobbit_630_motor_tick_driver_fault_stops_ticking",
66
+
        "--",
67
+
        "--nocapture",
68
+
    ]
69
+
    proc_fault = subprocess.run(cmd_fault, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
70
+
    assert proc_fault.returncode == 0, f"controller fault test failed:\n{proc_fault.stdout}\n{proc_fault.stderr}"
```

#### Resolution Notes

Removed redundant and useless shallow regression test wrappers that only wrapped other test suites or cargo tests. Codified regression test best practice rules in GEMINI.md across firmware and hardware repos, prohibiting shallow test wrappers, requiring direct updates to original test cases, and preferring omission when logical invariants are already verified.
