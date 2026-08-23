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


class CLICommand(StrEnum):
    """Subcommands for the daemon management CLI."""

    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"
    LOG_PATH = "log-path"


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
PID_PATH = Path(__file__).parent.parent / "build" / ".daemon.pid"


def is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is running on the local system."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


BUFFER_SIZE = 8192
RELOAD_PREFIXES = (
    "projects",
    "projects_config",
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
EXIT_CODE_TOKEN = "__DAEMON_EXIT_CODE__"


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


class ClientLogFormatter(logging.Formatter):
    """Formats daemon logs for client streaming with appropriate symbols."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the record with symbols."""
        if record.levelno >= logging.ERROR:
            symbol = "❌"
        elif record.levelno >= logging.WARNING:
            symbol = "⚠️"
        else:
            symbol = "▶"
        return f"{symbol} {record.getMessage()}"


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

    # Route root logger to the daemon file handler
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


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

    def isatty(self) -> bool:
        """Return False as socket is not a TTY."""
        return False

    def close(self):
        """No-op close to prevent AttributeError during stream teardown."""
        pass


class DaemonServer:
    """Persistent server keeping providers and @method_cache in memory."""

    @validate_call(config={"arbitrary_types_allowed": True})
    def __init__(self, socket_path: Path = SOCKET_PATH):
        """Initialize the Daemon Server."""
        self.socket_path = socket_path
        self.pid_path = self.socket_path.with_suffix(".pid")
        self.last_load_time = 0.0
        self.manager: Optional[Any] = None
        self.socket_timeout = 30.0
        self.ttl_duration = 600.0
        self.testing = "pytest" in sys.modules

    @validate_call(config={"arbitrary_types_allowed": True})
    def reload_modules_if_needed(self):
        """Unload and reload modified modules to pick up code changes."""
        if self.testing:
            if self.manager is None:
                from model import AppConfig
                from provider import ProviderManager

                config = AppConfig()
                self.manager = ProviderManager(config, bootstrap=True)
            return

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

        # Also monitor any environment files (ending with .env) in the repository root (parent of src)
        repo_root = src_dir.parent
        if repo_root.exists():
            for file in os.listdir(repo_root):
                if file.endswith(".env") or file == ".env":
                    try:
                        mtime = (repo_root / file).stat().st_mtime
                        if mtime > max_mtime:
                            max_mtime = mtime
                    except Exception:
                        pass

        # If any files were modified since last load time, reload modules
        if max_mtime > self.last_load_time or self.manager is None:
            modules_to_unload = []
            for name in list(sys.modules.keys()):
                if name == __name__:
                    continue
                for prefix in RELOAD_PREFIXES:
                    if prefix.endswith("."):
                        if name.startswith(prefix):
                            modules_to_unload.append(name)
                            break
                    else:
                        if name == prefix or name.startswith(prefix + "."):
                            modules_to_unload.append(name)
                            break

            for mod in modules_to_unload:
                sys.modules.pop(mod, None)

            # Re-import dependencies
            from model import AppConfig
            from provider import ProviderManager

            config = AppConfig()
            self.manager = ProviderManager(config, bootstrap=True)
            self.last_load_time = time.time()
            daemon_log.info(f"Core modules reloaded successfully. Unloaded: {', '.join(modules_to_unload)}")

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

        # Configure JAX and fluid simulation logs to go to the daemon log file
        try:
            from provider import DAEMON_LOGGERS

            for name in DAEMON_LOGGERS:
                l = logging.getLogger(name)
                l.addHandler(handler)
                l.setLevel(logging.INFO)
        except Exception as e:
            daemon_log.warning(f"Could not configure daemon loggers: {e}")

        server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server_socket.bind(str(self.socket_path))
            # Restrict socket permissions so only the owner can read/write to it
            os.chmod(str(self.socket_path), 0o600)
            server_socket.listen(5)
            # Set socket timeout to check for idle TTL
            server_socket.settimeout(self.socket_timeout)
            self.socket_inode = self.socket_path.stat().st_ino
            # Write daemon PID to file to detect if alive but busy
            self.pid_path.write_text(str(os.getpid()))
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
                try:
                    if not self.socket_path.exists() or self.socket_path.stat().st_ino != self.socket_inode:
                        daemon_log.info("Socket file replaced or removed. Shutting down daemon.")
                        break
                except OSError:
                    daemon_log.info("Socket file inaccessible. Shutting down daemon.")
                    break
                idle_duration = time.time() - self.last_request_time
                if idle_duration >= self.ttl_duration:
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
                if not isinstance(req, dict):
                    raise ValueError(f"Request payload must be a dictionary, got {type(req).__name__}")
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
                if not isinstance(tool_name, str):
                    raise ValueError("Request field 'tool' must be a string.")
                argv = req.get(RequestField.ARGV, [])
                if not isinstance(argv, list):
                    raise ValueError("Request field 'argv' must be a list.")

                # Create output stream that forwards to socket
                socket_stream = SocketStream(conn)
                exit_code = 1

                # Dynamically attach a client log handler to stream daemon logs to the client
                client_log_handler = logging.StreamHandler(socket_stream)
                client_log_formatter = ClientLogFormatter()
                client_log_handler.setFormatter(client_log_formatter)
                client_log_handler.setLevel(logging.WARNING)
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
                            exit_code = 0
                        except SystemExit as e:
                            exit_code = e.code if e.code is not None else 0
                            # Gracefully handle normal or error tool exits without crashing daemon
                            if exit_code != 0:
                                print(f"\nTool {tool_name} exited with status code: {exit_code}", file=sys.stderr)
                                daemon_log.warning(f"Tool {tool_name} exited with status code: {exit_code}")
                        except Exception as e:
                            import traceback

                            print(f"\nTool {tool_name} failed with error: {e}", file=sys.stderr)
                            traceback.print_exc(file=sys.stderr)
                            daemon_log.exception(f"Tool {tool_name} execution failed")
                            exit_code = 1
                        finally:
                            sys.argv = old_argv
                            try:
                                conn.sendall(f"\n{EXIT_CODE_TOKEN}:{exit_code}\n".encode("utf-8"))
                            except OSError:
                                pass
                finally:
                    daemon_log.removeHandler(client_log_handler)

            except Exception as e:
                daemon_log.exception("Invalid request or internal error. Shutting down daemon to prevent stale state.")
                try:
                    conn.sendall(f"Internal daemon error: {e}\n".encode("utf-8"))
                except OSError:
                    pass
                conn.close()
                break
            else:
                conn.close()

        server_socket.close()
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
        if self.pid_path.exists():
            try:
                self.pid_path.unlink()
            except OSError:
                pass


class DaemonClient:
    """Client wrapper used by build.py, view.py, and config.py."""

    @validate_call(config={"arbitrary_types_allowed": True})
    def __init__(self, socket_path: Path = SOCKET_PATH):
        """Initialize the Daemon Client."""
        self.socket_path = socket_path
        self.pid_path = self.socket_path.with_suffix(".pid")

    @validate_call(config={"arbitrary_types_allowed": True})
    def start_daemon(self, print_msg: bool = False) -> bool:
        """Start the background daemon process and wait for it to start listening."""
        logger = None
        if print_msg:
            from shell import Logger

            logger = Logger(text="Starting daemon...", enabled=True)
            logger.print("Build daemon is not running. Starting background daemon...", symbol="🚀")

        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        daemon_script = Path(__file__).resolve()
        log_file = open(LOG_PATH, "a", encoding="utf-8")
        subprocess.Popen(
            [sys.executable, str(daemon_script), "start", "--foreground"],
            stdout=log_file,
            stderr=log_file,
            close_fds=True,
        )

        for _ in range(15):
            try:
                with daemon_connection(self.socket_path):
                    if print_msg and logger:
                        logger.done()
                    return True
            except (ConnectionRefusedError, FileNotFoundError, OSError):
                time.sleep(0.1)

        if print_msg and logger:
            logger.done()
        return False

    @property
    def running(self) -> bool:
        """Check if the daemon is currently running."""
        try:
            with daemon_connection(self.socket_path):
                return True
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return False

    @validate_call(config={"arbitrary_types_allowed": True})
    def stop_daemon(self) -> bool:
        """Stop the running background daemon and wait for it to exit cleanly."""
        try:
            with daemon_connection(self.socket_path) as client_socket:
                client_socket.sendall(cbor2.dumps({RequestField.COMMAND: DaemonCommand.STOP}))
                client_socket.recv(BUFFER_SIZE)
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return True

        for _ in range(15):
            try:
                with daemon_connection(self.socket_path):
                    time.sleep(0.1)
            except (ConnectionRefusedError, FileNotFoundError, OSError):
                return True
        return False

    @validate_call(config={"arbitrary_types_allowed": True})
    def restart_daemon(self) -> bool:
        """Stop and restart the background daemon."""
        self.stop_daemon()
        return self.start_daemon(print_msg=False)

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

        # If connection failed, check if the daemon is actually running but busy
        if not connected and self.pid_path.exists():
            try:
                pid = int(self.pid_path.read_text().strip())
                if is_pid_alive(pid):
                    # Loop and wait for the busy daemon to become free
                    start_time = time.time()
                    while time.time() - start_time < 300:  # up to 5 minutes
                        try:
                            with daemon_connection(self.socket_path):
                                connected = True
                                break
                        except (ConnectionRefusedError, OSError):
                            if not is_pid_alive(pid):
                                break
                            time.sleep(0.5)
            except (ValueError, OSError):
                pass

        if not connected:
            if not self.start_daemon():
                from shell import Logger

                logger = Logger(enabled=True)
                logger.print(
                    f"Error: Could not connect to or start build daemon. Check daemon logs at {LOG_PATH}", symbol="❌"
                )
                logger.done()
                sys.exit(1)

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
                    text = getattr(module, "SPINNER_TEXT", text)
                except Exception:
                    pass
                client_logger = Logger(text=text, enabled=True)

                # Receive and stream console output in real-time line-by-line
                buffer = ""
                exit_code = 0
                while True:
                    data = client_socket.recv(BUFFER_SIZE)
                    if not data:
                        break
                    buffer += data.decode("utf-8")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if not line.strip():
                            continue
                        # Check for exit code token
                        if line.startswith(f"{EXIT_CODE_TOKEN}:"):
                            try:
                                exit_code = int(line.split(f"{EXIT_CODE_TOKEN}:", 1)[1])
                            except ValueError:
                                exit_code = 1
                            continue
                        # Skip completion print as client_logger.done() handles it
                        if line.startswith("Done "):
                            continue

                        # Parse symbol and message by splitting on the first space
                        parts = line.split(" ", 1)
                        is_symbol = False
                        if len(parts) == 2 and parts[0]:
                            first_word = parts[0].strip()
                            # Check if the first word behaves like a symbol (short and non-alphanumeric/emoji)
                            if len(first_word) <= 3 and not any(c.isalnum() for c in first_word):
                                is_symbol = True

                        if is_symbol:
                            symbol = parts[0].strip()
                            msg = parts[1].strip()
                        else:
                            symbol = "▶"
                            msg = line
                        client_logger.print(msg, symbol=symbol)

                client_logger.done()
                if exit_code != 0:
                    sys.exit(exit_code)
        except KeyboardInterrupt:
            sys.exit(130)
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
    daemon_cmds = {c.value for c in CLICommand}

    # Use argparse subparsers if a subcommand or help is requested
    if len(sys.argv) > 1 and (sys.argv[1] in daemon_cmds or sys.argv[1] in ("-h", "--help")):
        parser = argparse.ArgumentParser(description="Daemon management utility.")
        subparsers = parser.add_subparsers(dest="command", required=True, help="Daemon commands")
        start_parser = subparsers.add_parser(CLICommand.START.value, help="Start the build daemon")
        start_parser.add_argument("--foreground", action="store_true", help="Run daemon in the foreground")
        subparsers.add_parser(CLICommand.STOP.value, help="Stop the running build daemon")
        subparsers.add_parser(CLICommand.RESTART.value, help="Restart the running build daemon")
        subparsers.add_parser(CLICommand.STATUS.value, help="Check build daemon status")
        subparsers.add_parser(CLICommand.LOG_PATH.value, help="Print the path to the daemon log file")

        args = parser.parse_args()

        if args.command == CLICommand.START.value:
            if args.foreground:
                server = DaemonServer()
                server.run()
            else:
                client = DaemonClient()
                if client.running:
                    print("Daemon is already running.")
                else:
                    if client.start_daemon(print_msg=True):
                        print("Daemon started successfully in background.")
                    else:
                        print("Failed to start daemon.")
        elif args.command == CLICommand.LOG_PATH.value:
            print(LOG_PATH)
        elif args.command == CLICommand.RESTART.value:
            client = DaemonClient()
            print("Stopping daemon...")
            if client.restart_daemon():
                print("Daemon restarted successfully.")
            else:
                print("Failed to restart daemon.")
        elif args.command == CLICommand.STOP.value:
            client = DaemonClient()
            if client.stop_daemon():
                print("Daemon stopped successfully.")
            else:
                print("Failed to stop daemon.")
        elif args.command == CLICommand.STATUS.value:
            try:
                with daemon_connection(SOCKET_PATH) as client_socket:
                    client_socket.sendall(cbor2.dumps({RequestField.COMMAND: DaemonCommand.STATUS}))
                    print(client_socket.recv(BUFFER_SIZE).decode("utf-8"))
            except (ConnectionRefusedError, FileNotFoundError, OSError):
                print("Daemon is not running.")
        sys.exit(0)
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
