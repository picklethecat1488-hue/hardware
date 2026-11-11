# 🟢 `[BUG-RUSTY-HORNET-486]` [carrier_board/carrier_board] Defect in PCB view

- **UUID**: `49c3ab3e-6eb3-4772-baa2-92d432595530`
- **ID**: `BUG-RUSTY-HORNET-486`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-11 00:19:56 UTC`
- **Resolved**: `2026-11-11 00:44:17 UTC`

#### Description

When syncing for loading viewer.py with a target, we should show a modal progress bar UI indicating exactly what stage of the sync process we are in.

#### Reproduction Steps

1. python tools/scope.py carrier_board/carrier_board:pcb

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `image/png` | [snapshot.png](attachments/BUG-RUSTY-HORNET-486/snapshot.png) | 3D CAD/PCB annotated WebGL viewport snapshot |

#### Resolution Notes

Added staged modal progress bar UI during workstation sync, target switching, and geometry loading.
