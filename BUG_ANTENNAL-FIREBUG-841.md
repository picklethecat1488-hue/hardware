# 🔴 `[BUG-ANTENNAL-FIREBUG-841]` [cat_fountain/product] Defect in CAD view

- **UUID**: `37a3ee75-19a5-428e-a618-b1c71af0f4bd`
- **ID**: `BUG-ANTENNAL-FIREBUG-841`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 13:54:05 UTC`

#### Description

The viewport doesn’t cover the bottom 2/3 of my browser window

#### Reproduction Steps

1. python tools/scope.py cat_fountain/product:cad

#### Review Tasks & Functional Checklist

- [ ] <!-- task:114cb954 --> Verify CAD viewport dynamically expands to fill 100% of browser window upon resize | `python tools/scope.py cat_fountain/product:cad`
