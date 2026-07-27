"""Background build daemon and client for visualizer and build tools."""

import argparse
import contextlib
import inspect
import cbor2
import json
import logging
import os
import socket
import subprocess
import sys
import time
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional, List
from pydantic import validate_call


class DaemonCommand(StrEnum):
    """Supported commands for the build daemon."""

    RUN = "run"
    STOP = "stop"
    STATUS = "status"


class RequestField(StrEnum):
    """Fields in the client-server request payload."""

    COMMAND = "command"
    TOOL = "tool"
    ARGV = "argv"
    OUTDIR = "outdir"
    ENV = "env"


# Project-isolated UNIX Domain Socket path
SOCKET_PATH = Path(__file__).parent.parent / "build" / ".daemon.sock"
LOG_PATH = Path(__file__).parent.parent / "build" / "daemon.log"
BUFFER_SIZE = 8192
RELOAD_PREFIXES = (
    "projects.",
    "projects_config.",
    "provider",
    "model",
    "shell",
    "target_parser",
    "list",
    "build",
    "config",
    "view",
    "daemon",
)


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log as a JSON object."""
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


class StreamToLogger:
    """Redirects stream writes to a Python Logger as structured JSON entries."""

    def __init__(self, logger: logging.Logger, log_level: int = logging.INFO):
        """Initialize the logger."""
        self.logger = logger
        self.log_level = log_level

    def write(self, buf: str) -> int:
        """Write to the logger."""
        if buf and buf.strip():
            for line in buf.splitlines():
                if line.strip():
                    self.logger.log(self.log_level, line.strip())
        return len(buf)

    def flush(self):
        """Flush the logger."""
        pass


# Initialize structured logger
daemon_log = logging.getLogger("daemon")
daemon_log.setLevel(logging.INFO)
if not daemon_log.handlers:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(LOG_PATH), encoding="utf-8")
    formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    handler.setFormatter(formatter)
    daemon_log.addHandler(handler)


@contextlib.contextmanager
def daemon_connection(socket_path: Path):
    """Context manager to yield a connected client socket and ensure its closure."""
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client_socket.connect(str(socket_path))
        yield client_socket
    finally:
        client_socket.close()


class SocketStream:
    """Redirects writes to a socket connection."""

    def __init__(self, conn: socket.socket):
        """Initialize the Socket stream."""
        self.conn = conn

    def write(self, data: str) -> int:
        """Write data to the socket stream."""
        if data:
            try:
                self.conn.sendall(data.encode("utf-8"))
                return len(data)
            except OSError:
                pass
        return 0

    def flush(self):
        """Flush the socket stream."""
        pass


class DaemonServer:
    """Persistent server keeping providers and @method_cache in memory."""

    @validate_call(config={"arbitrary_types_allowed": True})
    def __init__(self, socket_path: Path = SOCKET_PATH):
        """Initialize the Daemon Server."""
        self.socket_path = socket_path
        self.last_load_time = 0.0
        self.manager: Optional[Any] = None

    @validate_call(config={"arbitrary_types_allowed": True})
    def reload_modules_if_needed(self):
        """Unload and reload modified modules to pick up code changes."""
        src_dir = Path(__file__).parent
        max_mtime = 0.0
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith((".py", ".yaml", ".yml")):
                    try:
                        mtime = (Path(root) / file).stat().st_mtime
                        if mtime > max_mtime:
                            max_mtime = mtime
                    except Exception:
                        pass

        # If any files were modified since last load time, reload modules
        if max_mtime > self.last_load_time or self.manager is None:
            modules_to_unload = []
            for name in list(sys.modules.keys()):
                if name.startswith(RELOAD_PREFIXES) and name != __name__:
                    modules_to_unload.append(name)

            for mod in modules_to_unload:
                sys.modules.pop(mod, None)

            # Re-import dependencies
            from model import AppConfig
            from provider import ProviderManager

            config = AppConfig()
            self.manager = ProviderManager(config, bootstrap=True)
            self.last_load_time = time.time()
            daemon_log.info("Core modules reloaded successfully.")

    @validate_call(config={"arbitrary_types_allowed": True})
    def run(self):
        """Start the UNIX Domain Socket server loop."""
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

        # Redirect daemon process's own stdout and stderr to structured logging
        sys.stdout = StreamToLogger(daemon_log, logging.INFO)
        sys.stderr = StreamToLogger(daemon_log, logging.ERROR)

        server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server_socket.bind(str(self.socket_path))
            # Restrict socket permissions so only the owner can read/write to it
            os.chmod(str(self.socket_path), 0o600)
            server_socket.listen(5)
            # Set socket timeout to check for idle TTL
            server_socket.settimeout(30.0)
        except OSError as e:
            daemon_log.error(f"Failed to bind daemon socket: {e}")
            sys.exit(1)

        daemon_log.info(f"Build Daemon started on UDS: {self.socket_path}")

        self.last_request_time = time.time()

        while True:
            try:
                conn, addr = server_socket.accept()
                self.last_request_time = time.time()
            except socket.timeout:
                idle_duration = time.time() - self.last_request_time
                if idle_duration >= 600.0:
                    daemon_log.info(
                        f"Daemon has been idle for {idle_duration / 60:.1f} minutes. Shutting down due to TTL."
                    )
                    break
                continue
            except KeyboardInterrupt:
                break
            except OSError:
                continue

            try:
                # Read request payload
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    conn.close()
                    continue

                req = cbor2.loads(data)
                command = req.get(RequestField.COMMAND, DaemonCommand.RUN)

                if command == DaemonCommand.STOP:
                    daemon_log.info("Shutdown command received. Stopping daemon.")
                    conn.sendall(b"Daemon stopping...\n")
                    conn.close()
                    break

                if command == DaemonCommand.STATUS:
                    conn.sendall(b"Daemon is running.\n")
                    conn.close()
                    continue

                tool_name = req.get(RequestField.TOOL)
                argv = req.get(RequestField.ARGV, [])

                # Create output stream that forwards to socket
                socket_stream = SocketStream(conn)

                # Dynamically attach a client log handler to stream daemon logs to the client
                client_log_handler = logging.StreamHandler(socket_stream)
                client_log_formatter = logging.Formatter("[%(levelname)s] %(message)s")
                client_log_handler.setFormatter(client_log_formatter)
                daemon_log.addHandler(client_log_handler)

                try:
                    # Run build and redirect output
                    self.reload_modules_if_needed()

                    import importlib

                    # Swap sys.argv and redirect standard streams
                    old_argv = sys.argv
                    sys.argv = [f"{tool_name}.py"] + argv

                    with contextlib.redirect_stdout(socket_stream), contextlib.redirect_stderr(socket_stream):
                        try:
                            # Load tool module and call main
                            module = importlib.import_module(tool_name)
                            main_func = getattr(module, "main")
                            sig = inspect.signature(main_func)

                            if len(sig.parameters) == 0:
                                # view.py main takes no arguments
                                main_func()
                            else:
                                # build.py and config.py main take (logger, args)
                                get_args_func = getattr(module, "get_args")
                                args = get_args_func()

                                from shell import Logger

                                logger = Logger(enabled=True)
                                main_func(logger, args)
                        except Exception as e:
                            import traceback

                            print(f"\nTool {tool_name} failed with error: {e}", file=sys.stderr)
                            traceback.print_exc(file=sys.stderr)
                            daemon_log.exception(f"Tool {tool_name} execution failed")
                        finally:
                            sys.argv = old_argv
                finally:
                    daemon_log.removeHandler(client_log_handler)

            except Exception as e:
                daemon_log.exception("Internal daemon error during request processing")
                try:
                    conn.sendall(f"Internal daemon error: {e}\n".encode("utf-8"))
                except OSError:
                    pass
            finally:
                conn.close()

        server_socket.close()
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass


class DaemonClient:
    """Client wrapper used by build.py, view.py, and config.py."""

    @validate_call(config={"arbitrary_types_allowed": True})
    def __init__(self, socket_path: Path = SOCKET_PATH):
        """Initialize the Daemon Client."""
        self.socket_path = socket_path

    @validate_call(config={"arbitrary_types_allowed": True})
    def run(self, tool_name: str, argv: List[str]):
        """Run the specified tool through the daemon, starting it if necessary."""
        # Handle the --no-daemon override to run synchronously in-process
        if "--no-daemon" in argv:
            argv.remove("--no-daemon")
            self._run_locally(tool_name, argv)
            return

        connected = False
        try:
            with daemon_connection(self.socket_path):
                connected = True
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            pass

        if not connected:
            from shell import Logger

            logger = Logger(text="Starting daemon...", enabled=True)
            logger.print("Build daemon is not running. Starting background daemon...", symbol="🚀")

            self.socket_path.parent.mkdir(parents=True, exist_ok=True)
            daemon_script = Path(__file__).resolve()
            log_file = open(LOG_PATH, "a", encoding="utf-8")
            subprocess.Popen(
                [sys.executable, str(daemon_script), "--start-daemon"],
                stdout=log_file,
                stderr=log_file,
                close_fds=True,
            )

            # Retry loop
            for _ in range(15):
                time.sleep(0.3)
                try:
                    with daemon_connection(self.socket_path):
                        connected = True
                        break
                except (ConnectionRefusedError, FileNotFoundError, OSError):
                    pass

            if not connected:
                logger.print(
                    f"Error: Could not connect to or start build daemon. Check daemon logs at {LOG_PATH}", symbol="❌"
                )
                logger.done()
                sys.exit(1)
            else:
                logger.done()

        # Prepare CBOR request
        req = {
            RequestField.COMMAND: DaemonCommand.RUN,
            RequestField.TOOL: tool_name,
            RequestField.ARGV: argv,
        }
        try:
            with daemon_connection(self.socket_path) as client_socket:
                client_socket.sendall(cbor2.dumps(req))

                # Initialize client-side spinner logger to render progress beautifully
                from shell import Logger
                import importlib

                text = "Building..."
                try:
                    module = importlib.import_module(tool_name)
                    text = getattr(module, "SPINNER_TEXT", "Building...")
                except Exception:
                    pass
                client_logger = Logger(text=text, enabled=True)

                # Receive and stream console output in real-time line-by-line
                buffer = ""
                while True:
                    data = client_socket.recv(BUFFER_SIZE)
                    if not data:
                        break
                    buffer += data.decode("utf-8")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if not line.strip():
                            continue
                        # Skip completion print as client_logger.done() handles it
                        if line.startswith("Done "):
                            continue

                        # Parse symbol and message
                        if len(line) >= 2 and line[1] == " ":
                            symbol = line[0]
                            msg = line[2:]
                        else:
                            symbol = "▶"
                            msg = line
                        client_logger.print(msg, symbol=symbol)

                client_logger.done()
        except KeyboardInterrupt:
            from shell import Logger

            logger = Logger(enabled=True)
            logger.print("Build cancelled by user.", symbol="🛑")
            logger.done()
        except OSError as e:
            from shell import Logger

            logger = Logger(enabled=True)
            logger.print(f"Error communicating with daemon: {e}", symbol="❌")
            logger.print(f"Check daemon logs at {LOG_PATH}", symbol="📋")
            logger.done()
            sys.exit(1)

    @validate_call(config={"arbitrary_types_allowed": True})
    def _run_locally(self, tool_name: str, argv: List[str]):
        """Fallback to in-process execution."""
        import importlib

        old_argv = sys.argv
        sys.argv = [f"{tool_name}.py"] + argv
        try:
            module = importlib.import_module(tool_name)
            main_func = getattr(module, "main")
            sig = inspect.signature(main_func)
            if len(sig.parameters) == 0:
                main_func()
            else:
                get_args_func = getattr(module, "get_args")
                args = get_args_func()
                from shell import Logger

                logger = Logger(enabled=True)
                main_func(logger, args)
        finally:
            sys.argv = old_argv


def main():
    """Parser routing logic."""
    parser = argparse.ArgumentParser(description="Daemon-backed Build Utility.")
    parser.add_argument("--start-daemon", action="store_true", help="Start the build daemon in foreground")
    parser.add_argument("--stop-daemon", action="store_true", help="Stop the running build daemon")
    parser.add_argument("--status", action="store_true", help="Check build daemon status")
    parser.add_argument("--log-path", action="store_true", help="Print the path to the daemon log file")

    args, unknown = parser.parse_known_args()

    if args.start_daemon:
        server = DaemonServer()
        server.run()
    elif args.log_path:
        print(LOG_PATH)
    elif args.stop_daemon:
        try:
            with daemon_connection(SOCKET_PATH) as client_socket:
                client_socket.sendall(cbor2.dumps({RequestField.COMMAND: DaemonCommand.STOP}))
                print(client_socket.recv(BUFFER_SIZE).decode("utf-8"))
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            print("Daemon is not running.")
    elif args.status:
        try:
            with daemon_connection(SOCKET_PATH) as client_socket:
                client_socket.sendall(cbor2.dumps({RequestField.COMMAND: DaemonCommand.STATUS}))
                print(client_socket.recv(BUFFER_SIZE).decode("utf-8"))
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            print("Daemon is not running.")
    else:
        # Default behavior: start daemon and run build
        parser = argparse.ArgumentParser(description="Daemon-backed Build Utility.")
        parser.add_argument(
            "-e",
            "--env",
            required=False,
            default=None,
            help="Output environment to file and exit.",
        )
        parser.add_argument("-out", "--outdir", default="build", help="Target directory for outputs")
        parser.add_argument("targets", nargs="*", help="Specific targets to build.")
        args = parser.parse_args()

        client = DaemonClient()
        # Re-pack arguments to pass to the daemon
        argv = []
        if args.env is not None:
            argv += ["-e", args.env]
        if args.outdir != "build":
            argv += ["-out", args.outdir]
        argv += args.targets

        client.run("build", argv)


if __name__ == "__main__":
    main()
