"""Markdown export engine for repository bug tracking.

Converts bug report database states, severities, attachments, and resolution notes
into a clean GitHub-flavored Markdown document (build/BUGS.md) with overview metrics,
action checklists, and embedded references.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Dict, List, Optional

from model.bug_report import (
    BugAttachmentModel,
    BugCategory,
    BugDatabaseModel,
    BugReportModel,
    BugSeverity,
    BugStatus,
)


class MarkdownBugExporter:
    """Serializes bug tracker databases to GitHub-flavored Markdown and JSON."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize exporter with repository base path.

        Args:
            repo_root: Base path of repository for file links.
        """
        self.repo_root = repo_root

    def export_markdown(self, database: BugDatabaseModel, output_path: Path) -> Path:
        """Generate and save BUGS.md markdown document.

        Args:
            database: Active bug database model.
            output_path: Destination path for BUGS.md file.

        Returns:
            Resolved Path where markdown was saved.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        md_text = self.render_markdown(database)
        output_path.write_text(md_text, encoding="utf-8")
        return output_path

    def render_markdown(self, database: BugDatabaseModel) -> str:
        """Render bug database to structured GitHub-flavored Markdown.

        Args:
            database: Bug database model.

        Returns:
            Formatted Markdown document string.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        status_counts = database.count_by_status()
        severity_counts = database.count_by_severity()
        category_counts = database.count_by_category()

        total_bugs = len(database.bugs)
        open_bugs = sum(1 for b in database.bugs if b.status in (BugStatus.OPEN, BugStatus.IN_PROGRESS))
        resolved_bugs = sum(1 for b in database.bugs if b.status in (BugStatus.RESOLVED, BugStatus.CLOSED))
        resolved_pct = int((resolved_bugs / total_bugs) * 100) if total_bugs > 0 else 100

        lines: List[str] = [
            f"# Bug Report Tracker: {database.title}",
            "",
            "> Automated bug tracking, triage, and issue registry generated via Hardware Bug Report Engine.",
            "",
            "## Tracker Overview",
            "",
            "| Metric | Details |",
            "| :--- | :--- |",
            f"| **Report Date** | `{now_str}` |",
            f"| **Total Issues** | `{total_bugs}` |",
            f"| **Open Issues** | `{open_bugs}` |",
            f"| **Resolved / Closed** | `{resolved_bugs} ({resolved_pct}%)` |",
            "",
        ]

        if database.summary.strip():
            lines.extend(
                [
                    "## Executive Summary",
                    "",
                    database.summary.strip(),
                    "",
                ]
            )

        # Severity breakdown table
        lines.extend(
            [
                "## Issues by Severity",
                "",
                "| Severity | Count | Meaning |",
                "| :--- | :---: | :--- |",
                f"| **`[CRITICAL]`** | {severity_counts.get(BugSeverity.CRITICAL.value, 0)} | System crashes, build failures, blockages, or electrical shorts. |",
                f"| **`[HIGH]`** | {severity_counts.get(BugSeverity.HIGH.value, 0)} | Major functional defects, broken routing, DRC violations, or unphysical behavior. |",
                f"| **`[MEDIUM]`** | {severity_counts.get(BugSeverity.MEDIUM.value, 0)} | Silkscreen collisions, layout sub-optimality, or visual clipping. |",
                f"| **`[LOW]`** | {severity_counts.get(BugSeverity.LOW.value, 0)} | Minor aesthetic imperfections or documentation notes. |",
                "",
            ]
        )

        # Subsystem breakdown table
        lines.extend(
            [
                "## Issues by Category",
                "",
                "| Category | Count | Description |",
                "| :--- | :---: | :--- |",
                f"| **`PCB`** | {category_counts.get(BugCategory.PCB.value, 0)} | Schematics, routing, footprints, nets, DRC, silkscreen. |",
                f"| **`CAD`** | {category_counts.get(BugCategory.CAD.value, 0)} | 3D geometry, step models, enclosures, mechanical assembly. |",
                f"| **`SIMULATION`** | {category_counts.get(BugCategory.SIMULATION.value, 0)} | JAX SPH fluid dynamics, PyBullet kinematics, physics. |",
                f"| **`INFRASTRUCTURE`** | {category_counts.get(BugCategory.INFRASTRUCTURE.value, 0)} | Build tooling, compilers, test runners, headless tools. |",
                f"| **`UI`** | {category_counts.get(BugCategory.UI.value, 0)} | Web dashboards, CLI viewers, review interfaces. |",
                "",
            ]
        )

        # Issue checklist
        lines.extend(
            [
                "## Issue Checklist",
                "",
            ]
        )
        if not database.bugs:
            lines.append("_No bugs registered in tracker._\n")
        else:
            for b in database.bugs:
                chk = "x" if b.status in (BugStatus.RESOLVED, BugStatus.CLOSED) else " "
                comp_tag = f" `[{b.component}]`" if b.component else ""
                lines.append(
                    f"- [{chk}] **`[{b.severity.value}]`** [#{b.id}](#{b.id.lower()}): {b.title}{comp_tag} (`{b.status.value}`)"
                )
            lines.append("")

        # Detailed Issue Specifications
        lines.extend(
            [
                "## Detailed Issue Log",
                "",
            ]
        )

        for b in database.bugs:
            status_icon = (
                "🟢"
                if b.status in (BugStatus.RESOLVED, BugStatus.CLOSED)
                else ("🟡" if b.status == BugStatus.IN_PROGRESS else "🔴")
            )
            lines.extend(
                [
                    f'### <a id="{b.id.lower()}"></a> {status_icon} `[{b.id}]` {b.title}',
                    "",
                    f"- **Status**: `{b.status.value}`",
                    f"- **Severity**: `{b.severity.value}`",
                    f"- **Category**: `{b.category.value}`",
                ]
            )
            if b.component:
                lines.append(f"- **Component**: `{b.component}`")
            if b.created_at:
                lines.append(f"- **Created**: `{b.created_at}`")
            if b.resolved_at:
                lines.append(f"- **Resolved**: `{b.resolved_at}`")
            lines.append("")

            if b.description.strip():
                lines.extend(
                    [
                        "#### Description",
                        "",
                        b.description.strip(),
                        "",
                    ]
                )

            if b.reproduction_steps:
                lines.extend(
                    [
                        "#### Reproduction Steps",
                        "",
                    ]
                )
                for step_idx, step in enumerate(b.reproduction_steps, 1):
                    lines.append(f"{step_idx}. {step}")
                lines.append("")

            if b.expected_behavior.strip() or b.actual_behavior.strip():
                lines.extend(
                    [
                        "#### Behavior Comparison",
                        "",
                        f"- **Expected**: {b.expected_behavior.strip() or '_Not specified_'}",
                        f"- **Actual**: {b.actual_behavior.strip() or '_Not specified_'}",
                        "",
                    ]
                )

            if b.logs.strip():
                lines.extend(
                    [
                        "#### Execution / Console Logs",
                        "",
                        "```text",
                        b.logs.strip(),
                        "```",
                        "",
                    ]
                )

            if b.attachments:
                lines.extend(
                    [
                        "#### Attachments & References",
                        "",
                        "| Type | Filename | Description |",
                        "| :--- | :--- | :--- |",
                    ]
                )
                for att in b.attachments:
                    lines.append(
                        f"| `{att.file_type}` | [{att.filename}]({att.file_path}) | {att.description or '_None_'} |"
                    )
                lines.append("")

            if b.resolution_notes.strip():
                lines.extend(
                    [
                        "#### Resolution Notes",
                        "",
                        b.resolution_notes.strip(),
                        "",
                    ]
                )

            lines.append("---\n")

        return "\n".join(lines).strip() + "\n"

    def export_state_json(self, database: BugDatabaseModel, state_path: Path) -> Path:
        """Persist bug database to JSON file.

        Args:
            database: Bug database model.
            state_path: Destination JSON file path.

        Returns:
            Resolved Path where JSON was saved.
        """
        state_path.parent.mkdir(parents=True, exist_ok=True)
        data = database.model_dump(mode="json")
        state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return state_path

    def load_state_json(self, state_path: Path) -> Optional[BugDatabaseModel]:
        """Load bug database from JSON file if it exists.

        Args:
            state_path: Path to JSON state file.

        Returns:
            BugDatabaseModel if file exists and is valid, else None.
        """
        if not state_path.exists():
            return None
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            return BugDatabaseModel.model_validate(data)
        except Exception:
            return None

    def parse_markdown(self, markdown_path: Path) -> Optional[BugDatabaseModel]:
        """Parse an existing BUGS.md file into a BugDatabaseModel.

        Args:
            markdown_path: Path to BUGS.md file.

        Returns:
            BugDatabaseModel if file exists and was parsed, else None.
        """
        if not markdown_path.exists():
            return None
        try:
            content = markdown_path.read_text(encoding="utf-8")
            return self.parse_markdown_text(content)
        except Exception:
            return None

    def parse_markdown_text(self, content: str) -> BugDatabaseModel:
        """Parse raw BUGS.md text content into a BugDatabaseModel.

        Args:
            content: Raw Markdown string.

        Returns:
            BugDatabaseModel populated with parsed issues.
        """
        title_match = re.search(r"^#\s+Bug Report Tracker:\s*(.*?)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Hardware Bug Tracker"

        # Check list items for quick-action statuses: - [x] or - [ ]
        checklist_status: Dict[str, BugStatus] = {}
        for line in content.splitlines():
            chk_m = re.match(r"^-\s+\[([ xX])\]\s+.*?\b(BUG-\d+)\b", line)
            if chk_m:
                is_checked = chk_m.group(1).lower() == "x"
                chk_id = chk_m.group(2)
                checklist_status[chk_id] = BugStatus.RESOLVED if is_checked else BugStatus.OPEN

        db = BugDatabaseModel(title=title)

        # Split into bug sections by ### headers
        sections = re.split(r"\n(?=###\s+)", content)
        for sec in sections:
            sec_clean = sec.strip()
            if not sec_clean.startswith("###"):
                continue

            header_match = re.search(
                r'###\s+(?:<a id=".*?></a>\s*)?(?:[^\n\[]*?)?`\[(BUG-\d+)\]`\s*(.*?)$', sec_clean, re.MULTILINE
            )
            if not header_match:
                continue

            bug_id = header_match.group(1).strip()
            bug_title = header_match.group(2).strip()

            # Parse metadata lines
            status_val = BugStatus.OPEN
            m_status = re.search(r"-\s+\*\*Status\*\*:\s*`?([A-Za-z_]+)`?", sec_clean)
            if m_status:
                try:
                    status_val = BugStatus(m_status.group(1).strip().upper())
                except ValueError:
                    status_val = BugStatus.OPEN
            elif bug_id in checklist_status:
                status_val = checklist_status[bug_id]

            # If checklist explicitly checked [x], prefer RESOLVED unless CLOSED
            if checklist_status.get(bug_id) == BugStatus.RESOLVED and status_val == BugStatus.OPEN:
                status_val = BugStatus.RESOLVED

            severity_val = BugSeverity.MEDIUM
            m_sev = re.search(r"-\s+\*\*Severity\*\*:\s*`?([A-Za-z_]+)`?", sec_clean)
            if m_sev:
                try:
                    severity_val = BugSeverity(m_sev.group(1).strip().upper())
                except ValueError:
                    severity_val = BugSeverity.MEDIUM

            category_val = BugCategory.GENERAL
            m_cat = re.search(r"-\s+\*\*Category\*\*:\s*`?([A-Za-z_]+)`?", sec_clean)
            if m_cat:
                try:
                    category_val = BugCategory(m_cat.group(1).strip().upper())
                except ValueError:
                    category_val = BugCategory.GENERAL

            component_val = ""
            m_comp = re.search(r"-\s+\*\*Component\*\*:\s*`?([^\n`*]+)`?", sec_clean)
            if m_comp:
                component_val = m_comp.group(1).strip()

            created_val = ""
            m_created = re.search(r"-\s+\*\*Created\*\*:\s*`?([^\n`*]+)`?", sec_clean)
            if m_created:
                created_val = m_created.group(1).strip()

            resolved_val = None
            m_resolved = re.search(r"-\s+\*\*Resolved\*\*:\s*`?([^\n`*]+)`?", sec_clean)
            if m_resolved:
                resolved_val = m_resolved.group(1).strip()

            # Parse subsections: ####
            subsections = re.split(r"\n(?=####\s+)", sec_clean)
            desc = ""
            steps: List[str] = []
            expected = ""
            actual = ""
            logs = ""
            res_notes = ""
            attachments: List[BugAttachmentModel] = []

            for sub in subsections:
                sub_clean = sub.strip()
                if not sub_clean.startswith("####"):
                    continue

                sub_lines = sub_clean.splitlines()
                sub_title = sub_lines[0].replace("####", "").strip().lower()
                sub_body = "\n".join(sub_lines[1:]).strip()
                # Remove trailing divider --- if present
                if sub_body.endswith("---"):
                    sub_body = sub_body[:-3].strip()

                match sub_title:
                    case "description":
                        desc = sub_body
                    case "reproduction steps":
                        for step_line in sub_body.splitlines():
                            step_m = re.match(r"^\d+\.\s*(.*?)$", step_line.strip())
                            if step_m:
                                steps.append(step_m.group(1).strip())
                            elif step_line.strip().startswith("-"):
                                steps.append(step_line.strip().lstrip("-").strip())
                    case "expected behavior":
                        expected = sub_body
                    case "actual behavior":
                        actual = sub_body
                    case "execution / console logs":
                        cleaned_logs = sub_body
                        if cleaned_logs.startswith("```"):
                            first_nl = cleaned_logs.find("\n")
                            if first_nl != -1:
                                cleaned_logs = cleaned_logs[first_nl + 1 :]
                        if cleaned_logs.endswith("```"):
                            cleaned_logs = cleaned_logs[:-3]
                        logs = cleaned_logs.strip()
                    case "resolution notes":
                        res_notes = sub_body
                    case "attachments & references":
                        for att_line in sub_body.splitlines():
                            att_m = re.match(
                                r"^\|\s*`?(.*?)`?\s*\|\s*\[(.*?)\]\((.*?)\)\s*\|\s*(.*?)\s*\|$", att_line.strip()
                            )
                            if att_m:
                                ftype = att_m.group(1).strip()
                                fname = att_m.group(2).strip()
                                fpath = att_m.group(3).strip()
                                fdesc = att_m.group(4).strip()
                                if fdesc in ("_None_", "None"):
                                    fdesc = ""
                                attachments.append(
                                    BugAttachmentModel(
                                        id=f"att-{len(attachments) + 1}",
                                        filename=fname,
                                        file_type=ftype,
                                        file_path=fpath,
                                        description=fdesc,
                                    )
                                )

            bug = BugReportModel(
                id=bug_id,
                title=bug_title,
                status=status_val,
                severity=severity_val,
                category=category_val,
                component=component_val,
                created_at=created_val or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                resolved_at=resolved_val,
                description=desc,
                reproduction_steps=steps,
                expected_behavior=expected,
                actual_behavior=actual,
                logs=logs,
                attachments=attachments,
                resolution_notes=res_notes,
            )
            db.add_or_update(bug)

        return db

    def merge_databases(self, base_db: BugDatabaseModel, md_db: BugDatabaseModel) -> BugDatabaseModel:
        """Merge markdown database changes into base database using Read-Modify-Write rules.

        Args:
            base_db: Current base database model (e.g. from SQLite).
            md_db: Database model parsed from BUGS.md.

        Returns:
            Updated base_db with all merged changes.
        """
        existing_map = {b.id: b for b in base_db.bugs}

        for md_bug in md_db.bugs:
            if md_bug.id not in existing_map:
                # Newly added bug in BUGS.md
                base_db.bugs.append(md_bug)
                existing_map[md_bug.id] = md_bug
            else:
                existing = existing_map[md_bug.id]
                # Status update
                if md_bug.status != existing.status:
                    existing.status = md_bug.status
                    if md_bug.status in (BugStatus.RESOLVED, BugStatus.CLOSED):
                        if not existing.resolved_at:
                            existing.resolved_at = md_bug.resolved_at or datetime.now(timezone.utc).strftime(
                                "%Y-%m-%d %H:%M:%S UTC"
                            )
                    else:
                        existing.resolved_at = None

                # Non-empty title / severity / category / component updates
                if md_bug.title and md_bug.title != existing.title:
                    existing.title = md_bug.title
                if md_bug.severity != existing.severity:
                    existing.severity = md_bug.severity
                if md_bug.category != existing.category:
                    existing.category = md_bug.category
                if md_bug.component and md_bug.component != existing.component:
                    existing.component = md_bug.component

                # Description & notes
                if md_bug.description.strip() and md_bug.description.strip() != existing.description.strip():
                    existing.description = md_bug.description
                if (
                    md_bug.resolution_notes.strip()
                    and md_bug.resolution_notes.strip() != existing.resolution_notes.strip()
                ):
                    existing.resolution_notes = md_bug.resolution_notes

                # Reproduction steps
                if md_bug.reproduction_steps and md_bug.reproduction_steps != existing.reproduction_steps:
                    existing.reproduction_steps = md_bug.reproduction_steps

                # Behaviors & logs
                if (
                    md_bug.expected_behavior.strip()
                    and md_bug.expected_behavior.strip() != existing.expected_behavior.strip()
                ):
                    existing.expected_behavior = md_bug.expected_behavior
                if (
                    md_bug.actual_behavior.strip()
                    and md_bug.actual_behavior.strip() != existing.actual_behavior.strip()
                ):
                    existing.actual_behavior = md_bug.actual_behavior
                if md_bug.logs.strip() and md_bug.logs.strip() != existing.logs.strip():
                    existing.logs = md_bug.logs

                # Attachments: merge unique by file_path
                existing_paths = {a.file_path for a in existing.attachments}
                for att in md_bug.attachments:
                    if att.file_path not in existing_paths:
                        existing.attachments.append(att)
                        existing_paths.add(att.file_path)

        return base_db
