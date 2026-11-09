# 🟢 `[BUG-CREEPING-WATERSTRIDER-835]` WOrking tree CR feedback does not get committed

- **UUID**: `99969033-d423-4f03-aade-a5fd45b12fda`
- **ID**: `BUG-CREEPING-WATERSTRIDER-835`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `dashboard`
- **Created**: `2026-11-08 12:12:27 UTC`
- **Resolved**: `2026-11-09 18:55:53 UTC`

#### Description

Example:
1) I make working tree CR feedback. It gets saved to CR_working.md
2) changes get staged into commit foo

#### Behavior Comparison

- **Expected**: 3) Open review feedback in CR_working.md should get moved into CR_foo.md
- **Actual**: 3) Open review feedback stays in CR_working.md

#### Review Tasks & Functional Checklist

- [x] <!-- task:b933808b --> Verify working tree code review comments migrate to CR_<commit>.md upon git commit | `python tools/forge.py list-reviews --open`

#### Resolution Notes

Re-key working comments to new commit hash in SQLite, update ReviewServer session, export to CR_<new_sha>.md, and sync feedback worktree upon commit
