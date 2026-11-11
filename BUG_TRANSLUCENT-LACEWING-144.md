# 🟢 `[BUG-TRANSLUCENT-LACEWING-144]` [carrier_board/carrier_board] Defect in PCB view

- **UUID**: `cf9a924c-9c73-4e4c-b249-6be0475c8f46`
- **ID**: `BUG-TRANSLUCENT-LACEWING-144`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-11 13:59:20 UTC`
- **Resolved**: `2026-11-11 18:19:57 UTC`

#### Description

Net highlighting does not work. We should also use a high contrast color scheme that makes PCB components more obvious when in PCB view, similar to what kicad uses

#### Reproduction Steps

1. python tools/scope.py carrier_board/carrier_board:pcb

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794421069036_kjvhz.png](attachments/BUG-TRANSLUCENT-LACEWING-144/screenshot_paste_1794421069036_kjvhz.png) | Pasted screenshot screenshot_paste_1794421069036_kjvhz.png |

#### Attached Commits

- `84e9c3d4`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:cbd6bdbb --> Verify PCB copper layers use KiCad high-contrast palette and active nets illuminate on click | `python tools/scope.py carrier_board/carrier_board:pcb`

#### Resolution Notes

Updated PCB layer colors to KiCad palette and added active net pad/trace glow in 3D viewer

-Net highlighting still does not work, but the net colors look correct. 
-The PCB is still not in a high contrast color scheme (attached screenshot)
-Selecting/deselecting layers doesn’t do anything
-We are missing the quickbar on the right to change PCB views that is present in the CAD view
-The inspect view should give info about the highlighted component/net/trace/via in addition to CAD info
