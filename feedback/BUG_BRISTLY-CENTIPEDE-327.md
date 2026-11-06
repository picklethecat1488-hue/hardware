# 🔴 `[BUG-BRISTLY-CENTIPEDE-327]` Add modal progress UIs for repo and bug actions

- **UUID**: `4bfee9c3-96a6-4d79-b0f8-5e450e99fece`
- **ID**: `BUG-BRISTLY-CENTIPEDE-327`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `dashboard`
- **Created**: `2026-11-06 06:45:37 UTC`

#### Description

Repo actions like sync, and bug actions like saving, approving or rejecting, and creating bugs now take sufficiently long that I think we need a modal UI to show action status, similar to the UI used for creating PRs. Can we do some profiling of repo and bug actions, optimize if needed, and add modal progress UIs for actions that take sufficiently long (>1s)? The UIs should be hidden automatically after the action completes, and only show if the action is taking a long time. We can also make this change to the sync action to make all actions behave uniformly.
