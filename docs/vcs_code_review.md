# VCS Workstation, Code Review & Quake HUD Templates

Guidelines for Quake VCS dashboard, Jinja2 templating, code review persistence, and Git LFS bug tracking.

## 1. Code Generation & Jinja2 Templates
* **Jinja2 Templating Engine**: Always use Jinja2 (`jinja2`) to generate templated Python scripts, Blender headless scripts, URDF models, or simulation configurations rather than embedding large multi-line f-strings directly inside Python source files.
* **Dedicated Templates Directory**: All templated script files (`.py.j2`, `.yaml.j2`, `.urdf.j2`, `.sh.j2`) MUST be stored in a dedicated `templates/` folder nested within the respective package or module (e.g., `src/provider/templates/`).
* **Clean Rendering & Context Separation**: Render external Jinja2 templates via `jinja2.Environment(loader=jinja2.FileSystemLoader(...), trim_blocks=True, lstrip_blocks=True)` or package loaders, passing configuration parameters as explicit dictionaries or strongly typed models.
* **No Silent Exception Swallowing in Templates**: Templated scripts (`.py.j2`) MUST follow standard code quality standards. Never generate `try/except/pass` fallback ladders inside Jinja2 templates; inspect environment capabilities deterministically via template variables.

## 2. Review Session Feedback & SQLite Persistence
* **Review Persistence**: The interactive code review web dashboard (`dashboard.py /review`) and server (`DashboardServer` / `ReviewServer`) MUST persist session feedback, comments, and file review statuses across server restarts.
* **Atomic Storage**: Feedback is persisted atomically to SQLite (`build/code_review.sqlite`, `SQLiteReviewStore`) with automatic synchronization to JSON state (`build/cr_feedback.json`), Markdown reports (`feedback/CR.md`), and granular commit review files (`feedback/CR_<commit>.md`).
* **CLI & Subcommands**: Query review status in the console (`python src/dashboard.py list-reviews` or `--reviews`), filter unresolved comments (`--open`), or resolve items (`python src/dashboard.py resolve-comment <id>`).

## 3. Structured Bug Tracking & Git LFS Attachments
* **Defect Lifecycle**: Defects, routing anomalies, and visual flaws must be tracked systematically using the Dashboard CLI (`src/dashboard.py`) and persisted in SQLite (`build/bugs.sqlite`, `SQLiteBugStore`), synchronized automatically to `feedback/BUGS.md`, individual issue files (`feedback/BUG_<id>.md`), and `build/bugs_state.json`.
* **Git LFS Attachments**: All bug report attachments (`build/attachments/` and `feedback/attachments/`) are tracked in **GitHub LFS** and considered public to the repository; never attach sensitive credentials, secret tokens, private keys, or proprietary secrets.
* **Unresolved Bug Persistence Mandate**: If a bug or defect cannot be fully resolved in the current turn or session (due to missing datasheets, ambiguous specifications, external blockers, or incomplete verification), update the bug entry in SQLite and markdown files (via `python src/dashboard.py`) with all investigation notes, reproduction steps, and blocking details, leaving its status as `OPEN`. NEVER mark an unresolved or partially completed bug as resolved, closed, or silently drop it from tracking.

## 4. VCS Engine & Operations
* **DAG Tree Smartlog**: The VCS engine renders smartlog commit graphs and working tree status dynamically.
* **CLI Parity**: All major VCS operations (syncing, committing, amending, diff viewing) are supported via both web workstation APIs and CLI subcommands (`python src/dashboard.py sync`, `python src/dashboard.py commit`).
