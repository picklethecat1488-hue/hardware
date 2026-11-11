# 🟢 `[BUG-STRIDULATING-COCOON-33]` [carrier_board/carrier_board] Defect in PCB view

- **UUID**: `e513aac7-441d-4ac7-bb8d-1ae418306589`
- **ID**: `BUG-STRIDULATING-COCOON-33`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-11 13:59:41 UTC`
- **Resolved**: `2026-11-11 18:20:28 UTC`
- **Accepted**: `2026-11-11 18:20:34 UTC`

#### Description

Net highlighting shows 0 pins for everything

#### Reproduction Steps

1. python tools/scope.py carrier_board/carrier_board:pcb

#### Attached Commits

- `84e9c3d4`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:f7a17f1f --> Verify netlist panel displays non-zero pin counts for nets with connected component pads | `python tools/scope.py carrier_board/carrier_board:pcb`

#### Resolution Notes

Fixed net pin tuple parsing in pipeline PCB metadata extraction to format (refdes, pin) properly
