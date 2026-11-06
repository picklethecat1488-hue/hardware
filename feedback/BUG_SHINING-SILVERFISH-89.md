# 🟢 `[BUG-SHINING-SILVERFISH-89]` Attachments show up in the diff view

- **UUID**: `4f9fe270-0b4f-4ff7-acce-8b9e66188e1c`
- **ID**: `BUG-SHINING-SILVERFISH-89`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `dashboard`
- **Created**: `2026-11-06 06:44:04 UTC`
- **Resolved**: `2026-11-06 17:17:35 UTC`
- **Accepted**: `2026-11-06 17:17:38 UTC`

#### Description

Attachment LFS changes show up in the diff view. Can we ensure that attachments are stored in the bug branches (refs/heads/bugs and ref/heads/worms) and migrate existing attachments, if needed?

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1793947517131_gdv1n.png](attachments/BUG-SHINING-SILVERFISH-89/screenshot_paste_1793947517131_gdv1n.png) | Pasted screenshot screenshot_paste_1793947517131_gdv1n.png |

#### Attached Commits

- `67772fbf`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:29d45ad5 --> Verify attachments are excluded from diff view and stored on refs/heads/bugs | `git status --porcelain`

#### Resolution Notes

Decoupled attachments to dedicated refs/heads/bugs detached branch, added attachments to .gitignore, hid attachments from git_engine diff view, and added checkout_attachments restoration.
