# 🔴 `[BUG-ARMORED-LEAFHOPPER-983]` Daemon preloaded modules and test_daemon_spawn_tools reference obsolete view tool instead of scope

- **UUID**: `2839254b-278b-4212-8359-c0c6e6ab0c84`
- **ID**: `BUG-ARMORED-LEAFHOPPER-983`
- **Status**: `OPEN`
- **Severity**: `HIGH`
- **Category**: `INFRASTRUCTURE`
- **Component**: `daemon`
- **Created**: `2026-11-12 17:48:20 UTC`

#### Description

When tools/view.py was removed and replaced by tools/scope.py, tools/daemon.py still listed 'view' in preloaded modules and tests/test_daemon.py::test_daemon_spawn_tools attempted client.run('view', ['--help']), causing ModuleNotFoundError: No module named 'view'.

#### Attached Commits

- `f64eb5cd`
