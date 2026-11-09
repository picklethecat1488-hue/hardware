# 🟢 `[BUG-GOLDEN-FIREFLY-566]` The engineering question of your 3D print order#C-E77W908185A_pump_cover.stl

- **UUID**: `ab45f3a8-a869-4d88-99f9-915cf3f74083`
- **ID**: `BUG-GOLDEN-FIREFLY-566`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-09 18:18:29 UTC`
- **Resolved**: `2026-11-09 20:10:17 UTC`

#### Description

About your order, there is an engineering question for C-E77W908185A_pump_cover.stl

As shown in the attached picture, your file has multiple separate parts that are not fully merged.
If they need to be printed as a whole, please update your file and send it to us for an update via email.

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794248350763_t74l0.png](attachments/BUG-GOLDEN-FIREFLY-566/screenshot_paste_1794248350763_t74l0.png) | Pasted screenshot screenshot_paste_1794248350763_t74l0.png |

#### Attached Commits

- `8ec87ba3`

#### Review Tasks & Functional Checklist

- [x] <!-- task:75d8149f --> Inspect pump_cover STL mesh to verify single contiguous solid and no disconnected floating annular rings | `python tools/build.py cat_fountain:pump_cover:stl`

#### Resolution Notes

Bridge downward lip and annular snap-fit ridge with cylindrical connector, uniting pump cover into a single merged solid
