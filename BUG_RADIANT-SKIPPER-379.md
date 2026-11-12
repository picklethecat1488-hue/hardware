# 🔴 `[BUG-RADIANT-SKIPPER-379]` UI scale selector defaults to 75% on load and fails to increase at 100% scale in scope workstation

- **UUID**: `ba1a0115-bea3-405a-bc29-4b4dc60cf46b`
- **ID**: `BUG-RADIANT-SKIPPER-379`
- **Status**: `OPEN`
- **Severity**: `HIGH`
- **Category**: `UI`
- **Component**: `cat_fountain`

#### Description

In provider/templates/scope.html.j2, uiScaleSelect lacked the selected attribute on option 100%, causing browsers to default to the first option (75%). Additionally, html and body were styled with 100vw and 100vh instead of 100%, preventing proper zoom viewport scaling, and localStorage persisted the false 75% state across reloads.
