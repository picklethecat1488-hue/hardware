# 🟢 `[BUG-EMERALD-MOTH-182]` Target and Sync buttons unresponsive due to deferred event listener attachment and unhandled empty project state

- **UUID**: `bafe9f8c-d857-4073-b343-7cd1a5ed5f72`
- **ID**: `BUG-EMERALD-MOTH-182`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `UI`
- **Component**: `cat_fountain`
- **Created**: `2026-11-12 17:40:50 UTC`
- **Resolved**: `2026-11-12 17:41:06 UTC`

#### Description

Target (#btn-open-chooser) and Sync (#btn-sync) buttons in the scope CAD viewer HUD become unresponsive or fail to open/update because DOM event listener registration is deferred after asynchronous geometry loading. Additionally, openProjectChooserModal leaves the modal in a disabled state if state.projects is empty without triggering project loading.

#### Review Tasks & Functional Checklist

- [ ] <!-- task:0007738d --> Verify Target (#btn-open-chooser) and Sync (#btn-sync) buttons are immediately active and project chooser populates targets | `python tools/scope.py`

#### Resolution Notes

Separated DOM event listener attachment into synchronous initEventListeners called on DOMContentLoaded so Target and Sync buttons are immediately responsive without waiting for async geometry compilation. Updated openProjectChooserModal to asynchronously fetch projects if empty, and added unconfigured target/project fallback handling to the Sync button.
