# 🟢 `[BUG-EMERALD-MOTH-182]` Target and Sync buttons unresponsive due to deferred event listener attachment and unhandled empty project state

- **UUID**: `bafe9f8c-d857-4073-b343-7cd1a5ed5f72`
- **ID**: `BUG-EMERALD-MOTH-182`
- **Status**: `CLOSED`
- **Severity**: `HIGH`
- **Category**: `UI`
- **Component**: `cat_fountain`
- **Created**: `2026-11-12 17:40:50 UTC`
- **Resolved**: `2026-11-12 18:12:34 UTC`
- **Accepted**: `2026-11-12 20:51:13 UTC`
- **Rejected**: `2026-11-12 17:57:13 UTC`

#### Description

Target (#btn-open-chooser) and Sync (#btn-sync) buttons in the scope CAD viewer HUD become unresponsive or fail to open/update because DOM event listener registration is deferred after asynchronous geometry loading. Additionally, openProjectChooserModal leaves the modal in a disabled state if state.projects is empty without triggering project loading.

#### Attached Commits

- `27161e8e`
- `e1e29d83`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:0007738d --> Verify Target (#btn-open-chooser) and Sync (#btn-sync) buttons are immediately active and project chooser populates targets | `python tools/scope.py`

#### Resolution Notes

Removed dangling extra closing brace at line 2261 breaking script parse time, ensured openProjectChooserModal populates and enables controls even after cold start projects fetch, added readyState interactive/complete guard for initWorkstation, and added automated Node.js vm.Script syntax assertion in test_scope_server.py

#### Rejection Feedback

Separated DOM event listener attachment into synchronous initEventListeners called on DOMContentLoaded so Target and Sync buttons are immediately responsive without waiting for async geometry compilation. Updated openProjectChooserModal to asynchronously fetch projects if empty, and added unconfigured target/project fallback handling to the Sync button.
-Tried a couple times, this still isn’t working for me :-(
