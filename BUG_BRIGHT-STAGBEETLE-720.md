# 🔴 `[BUG-BRIGHT-STAGBEETLE-720]` Hide CAD viewer widget controls in all modes and move navigation, tree, and ruler to sidebar

- **UUID**: `c4361ee2-b0f3-4f96-8e31-335d3d9c87af`
- **ID**: `BUG-BRIGHT-STAGBEETLE-720`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `carrier_board`
- **Created**: `2026-11-11 14:01:07 UTC`
- **Rejected**: `2026-11-11 18:22:38 UTC`

#### Description

The CAD controls in the CAD viewer widget show in PCB view. We should hide those cad controls (show only the CAD object) and move the CAD viewer functionality into the left panel

#### Reproduction Steps

1. python tools/scope.py carrier_board/carrier_board:cad

#### Attached Commits

- `84e9c3d4`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:f2f57f00 --> Verify CAD navigation and display controls appear in left Display panel and viewer overlay is hidden in PCB mode | `python tools/scope.py carrier_board/carrier_board:cad`

#### Resolution Notes

Hid CAD viewer controls overlay in PCB mode and added Display controls to sidebar panel

- Rejected, we should hide the CAD viewer controls in the CAD and simulate modes as well
- Update the Tree view to show/hide individual layers and components like the Tree view does in the VAD Viewer widget does
- Add a ruler (mm) to the quicker
- Maintain the Axis indicator, when we hide the CAD controls

#### Rejection Feedback

Hid CAD viewer controls overlay in PCB mode and added Display controls to sidebar panel

- Rejected, we should hide the CAD viewer controls in the CAD and simulate modes as well
- Update the Tree view to show/hide individual layers and components like the Tree view does in the VAD Viewer widget does
- Add a ruler (mm) to the quicker
- Maintain the Axis indicator, when we hide the CAD controls
