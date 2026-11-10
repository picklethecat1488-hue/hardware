# 🟢 `[BUG-TRANSLUCENT-CRICKET-767]` Flex tail has carrier board pads and components

- **UUID**: `9b47e3f1-cd09-4506-ad2a-7bbe4fed8319`
- **ID**: `BUG-TRANSLUCENT-CRICKET-767`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-10 00:34:39 UTC`
- **Resolved**: `2026-11-10 14:11:33 UTC`
- **Accepted**: `2026-11-10 14:11:38 UTC`

#### Reproduction Steps

1. $ python tools/view.py carrier_board/flex_tail:pcb

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794270902078_nny6n.png](attachments/BUG-TRANSLUCENT-CRICKET-767/screenshot_paste_1794270902078_nny6n.png) | Pasted screenshot screenshot_paste_1794270902078_nny6n.png |

#### Attached Commits

- `ffa55f5717b6f5bd97a60b7b94a5935e75797559`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:ad89be04 --> Verify flex tail contains only J4 and capacitive electrodes in 3D CAD viewer | `python tools/view.py carrier_board/flex_tail:pcb --no-gui`

#### Resolution Notes

Scoped footprints, capacitive sensors, and test points in PCB3DAssembler to target shape_ref and board_type; added silkscreen rendering with canonical layer colors
