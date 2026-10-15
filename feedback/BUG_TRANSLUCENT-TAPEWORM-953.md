# 🟢 `[BUG-TRANSLUCENT-TAPEWORM-953]` Dashboard stuck at 20% on launch

- **UUID**: `3e17a613-50d8-4c90-9e62-24e63b8f13fe`
- **ID**: `BUG-TRANSLUCENT-TAPEWORM-953`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `INFRASTRUCTURE`
- **Component**: `dashboard`
- **Created**: `2026-10-15 00:32:11 UTC`
- **Resolved**: `2026-10-15 00:32:17 UTC`

#### Description

Upon launching or restarting the dashboard workstation, the UI was stuck displaying the feedback database synchronization modal at 20% progress. Inspection revealed a JavaScript `SyntaxError: Unexpected token ')'` in `diff_view.html.j2:1705` within the `sanitizeAuthor()` function introduced during privacy sanitization hardening. Because the script failed to parse, `initDiffView()` and `performInitialSync()` never ran, leaving the modal stuck at its initial 20% HTML state.

#### Resolution Notes

1. Pruned dangling closing parenthesis in `sanitizeAuthor()` condition in `src/provider/templates/diff_view.html.j2`.
2. Hardened workstation initialization lifecycle so `initDiffView()` fires immediately if `document.readyState !== 'loading'`, eliminating dependency on potentially pre-fired `DOMContentLoaded` events.
3. Added comprehensive regression test `test_regression_bug_translucent_tapeworm_953_dashboard_js_syntax_and_sync_screen` in `src/tests/test_dashboard.py` verifying balanced syntax and executing `node -c` across extracted `<script>` blocks in all dashboard templates (`diff_view.html.j2`, `code_review.html.j2`, `bug_report.html.j2`).
