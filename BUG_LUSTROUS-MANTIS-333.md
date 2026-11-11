# 🟢 `[BUG-LUSTROUS-MANTIS-333]` Simulate mode play button does not play physics simulation and timeline lacks clickable rerun logs (cat_fountain)

- **UUID**: `f3f7eee9-b90f-42b0-94ce-40a40f317991`
- **ID**: `BUG-LUSTROUS-MANTIS-333`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 13:57:40 UTC`
- **Resolved**: `2026-11-11 23:21:19 UTC`
- **Accepted**: `2026-11-11 23:21:30 UTC`
- **Rejected**: `2026-11-11 22:02:10 UTC`

#### Description

The play button does not work when I switch to “Simulate” mode. No fountain simulation actually plays, and there’s no way to click on individual rerun logs on the timeline.

#### Reproduction Steps

1. python tools/scope.py cat_fountain/simulation:simulate

#### Attached Commits

- `84e9c3d4`
- `c6a6039c1fad6b8c8351291c0842fdafb1a06d22`
- `5919a5dd`
- `d3e08b55`
- `7b5bbd30`
- `94796ad2`
- `e40dabc6`
- `5f2d077a`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:bd000649 --> Verify play button animates simulation scrubber and non-applicable mode tabs are disabled | `python tools/scope.py cat_fountain/simulation:simulate`
- [ ] <!-- task:38de1d8e --> Verify play button animates fountain fluid particles and impeller with clickable rerun timeline logs | `python tools/scope.py cat_fountain/simulation:simulate`
- [ ] <!-- task:98106dc2 --> Verify cat fountain simulate mode physics particles originate at pump (0, 0, 44), ascend vertical tube (0, 28) to spout apex Z=114.5, spread across lid tray Z=105, cascade down waterfall to reservoir pool above floor Z=41, and timeline logs scrub smoothly | `python tools/scope.py cat_fountain/product:simulate`

#### Resolution Notes

Corrected Scope simulation fluid particle trajectory coordinates to match exact CAD assembly boundaries: pump intake and volute at Z=44-46, vertical delivery tube at (0, 28) ascending to spout apex Z=114.5, lid drinking tray at Z=105.0, waterfall cascading to reservoir pool between Z=44.0 and 68.0 strictly above floor Z=41.0.

#### Rejection Feedback

Added fountain fluid particle simulation, rotating impeller animation, force repaint update loop, and clickable Rerun timeline log markers with live flow metrics

Rejected-I dstill don’t think this is working right. The physics particles appear incorrectly offset from the CAD geometry
