# 🔴 `[BUG-SEGMENTED-MOTH-70]` New Bug Report

- **UUID**: `2b254ab4-aaab-4a35-8d14-7aee1b2d1a5f`
- **ID**: `BUG-SEGMENTED-MOTH-70`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `Scope`
- **Created**: `2026-11-11 00:17:25 UTC`

#### Description

The terminal doesn’t detach when opening viewer/scope, unlike forge.py. See output below

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
