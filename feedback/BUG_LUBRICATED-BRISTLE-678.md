# 🟢 `[BUG-LUBRICATED-BRISTLE-678]` Pytest taking too long

- **UUID**: `b1c765fb-12fa-4332-a9fb-97daa3379a45`
- **ID**: `BUG-LUBRICATED-BRISTLE-678`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `Purest`
- **Created**: `2026-10-09 23:28:09 UTC`
- **Resolved**: `2026-10-09 23:36:01 UTC`

#### Description

There are some pytests that take multiple seconds to complete, and there doesn't appear to be any test parallelization, going off my activity monitor.

#### Resolution Notes

Fixed pytest worker hook in conftest.py to check whether slow tests are actually selected using Expression parsing rather than naive substring matching against 'not slow', restoring test parallelization for fast test runs.
