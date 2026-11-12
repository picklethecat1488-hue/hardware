# 🔴 `[BUG-EMERALD-MOTH-182]` Target and Sync buttons unresponsive due to deferred event listener attachment and unhandled empty project state

- **UUID**: `bafe9f8c-d857-4073-b343-7cd1a5ed5f72`
- **ID**: `BUG-EMERALD-MOTH-182`
- **Status**: `OPEN`
- **Severity**: `HIGH`
- **Category**: `UI`
- **Component**: `cat_fountain`

#### Description

Target (#btn-open-chooser) and Sync (#btn-sync) buttons in the scope CAD viewer HUD become unresponsive or fail to open/update because DOM event listener registration is deferred after asynchronous geometry loading. Additionally, openProjectChooserModal leaves the modal in a disabled state if state.projects is empty without triggering project loading.
