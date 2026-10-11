# 🟢 `[BUG-SUBTERRANEAN-VINEGARWORM-291]` There is some issue with pasting screenshots into bug reports

- **UUID**: `5b7f9c34-23de-4b6d-abbe-78cc61b40c26`
- **ID**: `BUG-SUBTERRANEAN-VINEGARWORM-291`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `Dashboard`
- **Created**: `2026-10-11 00:21:20 UTC`
- **Resolved**: `2026-10-11 01:10:48 UTC`

#### Description

Can you please fix this across firmware, hardware, and SSD repos, running pre-commit testing for each-
When I copy a screenshot and attempt to paste it into a bug, the screenshot is not correctly pasted.

#### Reproduction Steps

1. 1. $ python src/dashboard.py
2. 2. Open Bug Tracker
3. 3. Paste screenshot
4. 4. Copy another screenshot
5. 5. Paste another screenshot

#### Behavior Comparison

- **Expected**: The screenshot in 5 should be different from the screenshot in 3
- **Actual**: The screenshot image in 3 and 5 are identical

#### Resolution Notes

Added collision avoidance logic on upload in server and unique timestamped filenames for pasted screenshot attachments across hardware, firmware, and SSD repositories.
