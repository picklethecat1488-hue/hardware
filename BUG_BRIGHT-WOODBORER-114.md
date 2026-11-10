# 🟢 `[BUG-BRIGHT-WOODBORER-114]` Re : Re: The engineering question of your 3D print order#C-E77W908185A C-E72W908185A C-E71W908185A

- **UUID**: `2ae46cbe-de50-44bc-a93e-71e4496dc58a`
- **ID**: `BUG-BRIGHT-WOODBORER-114`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-10 14:11:40 UTC`
- **Resolved**: `2026-11-10 20:40:44 UTC`
- **Accepted**: `2026-11-10 20:40:42 UTC`

#### Description

Pls fix as much of this as possible-we can accept the risk of breakage for the rest

For orders C-E77W908185A and C-E72W908185A, there is still a risk of breakage due to the red-indicated thin thickness. Do you accept this risk or want to increase the thickness to 1 mm?
For order C-E71W908185A, the height of the protruding feature is still not enough. Would you like to take this risk or want to redesign your file?

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794319962134_wbolt.png](attachments/BUG-BRIGHT-WOODBORER-114/screenshot_paste_1794319962134_wbolt.png) | Pasted screenshot screenshot_paste_1794319962134_wbolt.png |
| `screenshot` | [screenshot_paste_1794319975453_u256e.png](attachments/BUG-BRIGHT-WOODBORER-114/screenshot_paste_1794319975453_u256e.png) | Pasted screenshot screenshot_paste_1794319975453_u256e.png |
| `screenshot` | [screenshot_paste_1794319983993_0c6us.png](attachments/BUG-BRIGHT-WOODBORER-114/screenshot_paste_1794319983993_0c6us.png) | Pasted screenshot screenshot_paste_1794319983993_0c6us.png |
| `screenshot` | [screenshot_paste_1794319993473_5hp3j.png](attachments/BUG-BRIGHT-WOODBORER-114/screenshot_paste_1794319993473_5hp3j.png) | Pasted screenshot screenshot_paste_1794319993473_5hp3j.png |
| `screenshot` | [screenshot_paste_1794320001277_60qmk.png](attachments/BUG-BRIGHT-WOODBORER-114/screenshot_paste_1794320001277_60qmk.png) | Pasted screenshot screenshot_paste_1794320001277_60qmk.png |

#### Attached Commits

- `8c8953467007256d57295120b57580346df9eb92`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:152ac737 --> Verify customer reply document for 3D print engineering query | `cat attachments/BUG-BRIGHT-WOODBORER-114/customer_reply.md`
- [ ] <!-- task:0f49750e --> Compile pump cover, bowl, and bottom cover parts into 3D models | `python tools/build.py cat_fountain/pump_cover cat_fountain/bowl cat_fountain/bottom_cover`
- [ ] <!-- task:b29ffac1 --> Visualize bowl and pump cover snap assembly in 3D viewer | `python tools/view.py cat_fountain/bowl cat_fountain/pump_cover --no-gui`

#### Resolution Notes

Resolved 3D print engineering query for orders C-E77W908185A, C-E72W908185A, C-E71W908185A: increased pump cover snap ridge thickness to 1.0mm, thickened pump casing wall to 2.6mm ensuring >= 1.0mm wall thickness at snap recess and groove, redesigned bottom cover snap ridge with 0.75mm protrusion and lead-in chamfers, and accepted risk for minor text engraving breakage
