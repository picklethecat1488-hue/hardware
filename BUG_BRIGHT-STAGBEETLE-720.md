# 🟢 `[BUG-BRIGHT-STAGBEETLE-720]` [carrier_board/carrier_board] Defect in CAD view

- **UUID**: `c4361ee2-b0f3-4f96-8e31-335d3d9c87af`
- **ID**: `BUG-BRIGHT-STAGBEETLE-720`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `carrier_board`
- **Created**: `2026-11-11 14:01:07 UTC`
- **Resolved**: `2026-11-11 14:27:38 UTC`

#### Description

The CAD controls in the CAD viewer widget show in PCB view. We should hide those cad controls (show only the CAD object) and move the CAD viewer functionality into the left panel

#### Reproduction Steps

1. python tools/scope.py carrier_board/carrier_board:cad

#### Review Tasks & Functional Checklist

- [ ] <!-- task:f2f57f00 --> Verify CAD navigation and display controls appear in left Display panel and viewer overlay is hidden in PCB mode | `python tools/scope.py carrier_board/carrier_board:cad`

#### Resolution Notes

Hid CAD viewer controls overlay in PCB mode and added Display controls to sidebar panel
