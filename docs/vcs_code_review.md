# VCS Workstation, Code Review & Quake HUD Templates

Guidelines for Quake VCS dashboard, Jinja2 templating, code review persistence, and Git LFS bug tracking.

## 1. Code Generation & Jinja2 Templates
* **Jinja2 Templating Engine**: Always use Jinja2 (`jinja2`) to generate templated Python scripts, Blender headless scripts, URDF models, or simulation configurations rather than embedding large multi-line f-strings directly inside Python source files.
* **Dedicated Templates Directory**: All templated script files (`.py.j2`, `.yaml.j2`, `.urdf.j2`, `.sh.j2`) MUST be stored in a dedicated `templates/` folder nested within the respective package or module (e.g., `provider/templates/`).
* **Clean Rendering & Context Separation**: Render external Jinja2 templates via `jinja2.Environment(loader=jinja2.FileSystemLoader(...), trim_blocks=True, lstrip_blocks=True)` or package loaders, passing configuration parameters as explicit dictionaries or strongly typed models.
* **No Silent Exception Swallowing in Templates**: Templated scripts (`.py.j2`) MUST follow standard code quality standards. Never generate `try/except/pass` fallback ladders inside Jinja2 templates; inspect environment capabilities deterministically via template variables.

## 2. Review Session Feedback & SQLite Persistence
* **Review Persistence**: The interactive code review web dashboard (`dashboard.py /review`) and server (`DashboardServer` / `ReviewServer`) MUST persist session feedback, comments, and file review statuses across server restarts.
* **Atomic Storage**: Feedback is persisted atomically to SQLite (`build/code_review.sqlite`, `SQLiteReviewStore`) with automatic synchronization to JSON state (`build/cr_feedback.json`), Markdown reports (`feedback/CR.md`), and granular commit review files (`feedback/CR_<commit>.md`).
* **CLI & Subcommands**: Query review status in the console (`python tools/dashboard.py list-reviews` or `--reviews`), filter unresolved comments (`--open`), or resolve items (`python tools/dashboard.py resolve-comment <id>`).

## 3. Structured Bug Tracking & Git LFS Attachments
* **Defect Lifecycle**: Defects, routing anomalies, and visual flaws must be tracked systematically using the Dashboard CLI (`tools/dashboard.py`) and persisted in SQLite (`build/bugs.sqlite`, `SQLiteBugStore`), synchronized automatically to individual issue files (`feedback/BUG_<id>.md`).
* **Verification Checklist Mandate on Resolution**: When transitioning any defect to `RESOLVED`, the author MUST update the defect's review tasks and functional checklist (`review_tasks`) with concise verification steps and executable demonstration commands that verify the change from a user-experience perspective (e.g. `python tools/view.py ...`, host CLI commands, or UI inspection using `python tools/dashboard.py add-task --id <ID> --title "<Step>" --command "<cmd>"`). Do NOT use `pytest` commands as review verification tasks, as automated test suites already run during pre-commit checks and CI; verification commands should demonstrate the actual user experience change or visual fix to allow peer reviewers to independently verify the fix prior to acceptance (`accept-bug`).
* **Git LFS Attachments**: All bug report attachments (`build/attachments/` and `feedback/attachments/`) are tracked in **GitHub LFS** and considered public to the repository; never attach sensitive credentials, secret tokens, private keys, or proprietary secrets.
* **Unresolved Bug Persistence Mandate**: If a bug or defect cannot be fully resolved in the current turn or session (due to missing datasheets, ambiguous specifications, external blockers, or incomplete verification), update the bug entry in SQLite and markdown files (via `python tools/dashboard.py`) with all investigation notes, reproduction steps, and blocking details, leaving its status as `OPEN`. NEVER mark an unresolved or partially completed bug as resolved, closed, or silently drop it from tracking.

## 4. VCS Engine & Operations
* **DAG Tree Smartlog**: The VCS engine renders smartlog commit graphs and working tree status dynamically.
* **CLI Parity**: All major VCS operations (syncing, committing, amending, diff viewing) are supported via both web workstation APIs and CLI subcommands (`python tools/dashboard.py sync`, `python tools/dashboard.py commit`).
* **Commit Author & Privacy Redaction**: Personal usernames, personal email addresses, and author identities (such as user nicknames and personal email domains) MUST be automatically elided and sanitized in the VCS engine (`GitEngine`), smartlog DAG models, commit info summaries, API responses, and web workstation UI templates (`code_review.html.j2`, `diff_view.html.j2`) into generic labels (`User`, `user@workspace`). Never leak the user's real or personal names in commit logs, smartlog displays, code review sessions, or git-tracked documentation.

## 5. Bidirectional Dashboard & Script Cross-Patching Mandate
* **Automatic Cross-Repository Synchronization**: Any bug fix, feature enhancement, styling update, or refactoring applied to developer scripts, tooling, or dashboard components in one repository (`firmware` or `hardware`) that is applicable to the other repository MUST be automatically cross-patched and mirrored into that repository, and vice versa.
* **Synchronized Subsystems**: This includes, but is not limited to:
  - Remote cloud runner and lifecycle orchestration (`tools/anvil`, `tools/vast_manager.py`, `~/.anvil.env`, `~/.anvil.lock`).
  - VCS web workstation and dashboard backends (`tools/dashboard.py`, `provider/vcs/git_engine.py`, `provider/worm_report/`, `provider/bug_report/`).
  - Shared workstation templates (`diff_view.html.j2`, `diff_component.html.j2`, `code_review.html.j2`, `worm_report.html.j2`, `bug_report.html.j2`).
  - Smartlog DAG tree rendering, commit selection, node highlighting, and author identity sanitization.
* **Zero Disparity**: Never allow dashboard bug fixes or tooling improvements (such as node highlighting, reverse-proxying, detached branch persistence, or SSH port handling) to remain isolated in one repository when the other repository shares the same architecture or template.

