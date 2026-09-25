"""Markdown export engine for code review findings and feedback.

Converts review session states, line comments, and file annotations into a
GitHub-flavored Markdown document (CR.md) with clickable links, code snippets,
severity badges, and action checklists.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Dict, List, Optional

from model.code_review import (
    CommentModel,
    FileReviewStatus,
    ReviewSessionModel,
    ReviewSeverity,
)
from provider.code_review.git_utils import is_file_ignored


class MarkdownReviewExporter:
    """Serializes review sessions to GitHub-flavored Markdown and JSON."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize exporter with repository root path.

        Args:
            repo_root: Base path of git repository for absolute file links.
        """
        self.repo_root = repo_root

    def export_markdown(
        self,
        session: ReviewSessionModel,
        output_path: Path,
        total_repo_files: int = 0,
    ) -> Path:
        """Generate and save CR.md markdown report.

        Args:
            session: Active review session state.
            output_path: Destination path for CR.md file.
            total_repo_files: Total changed files count.

        Returns:
            Resolved Path where markdown was saved.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        md_text = self.render_markdown(session, total_repo_files=total_repo_files)
        output_path.write_text(md_text, encoding="utf-8")
        return output_path

    def render_markdown(self, session: ReviewSessionModel, total_repo_files: int = 0) -> str:
        """Render review session to a structured Markdown string.

        Args:
            session: Active review session model.
            total_repo_files: Total count of changed files.

        Returns:
            Formatted Markdown document string.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        revisions_str = ", ".join(session.revisions) if session.revisions else "Working Tree / HEAD"

        severity_counts = session.count_by_severity()
        reviewed_count = sum(1 for f in session.files.values() if f.status == FileReviewStatus.REVIEWED)
        total_files = max(total_repo_files, len(session.files), 1)
        progress_pct = int((reviewed_count / total_files) * 100)

        lines: List[str] = [
            f"# Code Review Report: {session.title}",
            "",
            "> Automated code review log and findings generated via Quake Code Review Engine.",
            "",
            "## Review Overview",
            "",
            "| Metric | Details |",
            "| :--- | :--- |",
            f"| **Review Date** | `{now_str}` |",
            f"| **Revisions** | `{revisions_str}` |",
            f"| **Overall Verdict** | **`{session.verdict.value}`** |",
            f"| **Review Progress** | `{reviewed_count}/{total_files} files reviewed ({progress_pct}%)` |",
            f"| **Total Comments** | `{len(session.comments)} findings` |",
            "",
        ]

        if session.summary.strip():
            lines.extend(
                [
                    "## Executive Summary",
                    "",
                    session.summary.strip(),
                    "",
                ]
            )

        # Severity breakdown table
        lines.extend(
            [
                "## Findings by Severity",
                "",
                "| Severity | Count | Meaning |",
                "| :--- | :---: | :--- |",
                f"| **[MUST FIX]** | {severity_counts.get(ReviewSeverity.MUST_FIX.value, 0)} | Must be resolved before merge; bugs, defects, or safety regressions. |",
                f"| **[PROPOSAL]** | {severity_counts.get(ReviewSeverity.PROPOSAL.value, 0)} | Architecture ideas, design proposals, or optional enhancements. |",
                f"| **[NIT]** | {severity_counts.get(ReviewSeverity.NIT.value, 0)} | Minor formatting, naming, or cosmetic cleanups. |",
                "",
            ]
        )

        # Group comments by file
        comments_by_file: Dict[str, List[CommentModel]] = {}
        for comment in session.comments:
            comments_by_file.setdefault(comment.file_path, []).append(comment)

        all_file_paths = [
            fp
            for fp in sorted(set(list(session.files.keys()) + list(comments_by_file.keys())))
            if not is_file_ignored(fp)
        ]

        lines.extend(
            [
                "## File-by-File Review Findings",
                "",
            ]
        )

        if not all_file_paths:
            lines.extend(["*No files marked or commented on in this review session.*", ""])
        else:
            for file_path in all_file_paths:
                file_state = session.files.get(file_path)
                file_status = file_state.status.value if file_state else FileReviewStatus.PENDING.value
                file_notes = file_state.notes if file_state and file_state.notes else ""

                abs_file_url = f"file://{(self.repo_root / file_path).resolve()}"
                status_badge = "✅ `REVIEWED`" if file_status == "REVIEWED" else "⏳ `PENDING`"

                lines.extend(
                    [
                        f"### [`{file_path}`]({abs_file_url}) — {status_badge}",
                        "",
                    ]
                )

                if file_notes:
                    lines.extend([f"**File Notes**: {file_notes}", ""])

                file_comments = comments_by_file.get(file_path, [])
                if not file_comments:
                    lines.extend(["*No inline comments on this file.*", ""])
                    continue

                for comment in file_comments:
                    sev = comment.severity.value.replace("_", " ")
                    start = comment.start_line
                    end = comment.end_line
                    line_range_str = f"L{start}" if start == end else f"L{start}-L{end}"
                    line_url = f"{abs_file_url}#{line_range_str}"

                    lines.extend(
                        [
                            f"#### **[{sev}]** [{file_path}:{line_range_str}]({line_url})",
                            "",
                        ]
                    )

                    if comment.code_snippet.strip():
                        lang = self._detect_language(file_path)
                        lines.extend(
                            [
                                f"```{lang}",
                                comment.code_snippet.strip(),
                                "```",
                                "",
                            ]
                        )

                    lines.extend(
                        [
                            f"> **Reviewer ({comment.author})**: {self._format_file_references(comment.body)}",
                            "",
                        ]
                    )

        # Action checklist
        lines.extend(
            [
                "## Action Items Checklist",
                "",
            ]
        )

        action_comments = [
            c for c in session.comments if c.severity in [ReviewSeverity.MUST_FIX, ReviewSeverity.PROPOSAL]
        ]
        if not action_comments:
            lines.extend(["*No blocker or major action items remaining.*", ""])
        else:
            for comment in action_comments:
                start = comment.start_line
                end = comment.end_line
                line_range_str = f"L{start}" if start == end else f"L{start}-L{end}"
                abs_file_url = f"file://{(self.repo_root / comment.file_path).resolve()}#{line_range_str}"
                checked = "x" if comment.resolved else " "
                summary_snippet = comment.body.splitlines()[0] if comment.body else "Review item"
                summary_formatted = self._format_file_references(summary_snippet)
                sev_tag = comment.severity.value.replace("_", " ")
                lines.append(
                    f"- [{checked}] **[{sev_tag}]** [`{comment.file_path}:{line_range_str}`]({abs_file_url}): {summary_formatted}"
                )
            lines.append("")

        return "\n".join(lines)

    def _detect_language(self, file_path: str) -> str:
        """Infer markdown code block language from file extension."""
        suffix = Path(file_path).suffix.lower()
        match suffix:
            case ".py":
                return "python"
            case ".yaml" | ".yml":
                return "yaml"
            case ".json":
                return "json"
            case ".md":
                return "markdown"
            case ".sh" | ".bash" | ".zsh":
                return "bash"
            case ".html" | ".htm":
                return "html"
            case ".css":
                return "css"
            case ".js" | ".mjs":
                return "javascript"
            case ".ts":
                return "typescript"
            case ".c" | ".h":
                return "c"
            case ".cpp" | ".hpp" | ".cc":
                return "cpp"
            case _:
                return ""

    def _format_file_references(self, text: str) -> str:
        """Parse @file/path:line and @[file/path] references into clickable markdown file links."""
        if not text:
            return ""

        def _resolve_link(raw_ref: str) -> str:
            raw_ref = raw_ref.strip()
            line_anchor = ""
            file_part = raw_ref
            if ":" in raw_ref:
                file_part, line_part = raw_ref.split(":", 1)
                line_part = line_part.lstrip("L")
                line_anchor = f"#L{line_part}"

            p = Path(file_part)
            if p.is_absolute():
                abs_url = f"file://{p.resolve()}{line_anchor}"
            else:
                abs_url = f"file://{(self.repo_root / p).resolve()}{line_anchor}"

            return f"[`@{raw_ref}`]({abs_url})"

        pattern = re.compile(r"(@\[([^\]]+)\]|(?:^|(?<=\s))@([a-zA-Z0-9_./\\-]+(?::L?\d+(?:-L?\d+)?)?))")

        def _replacer(match: re.Match) -> str:
            bracketed = match.group(2)
            plain = match.group(3)
            trailing_punct = ""
            if plain:
                m_punct = re.search(r"[.,;:!?)]+$", plain)
                if m_punct:
                    trailing_punct = m_punct.group(0)
                    plain = plain[: -len(trailing_punct)]

            raw_ref = bracketed or plain
            if not raw_ref:
                return match.group(0)
            if plain and not any(c in plain for c in ["/", ".", ":"]):
                return match.group(0)
            return _resolve_link(raw_ref) + trailing_punct

        return pattern.sub(_replacer, text)

    def save_session_json(self, session: ReviewSessionModel, path: Path) -> None:
        """Serialize review session state to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        payload = session.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_session_json(self, path: Path) -> Optional[ReviewSessionModel]:
        """Deserialize review session state from JSON file if present."""
        if not path.exists() or not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReviewSessionModel.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return None
