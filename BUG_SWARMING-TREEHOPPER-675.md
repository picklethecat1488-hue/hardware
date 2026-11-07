# 🟢 `[BUG-SWARMING-TREEHOPPER-675]` Drive hub shaft through-hole blocked at thrust collar

- **UUID**: `79f76b9e-efbb-4628-8f3e-58c69539039a`
- **ID**: `BUG-SWARMING-TREEHOPPER-675`
- **Status**: `CLOSED`
- **Severity**: `HIGH`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-07 02:28:05 UTC`
- **Resolved**: `2026-11-07 02:28:13 UTC`
- **Accepted**: `2026-11-07 02:28:13 UTC`

#### Description

The drive hub motor shaft through-hole cut in _build_drive_hub_impl uses align=(Align.CENTER, Align.CENTER, Align.CENTER) centered at Z=0. This leaves the upper section through the thrust collar solid, blocking shaft insertion.

#### Attached Commits

- `26ee19ce`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:75f6c5ab --> Verify drive hub builds and motor shaft hole is open through the thrust collar | `python tools/build.py cat_fountain/drive_hub && python tools/view.py cat_fountain/drive_hub`

#### Resolution Notes

Replaced centered cylinder cut with bottom-anchored through-cylinder (align Align.MIN starting at Z=-1) so the shaft hole extends through the entire hub and upper thrust collar.
