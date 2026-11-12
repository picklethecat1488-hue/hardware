# 🟢 `[BUG-RADIANT-SKIPPER-379]` UI scale selector defaults to 75% on load and fails to increase at 100% scale in scope workstation

- **UUID**: `ba1a0115-bea3-405a-bc29-4b4dc60cf46b`
- **ID**: `BUG-RADIANT-SKIPPER-379`
- **Status**: `CLOSED`
- **Severity**: `HIGH`
- **Category**: `UI`
- **Component**: `cat_fountain`
- **Created**: `2026-11-12 18:04:04 UTC`
- **Resolved**: `2026-11-12 20:53:06 UTC`
- **Accepted**: `2026-11-12 20:53:17 UTC`

#### Description

In provider/templates/scope.html.j2, uiScaleSelect lacked the selected attribute on option 100%, causing browsers to default to the first option (75%). Additionally, html and body were styled with 100vw and 100vh instead of 100%, preventing proper zoom viewport scaling, and localStorage persisted the false 75% state across reloads.

#### Attached Commits

- `5774f536`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:07ccb8f5 --> Verify UI scale selector defaults to 100% and scales properly | `python tools/scope.py`

#### Resolution Notes

Added selected attribute to option 100% in uiScaleSelect dropdown, changed root styles to width/height 100% instead of 100vw/100vh for zoom scaling, and updated initUiScale to default to 100% and auto-correct former erroneous 75% fallback.
