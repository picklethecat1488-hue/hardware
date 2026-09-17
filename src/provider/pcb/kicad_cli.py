"""KiCad headless CLI runner for automated Gerber, drill, and board manufacturing export."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


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

    def __init__(self, cli_path: Optional[str | Path] = None):
        """Initialize KiCad CLI runner, detecting local binary."""
        self._custom_cli = Path(cli_path) if cli_path else None
        self._local_bin = self._find_local_bin()

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

        args = ["pcb", "export", "gerbers", "--no-protel-ext", "-o", f"{out_dir}/"]
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
