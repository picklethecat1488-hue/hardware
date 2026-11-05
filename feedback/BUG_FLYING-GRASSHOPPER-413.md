# 🟢 `[BUG-FLYING-GRASSHOPPER-413]` CI is failing

- **UUID**: `ab12a306-e6a7-4bc7-8185-4638209b1a39`
- **ID**: `BUG-FLYING-GRASSHOPPER-413`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Created**: `2026-10-17 23:30:57 UTC`
- **Resolved**: `2026-10-17 23:39:26 UTC`

#### Description

See attachments below. Both nightly license compliance and CI jobs are failing

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `document` | [clipboard_text_1792279899940.txt](attachments/BUG-FLYING-GRASSHOPPER-413/clipboard_text_1792279899940.txt) | Pasted text document |
| `document` | [clipboard_text_1792279938306.txt](attachments/BUG-FLYING-GRASSHOPPER-413/clipboard_text_1792279938306.txt) | Pasted text document |

#### Resolution Notes

Fixed license compliance failure by constraining pluggy<1.7.0 for scancode-toolkit in workflow and environment.yml. Fixed CI gate failure by formatting test_dashboard.py with ruff format. Added dedicated regression tests.
