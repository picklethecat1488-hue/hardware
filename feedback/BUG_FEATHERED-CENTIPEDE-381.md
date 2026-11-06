# 🟢 `[BUG-FEATHERED-CENTIPEDE-381]` It takes 10s to save bugs now

- **UUID**: `decd4cc3-3a98-4552-917e-d4b0cb668001`
- **ID**: `BUG-FEATHERED-CENTIPEDE-381`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `dashboard`
- **Created**: `2026-10-23 23:04:38 UTC`
- **Resolved**: `2026-11-05 15:32:56 UTC`

#### Description

IDK why this is, but saving and updating bugs takes extremely long now...

#### Attached Commits

- `95811f16`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:e96f35c0 --> Verify sub-second detached branch save responsiveness in dashboard | `python tools/dashboard.py inspect-bug --id BUG-FEATHERED-CENTIPEDE-381`

#### Resolution Notes

Optimized bug persistence and detached branch commits: 1) Batch git index updates via 'git update-index --index-info' instead of per-bug subprocess calls; 2) In-memory SHA-1 computation and direct blob persistence; 3) Incremental dirty bug saving in SQLite and markdown exporter; reducing save times from >12s to sub-second.
