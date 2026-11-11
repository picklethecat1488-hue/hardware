# 🟢 `[BUG-SEGMENTED-MOTH-70]` New Bug Report

- **UUID**: `2b254ab4-aaab-4a35-8d14-7aee1b2d1a5f`
- **ID**: `BUG-SEGMENTED-MOTH-70`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `Scope`
- **Created**: `2026-11-11 00:17:25 UTC`
- **Resolved**: `2026-11-11 18:08:38 UTC`
- **Accepted**: `2026-11-11 18:08:44 UTC`
- **Rejected**: `2026-11-11 00:45:51 UTC`

#### Description

The terminal doesn’t detach when opening viewer/scope, unlike forge.py. See output below

#### Behavior Comparison

- **Expected**: $ python tools/scope.py carrier_board/carrier_board:pcb
- **Actual**: $ python tools/scope.py carrier_board/carrier_board:pcb

#### Execution / Console Logs

```text
$ python tools/viewer.py
pybullet build time: Oct 20 2025 08:05:00
⠙ Building...◈ QUAKE CAD/PCB WORKSTATION ◈
  Target: carrier_board/carrier_board [PCB]
  URL:    http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB
⠋ Building...Using port 3939
⠦ Building...CameraKeepWarning: reset_camera is set to KEEP. If shown objects are not visible use the 'resize' and a 'view' button
⠼ Building...face 46 ignored
⠙ Building...face 46 ignored
⠹ Building...Desktop window closed; shutting down viewer server...
(cq)
```

#### Attached Commits

- `1a402490`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:4905b55c --> Verify Scope CLI detaches from terminal when launched and terminates cleanly with stop | `python tools/scope.py --help`
- [ ] <!-- task:2839c851 --> Verify Scope detaches cleanly with zero stdout/stderr noise | `python tools/scope.py carrier_board/carrier_board:pcb --no-app`
- [ ] <!-- task:b3162e48 --> Verify Scope terminates cleanly with stop command | `python tools/scope.py stop`

#### Resolution Notes

Eliminated terminal noise on detaching, added structured logging, resolved 10s socket timeout, fixed 512x512 app icon scaling and alpha transparency, added panel resizer, UI scale controls, Quake theme styling, inline pin and text editing, fixed Three-CAD-Viewer 'tab' destructuring error, and brought load time from >20s to <2s with disk caching, background pre-warming, and gzip streaming.

#### Rejection Feedback

Added terminal detaching by default with --no-detach and --foreground flags and stop command matching forge.py.

There is still some extra printing to stdout that I’d like cleaned up. Can you check under “Expected Behavior” and “Actual Behavior"
