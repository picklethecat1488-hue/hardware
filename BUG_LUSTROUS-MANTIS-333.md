# 🟢 `[BUG-LUSTROUS-MANTIS-333]` Simulate mode play button does not run PyBullet physics simulation or timeline logs

- **UUID**: `f3f7eee9-b90f-42b0-94ce-40a40f317991`
- **ID**: `BUG-LUSTROUS-MANTIS-333`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 13:57:40 UTC`
- **Resolved**: `2026-11-11 22:02:03 UTC`
- **Rejected**: `2026-11-11 18:13:25 UTC`

#### Description

The play button does not work when I switch to “Simulate” mode. No fountain simulation actually plays, and there’s no way to click on individual rerun logs on the timeline.

#### Reproduction Steps

1. python tools/scope.py cat_fountain/simulation:simulate

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794434475191_82foj.png](attachments/BUG-LUSTROUS-MANTIS-333/screenshot_paste_1794434475191_82foj.png) | Pasted screenshot screenshot_paste_1794434475191_82foj.png |

#### Attached Commits

- `84e9c3d4`
- `c6a6039c1fad6b8c8351291c0842fdafb1a06d22`
- `5919a5dd`
- `d3e08b55`
- `7b5bbd30`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:bd000649 --> Verify play button animates simulation scrubber and non-applicable mode tabs are disabled | `python tools/scope.py cat_fountain/simulation:simulate`
- [ ] <!-- task:38de1d8e --> Verify play button animates fountain fluid particles and impeller with clickable rerun timeline logs | `python tools/scope.py cat_fountain/simulation:simulate`

#### Resolution Notes

Added fountain fluid particle simulation, rotating impeller animation, force repaint update loop, and clickable Rerun timeline log markers with live flow metrics

Rejected-I dstill don’t think this is working right. The physics particles appear incorrectly offset from the CAD geometry

#### Rejection Feedback

Filtered non-applicable modes, mapped cat_fountain/simulation alias to product:simulate, and wired simulation playback loop

-Simulate mode still doesn’t work. Only the CAD window is shown, not the pybullet fountain simulation
