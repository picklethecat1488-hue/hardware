# 🔴 `[BUG-HUMIC-CENTIPEDE-711]` Clean up repo

- **UUID**: `33d8ef9c-5293-412b-9943-faa2d45e1b22`
- **ID**: `BUG-HUMIC-CENTIPEDE-711`
- **Status**: `OPEN`
- **Severity**: `LOW`
- **Category**: `INFRASTRUCTURE`
- **Created**: `2026-10-11 03:51:01 UTC`

#### Description

I see files tracked in the repo that should be untracked, or removed. Can we please clean up the repo a bit

#### Reproduction Steps

1. $ rm cat_fountain_wiring_diagram.svg
2. $ rm src/urdf_template.yaml

#### Execution / Console Logs

```text
$ sl status
! cat_fountain_wiring_diagram.svg
! src/urdf_template.yaml
```
