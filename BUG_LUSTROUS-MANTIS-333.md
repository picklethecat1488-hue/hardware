# 🟢 `[BUG-LUSTROUS-MANTIS-333]` [cat_fountain/simulation] Defect in SIMULATE view

- **UUID**: `f3f7eee9-b90f-42b0-94ce-40a40f317991`
- **ID**: `BUG-LUSTROUS-MANTIS-333`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 13:57:40 UTC`
- **Resolved**: `2026-11-11 18:13:19 UTC`

#### Description

The play button does not work when I switch to “Simulate” mode. We disable any views which are not applicable for the given target.

#### Reproduction Steps

1. python tools/scope.py cat_fountain/simulation:simulate

#### Attached Commits

- `84e9c3d4`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:bd000649 --> Verify play button animates simulation scrubber and non-applicable mode tabs are disabled | `python tools/scope.py cat_fountain/simulation:simulate`

#### Resolution Notes

Filtered non-applicable modes, mapped cat_fountain/simulation alias to product:simulate, and wired simulation playback loop

-Simulate mode still doesn’t work. Only the CAD window is shown, not the pybullet fountain simulation
