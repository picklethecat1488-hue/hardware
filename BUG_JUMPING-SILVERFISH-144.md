# 🟢 `[BUG-JUMPING-SILVERFISH-144]` These vias appear unnecessary

- **UUID**: `4bd7e7a9-4df6-45eb-b509-a609b8a6008c`
- **ID**: `BUG-JUMPING-SILVERFISH-144`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-09 23:07:13 UTC`
- **Resolved**: `2026-11-10 00:34:19 UTC`

#### Description

The vias I circled on the bottom right of the carrier board appear unnecessary; the only connections I see on any of them is an antenna on the back copper layer.

#### Execution / Console Logs

```text
python tools/view.py footprints/040
```

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794265655729_eo4n6.png](attachments/BUG-JUMPING-SILVERFISH-144/screenshot_paste_1794265655729_eo4n6.png) | Pasted screenshot screenshot_paste_1794265655729_eo4n6.png |

#### Attached Commits

- `3120b5c6`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:5cc14b27 --> Verify unnecessary vias and stubs removed from carrier board | `python tools/view.py carrier_board:pcb`

#### Resolution Notes

Removed 8 unnecessary through-hole vias, dangling stubs on B.Cu, and passives C15..D8 on bottom right of carrier board to eliminate parasitic antenna stubs and preserve ground plane.
