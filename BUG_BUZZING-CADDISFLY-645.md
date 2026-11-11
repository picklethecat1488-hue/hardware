# 🟢 `[BUG-BUZZING-CADDISFLY-645]` [cat_fountain/product] Defect in CAD view

- **UUID**: `9bfe7c94-8152-4469-8ba0-7ced48a27a38`
- **ID**: `BUG-BUZZING-CADDISFLY-645`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 00:15:49 UTC`
- **Resolved**: `2026-11-11 00:31:11 UTC`

#### Description

For text entry, ala pins, can we have a non-modal text input box on the main UI instead of a popup window? Having a modal popup is kind of jarring, and makes the text entry more difficult

#### Reproduction Steps

1. python src/view.py cat_fountain/product

#### Resolution Notes

Replaced modal prompt() dialogs with non-modal toolbar text input and inline editable notes in sidebar pins list.
