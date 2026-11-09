# 🔴 `[BUG-SWIFT-MITE-462]` The engineering questions of your 3D print order#C-E72W908185A_bowl.stl

- **UUID**: `a736e893-03c5-43c4-9dce-db6b5b6c5d1d`
- **ID**: `BUG-SWIFT-MITE-462`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-09 18:19:42 UTC`

#### Description

1. See the attached pic, the thickness for red-indicated places is too thin, and they may be broken during printing. There are two suggestions for your reference.
A. Increase the thickness to 1 mm. And then send the new file to us for an update.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794248422642_wc8c3.png](attachments/BUG-SWIFT-MITE-462/screenshot_paste_1794248422642_wc8c3.png) | Pasted screenshot screenshot_paste_1794248422642_wc8c3.png |

#### Review Tasks & Functional Checklist

- [ ] <!-- task:a23e29b4 --> Inspect bowl STL to verify >= 1.0mm thickness at PCB clip detent lip and charger port wall | `python tools/build.py cat_fountain:bowl:stl`
