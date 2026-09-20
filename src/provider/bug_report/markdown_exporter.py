"""Markdown export engine for repository bug tracking.

Converts bug report database states, severities, attachments, and resolution notes
into a clean GitHub-flavored Markdown document (build/BUGS.md) with overview metrics,
action checklists, and embedded references.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional

from model.bug_report import (
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
