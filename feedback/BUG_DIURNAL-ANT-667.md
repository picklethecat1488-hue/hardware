# 🟢 `[BUG-DIURNAL-ANT-667]` Opening commits in bug report workstation-broken

- **UUID**: `11c9c5fd-5d11-49fd-98dd-55d1692ee65d`
- **ID**: `BUG-DIURNAL-ANT-667`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `dashboard`
- **Created**: `2026-11-06 17:15:23 UTC`
- **Resolved**: `2026-11-06 20:42:14 UTC`

#### Description

Opening a commit in the bug report station doesn’t go to the code review window directly, instead it opens up a website to the toplevel VCS UI with only the working tree selected. Additionally, there is no way to go back to the bug report station when finished reviewing (there is no back button in the toolbar).

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1793985363740_q9986.png](attachments/BUG-DIURNAL-ANT-667/screenshot_paste_1793985363740_q9986.png) | Pasted screenshot screenshot_paste_1793985363740_q9986.png |

#### Attached Commits

- `44ebc5c6`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:e358784d --> Launch dashboard, open BUG-DIURNAL-ANT-667, click attached commit chip to verify it jumps directly to Code Review with '◀ Back to BUG-DIURNAL-ANT-667' button in toolbar | `python tools/dashboard.py --bugs`

#### Resolution Notes

Attached commits in Bug Report now navigate directly to Code Review for that commit, and Code Review provides toolbar and header buttons to return to the Bug Report workstation
