# 🔴 `[BUG-SHINING-SILVERFISH-89]` Attachments show up in the diff view

- **UUID**: `4f9fe270-0b4f-4ff7-acce-8b9e66188e1c`
- **ID**: `BUG-SHINING-SILVERFISH-89`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `dashboard`
- **Created**: `2026-11-06 06:44:04 UTC`

#### Description

Attachment LFS changes show up in the diff view. Can we ensure that attachments are stored in the bug branches (refs/heads/bugs and ref/heads/worms) and migrate existing attachments, if needed?

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `screenshot` | [screenshot_paste_1793947517131_gdv1n.png](attachments/BUG-SHINING-SILVERFISH-89/screenshot_paste_1793947517131_gdv1n.png) | Pasted screenshot screenshot_paste_1793947517131_gdv1n.png |

#### Review Tasks & Functional Checklist

- [ ] <!-- task:29d45ad5 --> Verify attachments are excluded from diff view and stored on refs/heads/bugs | `git status --porcelain`
