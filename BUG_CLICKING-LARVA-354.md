# 🟢 `[BUG-CLICKING-LARVA-354]` The engineering questions of your 3D print order#C-E71W908185A_bottom_cover.stl

- **UUID**: `d4d28107-f07e-4d7a-ac51-9a7aee11c17c`
- **ID**: `BUG-CLICKING-LARVA-354`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-09 18:20:44 UTC`
- **Resolved**: `2026-11-09 22:05:37 UTC`

#### Description

The height of the protruding feature is too small to print.

—This looks like a defect introduced by conversion of BREP CAD objects into STL meshes. Can you take a look/fix this?

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794248516656_cluu0.png](attachments/BUG-CLICKING-LARVA-354/screenshot_paste_1794248516656_cluu0.png) | Pasted screenshot screenshot_paste_1794248516656_cluu0.png |
| `screenshot` | [screenshot_paste_1794248529568_wddvz.png](attachments/BUG-CLICKING-LARVA-354/screenshot_paste_1794248529568_wddvz.png) | Pasted screenshot screenshot_paste_1794248529568_wddvz.png |

#### Review Tasks & Functional Checklist

- [x] <!-- task:3b7fdaad --> Compile bottom cover STL to verify smooth annular snap ridge and absence of unprintable horizontal shelf steps | `python tools/build.py cat_fountain/bottom_cover`

#### Resolution Notes

Replace stepped annular snap ring with continuous smooth Torus ridge on bottom cover
