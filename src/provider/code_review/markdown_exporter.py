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
import uuid as uuid_pkg

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

        if session.commit_history:
            lines.extend(
                [
                    "## Commit Updates & History",
                    "",
                    "| Action | Original Commit | Current Commit | Timestamp | Notes |",
                    "| :--- | :--- | :--- | :--- | :--- |",
                ]
            )
            for upd in session.commit_history:
                lines.append(
                    f"| `{upd.action}` | `{upd.original_commit}` | `{upd.current_commit}` | `{upd.timestamp}` | {upd.notes or '_None_'} |"
                )
            lines.append("")

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
                            f"<!-- comment-uuid: {comment.uuid} -->",
                        ]
                    )
                    if comment.commit:
                        lines.append(f"<!-- comment-commit: {comment.commit} -->")
                    lines.append("")

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
                    f"- [{checked}] **[{sev_tag}]** [`{comment.file_path}:{line_range_str}`]({abs_file_url}): {summary_formatted} <!-- uuid:{comment.uuid} -->"
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

    def parse_markdown_text(self, content: str) -> ReviewSessionModel:
        """Parse raw CR.md or CR_<commit>.md text content into a ReviewSessionModel.

        Args:
            content: Raw Markdown string.

        Returns:
            ReviewSessionModel populated with parsed comments.
        """
        title_m = re.search(r"^#\s+Code Review Report:\s*(.*?)$", content, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else "Code Review"

        session = ReviewSessionModel(title=title)

        # Parse checklist items to extract resolution states: - [x] or - [ ]
        checklist_data: Dict[str, bool] = {}
        for line in content.splitlines():
            chk_m = re.match(
                r"^-\s+\[([ xX])\]\s+\*\*\[(.*?)\]\*\*\s+\[`([^`:]+):L?(\d+)(?:-L?(\d+))?`\](?:\([^)]*\))?:\s*(.*?)(?:\s*<!--\s*uuid:([a-fA-F0-9-]+)\s*-->)?$",
                line.strip(),
            )
            if chk_m:
                is_resolved = chk_m.group(1).lower() == "x"
                fpath = chk_m.group(3).strip()
                s_line = int(chk_m.group(4))
                e_line = int(chk_m.group(5)) if chk_m.group(5) else s_line
                uuid_str = chk_m.group(7)
                if uuid_str:
                    checklist_data[uuid_str] = is_resolved
                checklist_data[f"{fpath}:{s_line}-{e_line}"] = is_resolved

        # Parse inline comment sections
        comment_blocks = re.split(r"\n(?=####\s+\*\*\[)", content)
        for block in comment_blocks:
            block_clean = block.strip()
            if not block_clean.startswith("####"):
                continue

            header_m = re.match(r"####\s+\*\*\[(.*?)\]\*\*\s+\[([^:]+):L?(\d+)(?:-L?(\d+))?\]", block_clean)
            if not header_m:
                continue

            sev_str = header_m.group(1).strip().replace(" ", "_").upper()
            try:
                sev = ReviewSeverity(sev_str)
            except ValueError:
                sev = ReviewSeverity.MUST_FIX

            fpath = header_m.group(2).strip()
            start_line = int(header_m.group(3))
            end_line = int(header_m.group(4)) if header_m.group(4) else start_line

            uuid_m = re.search(r"<!--\s*comment-uuid:\s*([a-fA-F0-9-]+)\s*-->", block_clean)
            c_uuid = uuid_m.group(1).strip() if uuid_m else str(uuid_pkg.uuid4())

            commit_m = re.search(r"<!--\s*comment-commit:\s*([^\s>]+)\s*-->", block_clean)
            c_commit = commit_m.group(1).strip() if commit_m else ""

            snippet_m = re.search(r"```[a-zA-Z0-9_-]*\n(.*?)\n```", block_clean, re.DOTALL)
            code_snippet = snippet_m.group(1).strip() if snippet_m else ""

            body_m = re.search(r">\s+\*\*Reviewer\s*\((.*?)\)\*\*:\s*(.*?)$", block_clean, re.MULTILINE | re.DOTALL)
            author = "Reviewer"
            body = ""
            if body_m:
                author = body_m.group(1).strip()
                body = body_m.group(2).strip()
            else:
                body_lines = [l.lstrip("> ").strip() for l in block_clean.splitlines() if l.startswith(">")]
                body = "\n".join(body_lines).strip()

            body = re.sub(r"\[`(@[^`]+)`\]\([^)]+\)", r"\1", body)
            resolved = checklist_data.get(c_uuid, checklist_data.get(f"{fpath}:{start_line}-{end_line}", False))

            comment = CommentModel(
                id=c_uuid[:8],
                uuid=c_uuid,
                file_path=fpath,
                start_line=start_line,
                end_line=end_line,
                severity=sev,
                body=body,
                author=author,
                code_snippet=code_snippet,
                created_at=datetime.now(timezone.utc).isoformat(),
                resolved=resolved,
                commit=c_commit,
            )
            session.comments.append(comment)

        return session

    def merge_commit_feedback(self, session: ReviewSessionModel, cr_commit_file: Path) -> ReviewSessionModel:
        """Auto-merge CR feedback if the CR file already exists for a commit.

        Args:
            session: Active review session model.
            cr_commit_file: Path to existing CR_<commit>.md file.

        Returns:
            Updated ReviewSessionModel with merged feedback.
        """
        if not cr_commit_file.exists() or not cr_commit_file.is_file():
            return session
        try:
            commit_from_filename = ""
            if cr_commit_file.stem.startswith("CR_") and cr_commit_file.stem != "CR":
                commit_from_filename = cr_commit_file.stem[3:]

            content = cr_commit_file.read_text(encoding="utf-8")
            parsed_session = self.parse_markdown_text(content)
            existing_by_uuid = {c.uuid: c for c in session.comments if c.uuid}
            existing_by_loc = {(c.file_path, c.start_line, c.end_line): c for c in session.comments}

            for pc in parsed_session.comments:
                if not pc.commit and commit_from_filename:
                    pc.commit = commit_from_filename

                match_c = None
                if pc.uuid and pc.uuid in existing_by_uuid:
                    match_c = existing_by_uuid[pc.uuid]
                elif (pc.file_path, pc.start_line, pc.end_line) in existing_by_loc:
                    match_c = existing_by_loc[(pc.file_path, pc.start_line, pc.end_line)]

                if match_c:
                    if pc.resolved:
                        match_c.resolved = True
                    if pc.body and pc.body != match_c.body:
                        match_c.body = pc.body
                else:
                    session.comments.append(pc)
                    if pc.uuid:
                        existing_by_uuid[pc.uuid] = pc
                    existing_by_loc[(pc.file_path, pc.start_line, pc.end_line)] = pc
        except Exception:
            pass
        return session

    def export_commit_markdown(
        self,
        session: ReviewSessionModel,
        commit_sha: str,
        feedback_dir: Path,
        total_repo_files: int = 0,
    ) -> Optional[Path]:
        """Export commit-specific review findings to feedback/CR_<commit>.md.

        Only exports if there are comments associated with this commit. If no comments
        exist for the commit, any existing CR_<commit>.md is unlinked.

        Args:
            session: Active review session model.
            commit_sha: Commit hash or identifier.
            feedback_dir: Directory where CR_<commit>.md is stored.
            total_repo_files: Total changed files count.

        Returns:
            Path to written markdown report, or None if no comments exist for commit.
        """
        feedback_dir.mkdir(parents=True, exist_ok=True)
        safe_sha = commit_sha.replace("/", "_").strip()
        target_path = feedback_dir / f"CR_{safe_sha}.md"

        # Filter comments for commit_sha
        commit_comments = [
            c
            for c in session.comments
            if (
                c.commit
                and (
                    c.commit == safe_sha
                    or safe_sha.startswith(c.commit)
                    or c.commit.startswith(safe_sha)
                )
            )
            or (
                not c.commit
                and session.commit_hash
                and (
                    session.commit_hash == safe_sha
                    or safe_sha.startswith(session.commit_hash)
                    or session.commit_hash.startswith(safe_sha)
                )
            )
        ]

        if not commit_comments:
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass
            return None

        commit_session = session.model_copy(deep=True)
        commit_session.comments = commit_comments
        commit_session.revisions = [commit_sha]
        md_text = self.render_markdown(commit_session, total_repo_files=total_repo_files)
        target_path.write_text(md_text, encoding="utf-8")
        return target_path
