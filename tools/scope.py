#!/usr/bin/env python3
"""Interactive CAD/PCB Scope Workstation CLI tool."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Optional, Sequence
import urllib.parse

# Setup import paths
_tools_dir = Path(__file__).resolve().parent
_repo_dir = _tools_dir.parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))
if str(_repo_dir) not in sys.path:
    sys.path.insert(0, str(_repo_dir))

from provider.browser import launch_browser, get_default_icon_path
from provider.shell import Logger
from provider.target_list import parse_target_string
from provider.provider_manager import ProviderManager

get_scope_icon_path = get_default_icon_path


def setup_scope_logging(log_file: Optional[Path] = None, verbose: bool = False) -> logging.Logger:
    """Configure structured logging for Scope workstation."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logger = logging.getLogger("scope")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not logger.handlers:
        target_log = log_file or (_repo_dir / "build" / "scope.log")
        target_log.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(target_log), encoding="utf-8")
        fh.setLevel(logging.DEBUG if verbose else logging.INFO)
        fh.setFormatter(logging.Formatter(log_format, date_format))
        logger.addHandler(fh)

        if verbose:
            ch = logging.StreamHandler(sys.stderr)
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(logging.Formatter(log_format, date_format))
            logger.addHandler(ch)

    return logger


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a network port is already actively bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def find_available_port(start_port: int = 8000, host: str = "127.0.0.1", max_attempts: int = 50) -> int:
    """Find the first open TCP port beginning at start_port."""
    for p in range(start_port, start_port + max_attempts):
        if not is_port_in_use(p, host):
            return p
    return start_port


class ScopeTool:
    """Coordinates CAD/PCB Scope Workstation server, geometry pipeline, and browser launching."""

    def __init__(
        self,
        manager: Optional[ProviderManager] = None,
        logger: Optional[Logger] = None,
    ):
        """Initialize ScopeTool dependencies."""
        self.manager = manager
        self.logger = logger or Logger(enabled=True)

    def handle_stop(self) -> int:
        """Stop running Scope workstation daemon."""
        lock_file = _repo_dir / "build" / "scope.lock"
        if lock_file.exists():
            try:
                data = json.loads(lock_file.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if pid:
                    os.kill(pid, signal.SIGTERM)
                    deadline = time.time() + 1.5
                    while time.time() < deadline:
                        try:
                            os.kill(pid, 0)
                            time.sleep(0.05)
                        except OSError:
                            break
                    self.logger.print(f"Stopped Scope workstation (PID {pid}).", symbol="➜")
            except OSError as e:
                self.logger.print(f"Could not stop Scope: {e}", symbol="❌")
            finally:
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                    except OSError:
                        pass
            return 0
        else:
            self.logger.print("Scope workstation is not running.", symbol="➜")
            return 0

    def run_headless_simulation(self, args: argparse.Namespace) -> int:
        """Execute physical simulation headlessly without GUI and capture RRD / MP4 artifacts."""
        from provider.scope.pipeline import ScopeGeometryPipeline
        from provider.types import Section, Mode
        from provider.room import Room

        primary_target = args.targets[0] if args.targets else None
        if not primary_target:
            self.logger.print("Error: No target specified for simulation capture.", symbol="❌")
            return 1

        proj, target, sub, auto_mode = parse_target_string(primary_target)
        mode = args.mode or auto_mode or "SIMULATE"

        self.logger.print(
            f"Initializing headless simulation capture for {proj}/{target} (mode: {mode})...",
            symbol="🌊",
        )

        pipeline = ScopeGeometryPipeline(manager=self.manager, logger=self.logger)

        try:
            parsed_targets = pipeline.target_parser.resolve(primary_target, Section.VIEW)
        except Exception:
            try:
                parsed_targets = pipeline.target_parser.resolve(f"{proj}/{target}", Section.VIEW)
            except Exception as err:
                self.logger.print(f"Error: Failed to resolve simulation view target: {err}", symbol="❌")
                return 1

        parsed_targets = parsed_targets.for_modes([Mode.SIMULATE])
        results = pipeline.manager.router.run(parsed_targets)
        if not results:
            self.logger.print(f"Error: No simulation room produced for target '{primary_target}'.", symbol="❌")
            return 1

        fq_target = f"{proj}/{target}"

        # Ensure URDF is compiled if not already present
        from tools.list import Lister

        lister = Lister(pipeline.manager, self.logger)
        urdf_rel_path = lister.get_urdf_output(fq_target)
        real_urdf_path = Path("build") / urdf_rel_path
        if not real_urdf_path.exists():
            from tools.build import Builder

            builder = Builder(pipeline.manager, self.logger)
            builder.export_urdf([fq_target])

        for room_name, room in results:
            if not isinstance(room, Room):
                self.logger.print(f"Error: Target '{room_name}' did not produce a Room object.", symbol="❌")
                return 1

            steps = args.steps if args.steps is not None else 20000
            save_rrd = args.save_rrd
            save_mp4 = args.save_mp4

            if save_rrd:
                Path(save_rrd).parent.mkdir(parents=True, exist_ok=True)
            if save_mp4:
                Path(save_mp4).parent.mkdir(parents=True, exist_ok=True)

            self.logger.print(
                f"Running simulation: {steps} steps -> RRD: {save_rrd or 'None'}, MP4: {save_mp4 or 'None'}",
                symbol="🤖",
            )

            p_map = {p.name: p for p in pipeline.manager.router.providers}
            provider = p_map.get(proj)
            hooks = getattr(room, "provider_hooks", None)
            if not hooks and provider:
                try:
                    hooks = provider.get_simulate_hooks(target)
                except Exception:
                    hooks = {}
            if hooks is None:
                hooks = {}

            room.simulate(
                provider_hooks=hooks,
                proj_name=proj,
                sim_target=fq_target,
                steps=steps,
                manager=pipeline.manager,
                logger=self.logger,
                save_rrd=save_rrd,
                save_mp4=save_mp4,
                fps=args.fps,
                spawn_viewer=False,
                stage_window_size=args.stage_window_size,
            )
            self.logger.print("Headless simulation completed successfully.", symbol="✅")
            if save_rrd and Path(save_rrd).exists():
                size_mb = Path(save_rrd).stat().st_size / (1024 * 1024)
                self.logger.print(f"Artifact captured: {save_rrd} ({size_mb:.2f} MB)", symbol="📦")
            if save_mp4 and Path(save_mp4).exists():
                size_mb = Path(save_mp4).stat().st_size / (1024 * 1024)
                self.logger.print(f"Artifact captured: {save_mp4} ({size_mb:.2f} MB)", symbol="📦")

        return 0

    def run(self, args: argparse.Namespace) -> int:
        """Execute Scope workstation server lifecycle."""
        # 1. Subcommands
        if args.targets and args.targets[0] == "stop":
            return self.handle_stop()

        if args.targets and args.targets[0] == "restart":
            self.handle_stop()
            args.targets = args.targets[1:]

        # 2. Headless simulation capture mode (e.g. anvil simulate ... -s 500 --save-rrd ...)
        if getattr(args, "save_rrd", None) or getattr(args, "save_mp4", None):
            return self.run_headless_simulation(args)

        primary_target = args.targets[0] if args.targets else None
        proj, target, sub, auto_mode = parse_target_string(primary_target)
        mode = args.mode or auto_mode

        expected_query = (
            urllib.parse.urlencode(
                {
                    "project": proj,
                    "target": target,
                    "subassembly": sub or "",
                    "mode": mode,
                }
            )
            if proj
            else ""
        )

        lock_file = _repo_dir / "build" / "scope.lock"
        if lock_file.exists() and not getattr(args, "no_detach", False):
            try:
                data = json.loads(lock_file.read_text(encoding="utf-8"))
                running_pid = data.get("pid")
                running_url = data.get("url", "")
                if running_pid:
                    try:
                        os.kill(running_pid, 0)
                        running_query = urllib.parse.urlsplit(running_url).query
                        if getattr(args, "no_browser", False) and running_query == expected_query:
                            self.logger.print(
                                f"Scope workstation is already running at {running_url} (PID {running_pid}).",
                                symbol="➜",
                            )
                            self.logger.print(
                                "Use 'python tools/scope.py stop' or 'python tools/scope.py restart' to manage it.",
                                symbol="➜",
                            )
                            return 0
                        self.handle_stop()
                    except OSError:
                        lock_file.unlink(missing_ok=True)
            except (json.JSONDecodeError, OSError):
                lock_file.unlink(missing_ok=True)

        port = args.port
        if is_port_in_use(port, args.host):
            port = find_available_port(start_port=port, host=args.host)

        if proj:
            server_url = f"http://{args.host}:{port}/?{expected_query}"
        else:
            server_url = f"http://{args.host}:{port}/"

        # 2. Detach from terminal unless --no-detach / --foreground is requested
        if not getattr(args, "no_detach", False):
            log_dir = _repo_dir / "build"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "scope.log"
            log_file = open(log_path, "a", encoding="utf-8")

            filtered_args = []
            skip_next = False
            for arg in sys.argv[1:]:
                if skip_next:
                    skip_next = False
                    continue
                if arg in ("--no-detach", "--foreground"):
                    continue
                if arg == "--port":
                    skip_next = True
                    continue
                if arg.startswith("--port="):
                    continue
                filtered_args.append(arg)

            child_args = (
                [sys.executable, str(Path(sys.argv[0]).resolve())]
                + filtered_args
                + ["--no-detach", "--port", str(port)]
            )

            popen_kwargs = {
                "stdout": log_file,
                "stderr": log_file,
                "stdin": subprocess.DEVNULL,
            }
            if os.name == "posix":
                popen_kwargs["start_new_session"] = True
            elif sys.platform in ("win32", "win64"):
                detached_flag = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                new_grp_flag = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                popen_kwargs["creationflags"] = detached_flag | new_grp_flag

            proc = subprocess.Popen(child_args, **popen_kwargs)

            deadline = time.time() + 5.0
            while time.time() < deadline:
                if proc.poll() is not None:
                    self.logger.print("Error: Scope workstation failed to start.", symbol="❌")
                    return 1
                if lock_file.exists():
                    try:
                        data = json.loads(lock_file.read_text(encoding="utf-8"))
                        if data.get("pid") == proc.pid:
                            break
                    except (json.JSONDecodeError, OSError):
                        pass
                time.sleep(0.05)

            self.logger.print(f"Scope workstation running at {server_url} (PID {proc.pid}).", symbol="➜")
            self.logger.print("Detached from terminal.", symbol="➜")
            return 0

        # 3. Foreground / non-detached server process
        scope_logger = setup_scope_logging(args.log_file, verbose=args.verbose)
        scope_logger.info("Starting Scope workstation in foreground (PID %d)...", os.getpid())

        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "url": server_url,
                    "no_browser": getattr(args, "no_browser", False),
                }
            ),
            encoding="utf-8",
        )

        self.logger.print(f"Scope workstation running at {server_url} (PID {os.getpid()}).", symbol="➜")

        from provider.scope import ScopeServer, ScopeGeometryPipeline

        pipeline = ScopeGeometryPipeline()
        server = ScopeServer(
            host=args.host,
            port=port,
            repo_root=_repo_dir,
            pipeline=pipeline,
            logger=scope_logger,
            bind_and_activate=True,
        )
        if proj and target:
            server.warm_up(
                project=proj,
                target=target,
                subassembly=sub,
                mode=mode,
            )

        if not args.no_browser:

            def _on_close():
                scope_logger.info("Desktop window closed; shutting down scope server...")
                threading.Thread(target=server.shutdown, daemon=True).start()

            threading.Thread(
                target=launch_browser,
                args=(server_url, args.browser),
                kwargs={
                    "title": "◈ SCOPE // CAD/PCB WORKSTATION ◈",
                    "bg_color": "#0d0f14",
                    "icon_path": get_default_icon_path(_repo_dir),
                    "on_close": _on_close,
                },
                daemon=True,
            ).start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            scope_logger.info("Shutting down scope server...")
        finally:
            if lock_file.exists():
                try:
                    lock_file.unlink()
                except OSError:
                    pass
            server.server_close()

        return 0


def setup_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser for Scope workstation."""
    parser = argparse.ArgumentParser(
        description="Launch Interactive CAD/PCB Scope Workstation with Forge Target Bug integration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=[],
        help="Target to inspect (e.g. carrier_board/carrier_board:pcb, cat_fountain/bowl:part).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP port to bind (default: 8000).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--mode",
        choices=["CAD", "PCB", "SIMULATE", "DIAGRAM"],
        default=None,
        help="Override visualization mode.",
    )
    parser.add_argument(
        "--browser",
        choices=["webview", "eel"],
        default="webview",
        help="Display environment ('webview' native window or 'eel').",
    )
    parser.add_argument(
        "--app",
        action="store_const",
        dest="browser",
        const="webview",
        help="Open in standalone desktop window (default).",
    )
    parser.add_argument(
        "--no-app",
        "--no-browser",
        action="store_true",
        dest="no_browser",
        help="Disable opening desktop window; run server only.",
    )
    parser.add_argument(
        "--no-detach",
        "--foreground",
        action="store_true",
        dest="no_detach",
        help="Run workstation server in the foreground without detaching from terminal.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        dest="verbose",
        help="Enable verbose debug logging.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Path to scope log file (default: build/scope.log).",
    )
    parser.add_argument(
        "-s",
        "--steps",
        type=int,
        default=None,
        help="Number of simulation steps to run in simulation capture mode.",
    )
    parser.add_argument(
        "--save-rrd",
        type=str,
        default=None,
        help="Path to save simulation Rerun recording (.rrd) in GUI-less capture mode.",
    )
    parser.add_argument(
        "--save-mp4",
        type=str,
        default=None,
        help="Path to save simulation video recording (.mp4) in GUI-less capture mode.",
    )
    parser.add_argument(
        "--stage-window-size",
        type=int,
        default=None,
        help="Stage window size for staging and merging simulation recordings.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=60,
        help="Simulation frame rate (default: 60).",
    )
    return parser


def get_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for Scope workstation."""
    parser = setup_parser()
    return parser.parse_args(argv)


def main(logger: Optional[Logger] = None, args: Optional[argparse.Namespace] = None) -> int:
    """Program entry point for Scope workstation."""
    if args is None:
        args = get_args()
    if logger is None:
        logger = Logger(enabled=True)

    tool = ScopeTool(logger=logger)
    return tool.run(args)


if __name__ == "__main__":
    sys.exit(main())
