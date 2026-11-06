# 🟢 `[BUG-SPECKLED-ROACH-49]` Pump cover should snap into place

- **UUID**: `5f81d6b7-6ce8-4fd3-a1c5-54e9ee014af2`
- **ID**: `BUG-SPECKLED-ROACH-49`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-06 04:28:00 UTC`
- **Resolved**: `2026-11-06 04:54:50 UTC`

#### Description

Right now, the pump cover may move freely up and down the shaft. We should use the same clip ring system used by the bowl to cover and lid to bottom cover connections to ensure the pump cover remains connected tightly to the bowl once in place.

#### Attached Commits

- `d0ab5f6a`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:a6119fc8 --> Inspect assembled cat fountain pump cover snap fit on volute casing | `python tools/view.py cat_fountain/product:view`

#### Resolution Notes

Added annular snap-fit ridge to pump cover downward lip and matching internal snap groove to casing recess on bowl (BUG-SPECKLED-ROACH-49)
