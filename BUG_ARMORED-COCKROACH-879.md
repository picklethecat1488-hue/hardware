# 🟢 `[BUG-ARMORED-COCKROACH-879]` [cat_fountain/product] Defect in CAD view

- **UUID**: `0eb5458d-548f-4192-89fa-02e92ff49cc0`
- **ID**: `BUG-ARMORED-COCKROACH-879`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 00:14:18 UTC`
- **Resolved**: `2026-11-11 00:25:35 UTC`

#### Description

Observed visual defect in CAD mode.
Target: cat_fountain/product

I don’t actually see the product view opening up

#### Reproduction Steps

1. python src/view.py cat_fountain/product

#### Review Tasks & Functional Checklist

- [ ] <!-- task:33f23969 --> Verify 3D instanced CAD geometry renders in Scope viewport | `python tools/scope.py cat_fountain/product --no-app --no-detach`

#### Resolution Notes

Imported decodeInstancedFormat and isInstancedFormat in scope.html.j2 to resolve instanced shape buffers and set config.reset_camera to RESET in pipeline.py.
