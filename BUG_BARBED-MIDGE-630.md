# 🟢 `[BUG-BARBED-MIDGE-630]` There are 3 outer borders in my dashboard window?

- **UUID**: `e4da4b73-81ef-4863-baf3-d4af7519adfc`
- **ID**: `BUG-BARBED-MIDGE-630`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `dashboard`
- **Created**: `2026-10-23 23:00:18 UTC`
- **Resolved**: `2026-11-05 15:45:39 UTC`
- **Accepted**: `2026-11-06 00:18:47 UTC`

#### Attached Commits

- `bf875947`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:1d39a9ea --> Verify clean window rendering with no redundant iframe borders or duplicate splitters | `python tools/dashboard.py inspect-bug --id BUG-BARBED-MIDGE-630`

#### Resolution Notes

Eliminate duplicate outer window borders and resize grippers by applying .in-iframe rules to common.css and workstation templates, and add frame-busting to diff_view.
