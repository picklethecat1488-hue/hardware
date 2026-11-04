# 🟢 `[BUG-LOAMY-BRISTLE-455]` Elide physical address and personal email in privacy sanitizer

- **UUID**: `09c3136e-35c6-442e-9708-46ac711fa0ed`
- **ID**: `BUG-LOAMY-BRISTLE-455`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `INFRASTRUCTURE`
- **Component**: `sanitizer`
- **Created**: `2026-10-15 00:37:10 UTC`
- **Resolved**: `2026-10-15 00:37:11 UTC`

#### Description

Extend the zero-dependency personal privacy and identity sanitizer (`src/provider/sanitizer.py`) to systematically redact physical addresses (street names, numbers, suite/apt/unit designators, P.O. Boxes, and postal/ZIP codes) and personal email addresses (user handles, consumer email domains like `@gmail.com`, `@me.com`, etc.) across developer feedback, bug reports, and logs. Additionally, update VCS engine commit author and email mapping to redact user author identities to `User` and `user@workspace`.

#### Resolution Notes

1. Added physical street address, unit/suite, and P.O. Box regex redaction to `<address>` and `<zip>` in `elide_personal_info()`, using pure regex matching without requiring an engineering whitelist or supplier address preservation.
2. Dynamically discovered user emails, handles, and system usernames to map all personal identifiers and consumer email domains to `<email>`.
3. Updated `elide_commit_author()` and `elide_commit_email()` in `src/provider/sanitizer.py` to map user author identities and commit emails to `User` and `user@workspace` via dynamic discovery.
4. Updated VCS workstation frontend `sanitizeAuthor()` in `diff_view.html.j2` and `code_review.html.j2` to read the author blacklist dynamically from the backend session.
5. Added dedicated regression unit tests in `src/tests/test_privacy_and_relative_paths.py`.
