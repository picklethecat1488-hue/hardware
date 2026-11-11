# 🟢 `[BUG-PLUMED-TREEHOPPER-556]` [cat_fountain/product] Defect in CAD view

- **UUID**: `2f789c96-5392-40df-a65e-2820923aa80a`
- **ID**: `BUG-PLUMED-TREEHOPPER-556`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 00:16:24 UTC`
- **Resolved**: `2026-11-11 00:27:59 UTC`

#### Description

We should hide PCB-related functionality when in CAD view, and vice versa

#### Reproduction Steps

1. python src/view.py cat_fountain/product

#### Review Tasks & Functional Checklist

- [ ] <!-- task:6e17cf04 --> Verify PCB Layers tab is hidden and CAD Tree tab is visible in CAD mode | `python tools/scope.py cat_fountain/product --no-app --no-detach`
- [ ] <!-- task:018bc0c5 --> Verify CAD Tree tab is hidden and PCB Layers tab is visible in PCB mode | `python tools/scope.py carrier_board/carrier_board:pcb --no-app --no-detach`

#### Resolution Notes

Mode-aware sidebar tabs toggle PCB Layers vs CAD Tree tabs based on active view mode.
