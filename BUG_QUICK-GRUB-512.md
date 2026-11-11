# 🟢 `[BUG-QUICK-GRUB-512]` Horizontal scrollbar under top HUD not themed to Quake CRT palette

- **UUID**: `02986800-0ef0-4a22-a6ed-b55f7082736c`
- **ID**: `BUG-QUICK-GRUB-512`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `Scope`
- **Created**: `2026-11-11 18:27:19 UTC`
- **Resolved**: `2026-11-11 19:45:21 UTC`

#### Description

The horizontal scrollbar under the header is not themed (screenshot attached)

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1794421688344_hbpe0.png](attachments/BUG-QUICK-GRUB-512/screenshot_paste_1794421688344_hbpe0.png) | Pasted screenshot screenshot_paste_1794421688344_hbpe0.png |

#### Attached Commits

- `1d9bc62d917d5cb498c939e3d561108177318d3b`
- `5919a5dd`
- `d3e08b55`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:b054ca1c --> Verify horizontal scrollbar under top HUD renders with Quake dark track and copper thumb | `python tools/scope.py`

#### Resolution Notes

Added dark color-scheme meta and WebKit scrollbar theming with Quake palette
