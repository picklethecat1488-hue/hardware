# 🟢 `[BUG-TRANSLUCENT-LACEWING-144]` PCB view net highlighting is non-functional and requires KiCad high-contrast theme (carrier_board)

- **UUID**: `cf9a924c-9c73-4e4c-b249-6be0475c8f46`
- **ID**: `BUG-TRANSLUCENT-LACEWING-144`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-11 13:59:20 UTC`
- **Resolved**: `2026-11-11 22:36:50 UTC`
- **Rejected**: `2026-11-11 22:00:22 UTC`

#### Description

Net highlighting does not work. We should also use a high contrast color scheme that makes PCB components more obvious when in PCB view, similar to what kicad uses

#### Reproduction Steps

1. python tools/scope.py carrier_board/carrier_board:pcb

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794434113716_f0sw8.png](attachments/BUG-TRANSLUCENT-LACEWING-144/screenshot_paste_1794434113716_f0sw8.png) | Pasted screenshot screenshot_paste_1794434113716_f0sw8.png |
| `screenshot` | [screenshot_paste_1794434209020_bde4d.png](attachments/BUG-TRANSLUCENT-LACEWING-144/screenshot_paste_1794434209020_bde4d.png) | Pasted screenshot screenshot_paste_1794434209020_bde4d.png |
| `screenshot` | [screenshot_paste_1794434388241_j5k2b.png](attachments/BUG-TRANSLUCENT-LACEWING-144/screenshot_paste_1794434388241_j5k2b.png) | Pasted screenshot screenshot_paste_1794434388241_j5k2b.png |

#### Attached Commits

- `84e9c3d4`
- `caafb7a1`
- `5919a5dd`
- `d3e08b55`
- `7b5bbd30`
- `a71069de`
- `e40dabc6`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:cbd6bdbb --> Verify PCB copper layers use KiCad high-contrast palette and active nets illuminate on click | `python tools/scope.py carrier_board/carrier_board:pcb`
- [ ] <!-- task:2ceb8e09 --> Verify PCB view displays KiCad high-contrast theme, interactive layer checkboxes/solo, 3D net highlighting, and PCB camera quickbar | `python tools/scope.py carrier_board/carrier_board:pcb`
- [ ] <!-- task:90ba4b66 --> Inspect carrier_board in Scope PCB mode, verify high-contrast theme is always active, hover pointer tooltip identifies components/traces/vias, clicking inspects elements without substrate selection, and traces/pads are smooth without black edge outlines | `python tools/scope.py carrier_board/carrier_board:pcb`

#### Resolution Notes

Removed manual HC buttons and made KiCad high contrast theme always on in PCB mode, suppressed substrate highlighting and bounding box selection, implemented minimum-distance entity picking and live hover pointer tooltip, replaced carrier board silkscreen arrow with sleek diamond emblem, and added rounded cylinder caps to trace vertices while disabling wireframe edge outlines on copper layers.

#### Rejection Feedback

Implemented KiCad high-contrast PCB color scheme, interactive layer checkboxes and solo toggling, 3D glowing net highlighting with background dimming and canvas repaint, PCB camera quickbar buttons (Top, Bot, Flip, HC), and rich PCB entity inspection for traces, vias, pads, and components

Rejected:
-The high contrast mode doesn’t really work the way I expect (attached a screenshot showing the kicad viewer’s contrasting colors)
-Can we disable highlighting of the substrate? We should only highlight things like components, traces, pads, vias, and silkscreening
-I cannot accutrately highlight individual traces and vias-the mouse pointer doesn’t accurately indicate which component is being highlighted
-There is a weird up arrow thing in the middle of the board
-We only need HC mode in PCB view and it should be always on-we don’t need a separate HC button in CAD or simulate view
-The inspect panel doesn’t show any info about the component, trace, pad, or via
-The pads and traces aren’t currently being rendered correctly when zoomed in (see atached screenshot from kicad viewer)
