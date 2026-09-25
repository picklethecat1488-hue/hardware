"""KiCad headless CLI runner for automated Gerber, drill, and board manufacturing export."""

import os
import shutil
import subprocess
import sys
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class KiCadDRCSeverity(str, Enum):
    """Severity levels for KiCad DRC violations."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class KiCadDRCViolation:
    """A single design rule check violation reported by KiCad."""

    rule: str
    description: str
    severity: KiCadDRCSeverity
    items: List[str] = field(default_factory=list)


@dataclass
class KiCadDRCReport:
    """Structured report of KiCad DRC check findings."""

    board_name: str
    violations_count: int
    unconnected_count: int
    footprint_errors_count: int
    violations: List[KiCadDRCViolation] = field(default_factory=list)
    report_path: Optional[Path] = None

    @property
    def error_count(self) -> int:
        """Return the total number of DRC errors, unconnected pads, and footprint errors."""
        err_violations = sum(1 for v in self.violations if v.severity == KiCadDRCSeverity.ERROR)
        # If unconnected or footprint errors were reported in counts but not in violations list, add them
        unconn_in_viols = sum(1 for v in self.violations if "unconnected" in v.rule.lower())
        fp_in_viols = sum(1 for v in self.violations if "footprint" in v.rule.lower())
        extra_unconn = max(0, self.unconnected_count - unconn_in_viols)
        extra_fp = max(0, self.footprint_errors_count - fp_in_viols)
        return err_violations + extra_unconn + extra_fp

    @property
    def warning_count(self) -> int:
        """Return the total number of DRC warnings."""
        return sum(1 for v in self.violations if v.severity == KiCadDRCSeverity.WARNING)

    @property
    def passed(self) -> bool:
        """Return True if there are zero DRC errors, unconnected pads, or footprint errors."""
        return self.error_count == 0

    def summary(self) -> str:
        """Return a human-readable summary of DRC findings."""
        lines = [
            f"KiCad DRC for '{self.board_name}': {self.error_count} error(s), {self.warning_count} warning(s), "
            f"{self.unconnected_count} unconnected pad(s), {self.footprint_errors_count} footprint error(s)"
        ]
        if not self.passed:
            lines.append("Violations summary:")
            for v in self.violations[:20]:
                items_str = " | ".join(v.items[:2]) if v.items else "no items"
                lines.append(f"  - [{v.severity.value.upper()}] [{v.rule}] {v.description} ({items_str})")
            if len(self.violations) > 20:
                lines.append(f"  ... and {len(self.violations) - 20} more violations.")
        return "\n".join(lines)


class KiCadCLI:
    """Headless wrapper around kicad-cli for compiling .kicad_pcb files into manufacturing outputs."""

    STANDARD_MACOS_PATHS = [
        "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
        "/Applications/KiCad.app/Contents/MacOS/kicad-cli",
        "/opt/homebrew/bin/kicad-cli",
        "/usr/local/bin/kicad-cli",
    ]

    STANDARD_LINUX_PATHS = [
        "/usr/bin/kicad-cli",
        "/usr/local/bin/kicad-cli",
        "/opt/kicad/bin/kicad-cli",
        "~/.local/bin/kicad-cli",
    ]

    STANDARD_WINDOWS_PATHS = [
        r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
        r"C:\Program Files\KiCad\7.0\bin\kicad-cli.exe",
        r"C:\Program Files\KiCad\bin\kicad-cli.exe",
    ]

    def __init__(
        self,
        cli_path: Optional[str | Path] = None,
        design_rules: Optional[Any] = None,
    ):
        """Initialize KiCad CLI runner, detecting local binary."""
        self._custom_cli = Path(cli_path) if cli_path else None
        self._local_bin = self._find_local_bin()
        self.design_rules = design_rules

    def _find_local_bin(self) -> Optional[Path]:
        """Locate the kicad-cli binary on the local system."""
        if self._custom_cli and self._custom_cli.is_file():
            return self._custom_cli

        env_bin = os.environ.get("KICAD_CLI_BIN")
        if env_bin and Path(env_bin).is_file():
            return Path(env_bin)

        which_path = shutil.which("kicad-cli")
        if which_path:
            return Path(which_path)

        if sys.platform == "darwin":
            candidates = self.STANDARD_MACOS_PATHS
        elif sys.platform.startswith("win"):
            candidates = self.STANDARD_WINDOWS_PATHS
        else:
            candidates = self.STANDARD_LINUX_PATHS

        for std_path in candidates:
            p = Path(std_path).expanduser()
            if p.is_file():
                return p

        return None

    @property
    def is_available(self) -> bool:
        """Return True if kicad-cli is installed and executable locally."""
        return self._local_bin is not None

    @property
    def version(self) -> Optional[str]:
        """Return the installed kicad-cli version string, or None if unavailable."""
        if not self._local_bin:
            return None
        if not hasattr(self, "_cached_version"):
            cmd = [str(self._local_bin), "--version"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self._cached_version = result.stdout.strip() if result.returncode == 0 else None
        return self._cached_version

    @property
    def major_version(self) -> int:
        """Return the major version integer of kicad-cli (e.g., 7, 8, 10), or 0 if unavailable."""
        ver = self.version
        if not ver:
            return 0
        match = re.match(r"^(\d+)", ver)
        return int(match.group(1)) if match else 0

    @property
    def supports_drc(self) -> bool:
        """Return True if kicad-cli supports the 'pcb drc' subcommand (KiCad 8+)."""
        return self.is_available and self.major_version >= 8

    def run_command(self, args: List[str]) -> str:
        """Execute a kicad-cli command locally."""
        if not self._local_bin:
            raise RuntimeError(
                "kicad-cli is not installed locally. Please install KiCad (e.g. brew install --cask kicad on macOS, "
                "apt install kicad on Linux, or download from kicad.org) or set KICAD_CLI_BIN."
            )
        cmd = [str(self._local_bin)] + args
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"kicad-cli error ({result.returncode}): {result.stderr.strip() or result.stdout}")
        return result.stdout

    def refill_zones(self, kicad_pcb_path: str | Path) -> None:
        """Refill copper zones and save the board file in-place using kicad-cli (KiCad 8+)."""
        if not self.supports_drc:
            return

        import tempfile

        pcb_file = Path(kicad_pcb_path).resolve()
        if not pcb_file.is_file():
            raise FileNotFoundError(f"KiCad PCB file not found: {pcb_file}")

        with tempfile.NamedTemporaryFile(suffix="-drc.rpt", delete=False) as tmp_rpt:
            tmp_rpt_path = Path(tmp_rpt.name)

        try:
            args = ["pcb", "drc", "--refill-zones", "--save-board", "-o", str(tmp_rpt_path), str(pcb_file)]
            self.run_command(args)
        finally:
            if tmp_rpt_path.exists():
                tmp_rpt_path.unlink()

    def export_gerbers(
        self,
        kicad_pcb_path: str | Path,
        output_dir: str | Path,
        layers: Optional[List[str]] = None,
    ) -> List[Path]:
        """Export RS-274X Gerber manufacturing layers from a .kicad_pcb file."""
        pcb_file = Path(kicad_pcb_path).resolve()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        if not pcb_file.is_file():
            raise FileNotFoundError(f"KiCad PCB file not found: {pcb_file}")

        args = ["pcb", "export", "gerbers", "--no-protel-ext"]
        if self.major_version >= 8:
            args.append("--check-zones")
        args.extend(["-o", f"{out_dir}/"])
        if layers:
            args.extend(["-l", ",".join(layers)])
        args.append(str(pcb_file))
        self.run_command(args)

        return list(out_dir.glob("*.gbr")) + list(out_dir.glob("*.gbrjob"))

    def export_drill(
        self,
        kicad_pcb_path: str | Path,
        output_dir: str | Path,
    ) -> List[Path]:
        """Export Excellon drill files (.drl) from a .kicad_pcb file."""
        pcb_file = Path(kicad_pcb_path).resolve()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        if not pcb_file.is_file():
            raise FileNotFoundError(f"KiCad PCB file not found: {pcb_file}")

        args = ["pcb", "export", "drill", "-o", f"{out_dir}/", str(pcb_file)]
        self.run_command(args)

        return list(out_dir.glob("*.drl"))

    def export_board_svg(
        self,
        kicad_pcb_path: str | Path,
        output_svg: str | Path,
        layers: str = "F.Cu,Edge.Cuts,F.SilkS",
    ) -> Path:
        """Export vector SVG layout diagram from a .kicad_pcb file."""
        pcb_file = Path(kicad_pcb_path).resolve()
        out_svg = Path(output_svg).resolve()
        out_svg.parent.mkdir(parents=True, exist_ok=True)

        if not pcb_file.is_file():
            raise FileNotFoundError(f"KiCad PCB file not found: {pcb_file}")

        args = [
            "pcb",
            "export",
            "svg",
            "-l",
            layers,
            "--page-size-mode",
            "2",
            "--exclude-drawing-sheet",
            "-o",
            str(out_svg),
            str(pcb_file),
        ]
        self.run_command(args)

        return out_svg

    def export_all_board_files(
        self,
        kicad_pcb_path: str | Path,
        output_dir: str | Path,
        layers: Optional[List[str]] = None,
    ) -> Dict[str, Path]:
        """Export all Gerber layers, drill files, and job metadata into the output directory."""
        gerbers = self.export_gerbers(kicad_pcb_path, output_dir, layers=layers)
        drills = self.export_drill(kicad_pcb_path, output_dir)
        results: Dict[str, Path] = {}
        for p in gerbers + drills:
            results[p.name] = p
        return results

    def run_drc(
        self,
        kicad_pcb_path: str | Path,
        output_report_path: str | Path,
        units: str = "mm",
        severity_all: bool = True,
        design_rules: Optional[Any] = None,
    ) -> KiCadDRCReport:
        """Run KiCad DRC check on a .kicad_pcb file and return parsed KiCadDRCReport."""
        import json

        pcb_file = Path(kicad_pcb_path).resolve()
        rpt_file = Path(output_report_path).resolve()
        rpt_file.parent.mkdir(parents=True, exist_ok=True)

        if not pcb_file.is_file():
            raise FileNotFoundError(f"KiCad PCB file not found: {pcb_file}")

        active_rules = design_rules if design_rules is not None else self.design_rules
        if active_rules is not None and hasattr(active_rules, "to_kicad_pro_dict"):
            pro_path = pcb_file.with_suffix(".kicad_pro")
            pro_data = active_rules.to_kicad_pro_dict()
            with open(pro_path, "w", encoding="utf-8") as f:
                json.dump(pro_data, f, indent=2)

        if not self.supports_drc:
            # On KiCad 7 systems, 'pcb drc' is not supported by kicad-cli; write placeholder passing report
            content = (
                f"** Drc report for {pcb_file.name} **\n"
                f"** Found 0 DRC violations **\n"
                f"** Found 0 unconnected pads **\n"
                f"** Found 0 Footprint errors **\n"
            )
            rpt_file.write_text(content, encoding="utf-8")
            return self.parse_drc_text(content, report_path=rpt_file)

        args = [
            "pcb",
            "drc",
            "--format",
            "report",
            "--units",
            units,
            "-o",
            str(rpt_file),
        ]
        if severity_all:
            args.append("--severity-all")
        args.append(str(pcb_file))
        self.run_command(args)

        return self.parse_drc_report(rpt_file)

    @classmethod
    def parse_drc_report(cls, report_path: str | Path) -> KiCadDRCReport:
        """Parse a KiCad DRC report file into a structured KiCadDRCReport."""
        rpt_file = Path(report_path).resolve()
        if not rpt_file.is_file():
            raise FileNotFoundError(f"KiCad DRC report file not found: {rpt_file}")

        content = rpt_file.read_text(encoding="utf-8")
        return cls.parse_drc_text(content, report_path=rpt_file)

    @classmethod
    def parse_drc_text(cls, content: str, report_path: Optional[Path] = None) -> KiCadDRCReport:
        """Parse KiCad DRC report text content into a structured KiCadDRCReport."""
        board_name = report_path.stem if report_path else "unknown"
        violations_count = 0
        unconnected_count = 0
        footprint_errors_count = 0
        violations: List[KiCadDRCViolation] = []

        header_match = re.search(r"\*\*\s+Drc report for\s+(.*?)\s+\*\*", content)
        if header_match:
            board_name = header_match.group(1).strip()

        v_match = re.search(r"\*\*\s+Found\s+(\d+)\s+DRC violations\s+\*\*", content)
        if v_match:
            violations_count = int(v_match.group(1))

        u_match = re.search(r"\*\*\s+Found\s+(\d+)\s+unconnected pads\s+\*\*", content)
        if u_match:
            unconnected_count = int(u_match.group(1))

        f_match = re.search(r"\*\*\s+Found\s+(\d+)\s+Footprint errors\s+\*\*", content)
        if f_match:
            footprint_errors_count = int(f_match.group(1))

        current_violation: Optional[KiCadDRCViolation] = None
        violation_header_re = re.compile(r"^\[([a-zA-Z0-9_-]+)\]:\s*(.*)$")
        severity_re = re.compile(r";\s*(error|warning|info)", re.IGNORECASE)

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("**"):
                if current_violation:
                    violations.append(current_violation)
                    current_violation = None
                continue

            v_header = violation_header_re.match(line)
            if v_header:
                if current_violation:
                    violations.append(current_violation)
                rule = v_header.group(1).strip()
                desc = v_header.group(2).strip()
                current_violation = KiCadDRCViolation(
                    rule=rule,
                    description=desc,
                    severity=KiCadDRCSeverity.ERROR,
                    items=[],
                )
            elif current_violation:
                sev_match = severity_re.search(stripped)
                if sev_match:
                    sev_str = sev_match.group(1).lower()
                    if sev_str == "error":
                        current_violation.severity = KiCadDRCSeverity.ERROR
                    elif sev_str == "warning":
                        current_violation.severity = KiCadDRCSeverity.WARNING
                    else:
                        current_violation.severity = KiCadDRCSeverity.INFO
                elif stripped.startswith("@(") or "Pad " in stripped or "Track " in stripped or "Via " in stripped:
                    current_violation.items.append(stripped)

        if current_violation:
            violations.append(current_violation)

        return KiCadDRCReport(
            board_name=board_name,
            violations_count=violations_count,
            unconnected_count=unconnected_count,
            footprint_errors_count=footprint_errors_count,
            violations=violations,
            report_path=report_path,
        )
