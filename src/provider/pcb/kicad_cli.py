"""KiCad headless CLI runner for automated Gerber, drill, and board manufacturing export."""

import os
import shutil
import subprocess
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

    def __init__(self, cli_path: Optional[str | Path] = None):
        """Initialize KiCad CLI runner, detecting local or remote executor."""
        self._custom_cli = Path(cli_path) if cli_path else None
        self._local_bin = self._find_local_bin()
        self._use_remote_anvil = False

        if not self._local_bin:
            self._use_remote_anvil = self._check_remote_anvil()

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

        for std_path in self.STANDARD_MACOS_PATHS:
            p = Path(std_path)
            if p.is_file():
                return p

        return None

    def _check_remote_anvil(self) -> bool:
        """Check if kicad-cli is available on the remote anvil server."""
        try:
            res = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", "anvil", "which kicad-cli"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            return res.returncode == 0 and bool(res.stdout.strip())
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        """Return True if kicad-cli can be executed locally or via anvil."""
        return self._local_bin is not None or self._use_remote_anvil

    def run_command(self, args: List[str]) -> str:
        """Execute a kicad-cli command locally or remotely via anvil."""
        if self._local_bin:
            cmd = [str(self._local_bin)] + args
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise RuntimeError(f"kicad-cli error ({result.returncode}): {result.stderr.strip() or result.stdout}")
            return result.stdout

        if self._use_remote_anvil:
            remote_cmd = "kicad-cli " + " ".join(args)
            result = subprocess.run(
                ["ssh", "anvil", remote_cmd],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Remote kicad-cli error ({result.returncode}): {result.stderr.strip() or result.stdout}"
                )
            return result.stdout

        raise RuntimeError(
            "kicad-cli is not installed locally or on anvil. Please install KiCad (e.g. brew install --cask kicad)."
        )

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

        if self._local_bin:
            args = ["pcb", "export", "gerbers", "--no-protel-ext", "-o", f"{out_dir}/"]
            if layers:
                args.extend(["-l", ",".join(layers)])
            args.append(str(pcb_file))
            self.run_command(args)
        else:
            # Execute on remote anvil server and pull back output files
            remote_pcb = f"/tmp/{pcb_file.name}"
            remote_out = f"/tmp/gerbers_{pcb_file.stem}"
            subprocess.run(["scp", str(pcb_file), f"anvil:{remote_pcb}"], check=True, capture_output=True)
            ssh_cmd = f"rm -rf {remote_out} && mkdir -p {remote_out} && kicad-cli pcb export gerbers --no-protel-ext"
            if layers:
                ssh_cmd += f" -l {','.join(layers)}"
            ssh_cmd += f" -o {remote_out}/ {remote_pcb}"
            subprocess.run(["ssh", "anvil", ssh_cmd], check=True, capture_output=True)
            subprocess.run(["rsync", "-az", f"anvil:{remote_out}/", f"{out_dir}/"], check=True, capture_output=True)

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

        if self._local_bin:
            args = ["pcb", "export", "drill", "-o", f"{out_dir}/", str(pcb_file)]
            self.run_command(args)
        else:
            remote_pcb = f"/tmp/{pcb_file.name}"
            remote_out = f"/tmp/drill_{pcb_file.stem}"
            subprocess.run(["scp", str(pcb_file), f"anvil:{remote_pcb}"], check=True, capture_output=True)
            ssh_cmd = f"rm -rf {remote_out} && mkdir -p {remote_out} && kicad-cli pcb export drill -o {remote_out}/ {remote_pcb}"
            subprocess.run(["ssh", "anvil", ssh_cmd], check=True, capture_output=True)
            subprocess.run(["rsync", "-az", f"anvil:{remote_out}/", f"{out_dir}/"], check=True, capture_output=True)

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

        if self._local_bin:
            args = [
                "pcb",
                "export",
                "svg",
                "-l",
                layers,
                "--page-size-mode",
                "2",
                "-o",
                str(out_svg),
                str(pcb_file),
            ]
            self.run_command(args)
        else:
            remote_pcb = f"/tmp/{pcb_file.name}"
            remote_svg = f"/tmp/{out_svg.name}"
            subprocess.run(["scp", str(pcb_file), f"anvil:{remote_pcb}"], check=True, capture_output=True)
            ssh_cmd = f"kicad-cli pcb export svg -l {layers} --page-size-mode 2 -o {remote_svg} {remote_pcb}"
            subprocess.run(["ssh", "anvil", ssh_cmd], check=True, capture_output=True)
            subprocess.run(["scp", f"anvil:{remote_svg}", str(out_svg)], check=True, capture_output=True)

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
