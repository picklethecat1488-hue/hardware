# 🟢 `[BUG-PUNCTATE-INSTAR-79]` Carrier board components are misaligned

- **UUID**: `178f5030-8568-4410-ab0a-4a6cc9d1ed73`
- **ID**: `BUG-PUNCTATE-INSTAR-79`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-10 00:37:19 UTC`
- **Resolved**: `2026-11-10 14:10:02 UTC`

#### Description

Carrier board PCB components are misaligned and clipping through the bottom of the PCB

#### Reproduction Steps

1. $ python tools/view.py carrier_board/carrier_board:pcb

#### Attached Commits

- `7306d322149deb5db864bbd70d2aab8b9e541bfe`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:174dda99 --> Verify carrier board components and copper traces are visible and not clipping in 3D CAD viewer | `python tools/view.py carrier_board/carrier_board:pcb --no-gui`

#### Resolution Notes

Aligned substrate bounds to 3D substrate geometry and offset component package bodies by local bounding box to prevent clipping through PCB; elevated traces and pads proud of substrate surface
