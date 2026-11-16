"""Smoke tests to verify documented README commands, Scope/Forge HTTP workstations, and JS integrity."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from typing import Any, Dict, Optional, Tuple
import urllib.request

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOCALHOST = "127.0.0.1"
EPHEMERAL_PORT = 0
HTTP_OK = 200
HTTP_TIMEOUT_SECONDS = 30.0
MIN_PCB_PAD_COUNT = 100
MAX_NODE_CONCURRENCY = 8


def _http_get(url: str) -> Tuple[int, Dict[str, str], bytes]:
    """Perform a local HTTP GET request and return ``(status, lower_headers, body)``."""
    req = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return resp.status, headers, resp.read()


class TestSmoke:
    """Executes documented CLI commands, Scope/Forge HTTP endpoints, and JS suites."""

    root_dir = REPO_ROOT
    build_dir: Path

    @pytest.fixture(autouse=True)
    def setup_build_dir(self, tmp_path: Path):
        """Set up a temporary build directory for each test and print its location."""
        self.build_dir = tmp_path / "integration_build"
        self.build_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[INFO] Using temporary build directory: {self.build_dir}")
        yield

    def run_command(self, args: list[str], extra_env: Optional[dict[str, str]] = None):
        """Run a command using the current python interpreter."""
        env = os.environ.copy()
        # Force CPU execution for JAX in smoke tests to bypass MPS compilation/deadlock lag on macOS
        if sys.platform == "darwin":
            env["JAX_PLATFORMS"] = "cpu"
            env["XLA_FLAGS"] = "--xla_cpu_multi_thread_eigen=false"
        if extra_env:
            env.update(extra_env)

        # Automatically redirect build.py output to our temporary directory
        if args and "tools/build.py" in args[0] and "-out" not in args:
            args.extend(["-out", str(self.build_dir)])

        cmd = [sys.executable, *args]
        result = subprocess.run(cmd, cwd=self.root_dir, capture_output=True, text=True, env=env, check=False)
        assert result.returncode == 0, (
            f"Command failed: {' '.join(cmd)}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        return result

    def test_build_commands(self) -> None:
        """Verify build.py commands execute correctly with various options and wildcards."""
        # 1. Verify building all parts and diagrams by default
        self.run_command(["tools/build.py"])
        assert (self.build_dir / "svg/exhaust_manifolds/exhaust_manifolds_diagram.svg").exists()
        assert (self.build_dir / "stl/exhaust_manifolds/driver_left.stl").exists()

        # 2. Verify wildcard building
        self.run_command(["tools/build.py", "cat_fountain/*"])
        assert (self.build_dir / "stl/cat_fountain/bowl.stl").exists()

        # 3. Verify building a specific subassembly and mode via string format
        self.run_command(["tools/build.py", "valve_actuator_limiter/limiter:part/default"])
        assert (self.build_dir / "stl/valve_actuator_limiter/limiter.stl").exists()

        # 4. Verify diagram-only building using the :diagram action suffix
        limiter_stl = self.build_dir / "stl/valve_actuator_limiter/limiter.stl"
        if limiter_stl.exists():
            limiter_stl.unlink()
        self.run_command(["tools/build.py", "valve_actuator_limiter/*:diagram"])
        assert (self.build_dir / "svg/valve_actuator_limiter/valve_actuator_limiter_diagram.svg").exists()
        assert not limiter_stl.exists()

        # 5. Verify diagram options integration via environment variables
        extra_env = {"VALVE_ACTUATOR_LIMITER__DIAGRAM_OPTIONS__SHOW_HIDDEN": "True"}
        self.run_command(["tools/build.py", "valve_actuator_limiter/*:diagram"], extra_env=extra_env)
        assert (self.build_dir / "svg/valve_actuator_limiter/valve_actuator_limiter_diagram.svg").exists()

    def test_config_commands(self) -> None:
        """Verify config.py commands run without error."""
        env_file = self.build_dir / ".test.env"
        self.run_command(["tools/config.py", "-e", str(env_file)])
        self.run_command(["tools/config.py", "exhaust_manifolds/driver", "-e", str(env_file)])
        self.run_command(["tools/config.py", "exhaust_manifolds/driver:config/text", "-e", str(env_file)])

    def test_scope_commands(self) -> None:
        """Verify scope.py workstation CLI commands execute correctly."""
        self.run_command(["tools/scope.py", "--help"])
        self.run_command(["tools/scope.py", "stop"])

    def test_list_commands(self) -> None:
        """Verify list.py commands execute correctly."""
        self.run_command(["tools/list.py", "targets"])
        self.run_command(["tools/list.py", "targets", "exhaust_manifolds/*"])
        self.run_command(["tools/list.py", "outputs"])
        self.run_command(["tools/list.py", "outputs", "exhaust_manifolds/*"])

    def test_scope_workstation_endpoints(self, tmp_path: Path) -> None:
        """Verify ScopeServer serves zero-inline-JS UI, Three.js r184 modules, CAD, PCB, and SIMULATE payloads."""
        from provider.scope.pipeline import ScopeGeometryPipeline
        from provider.scope.server import ScopeServer

        cache_dir = tmp_path / "scope_cache"
        fb_dir = tmp_path / "feedback"
        att_dir = tmp_path / "attachments"
        fb_dir.mkdir(parents=True, exist_ok=True)
        att_dir.mkdir(parents=True, exist_ok=True)

        pipeline = ScopeGeometryPipeline(cache_dir=cache_dir)
        server = ScopeServer(
            host=LOCALHOST,
            port=EPHEMERAL_PORT,
            repo_root=self.root_dir,
            pipeline=pipeline,
            sqlite_file=tmp_path / "bugs.sqlite",
            attachments_dir=att_dir,
            feedback_dir=fb_dir,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://{LOCALHOST}:{server.actual_port}"

        try:
            status, _, ui_bytes = _http_get(f"{base_url}/?project=carrier_board&target=carrier_board&mode=PCB")
            assert status == HTTP_OK
            ui_html = ui_bytes.decode("utf-8")
            assert 'id="app-boot-config"' in ui_html
            assert "/js/scope/main.js" in ui_html
            assert "three-cad-viewer" not in ui_html
            assert "onclick=" not in ui_html

            js_status, js_headers, js_bytes = _http_get(f"{base_url}/js/scope/main.js")
            assert js_status == HTTP_OK
            assert "javascript" in js_headers.get("content-type", "")
            assert b"getRuntimeContext" in js_bytes

            three_status, _, three_bytes = _http_get(f"{base_url}/static/vendor/three/three.module.js")
            assert three_status == HTTP_OK
            assert b"WebGLRenderer" in three_bytes

            proj_status, _, proj_bytes = _http_get(f"{base_url}/api/scope/projects")
            assert proj_status == HTTP_OK
            projects_payload: Dict[str, Any] = json.loads(proj_bytes.decode("utf-8"))
            assert len(projects_payload.get("projects", [])) > 0

            cad_status, _, cad_bytes = _http_get(f"{base_url}/api/scope/load?project=cat_fountain&target=bowl&mode=CAD")
            assert cad_status == HTTP_OK
            cad_payload: Dict[str, Any] = json.loads(cad_bytes.decode("utf-8"))
            assert cad_payload["type"] == "data"
            assert len(cad_payload["shapes"]["parts"]) >= 1

            pcb_status, _, pcb_bytes = _http_get(
                f"{base_url}/api/scope/load?project=carrier_board&target=carrier_board&mode=PCB"
            )
            assert pcb_status == HTTP_OK
            pcb_payload: Dict[str, Any] = json.loads(pcb_bytes.decode("utf-8"))
            assert len(pcb_payload["shapes"]["parts"]) == 1
            pcb_meta = pcb_payload["pcb_metadata"]
            assert pcb_meta["render_version"] == ScopeGeometryPipeline.PCB_METADATA_RENDER_VERSION
            assert len(pcb_meta["pads"]) >= MIN_PCB_PAD_COUNT

            sim_status, _, sim_bytes = _http_get(
                f"{base_url}/api/scope/load?project=cat_fountain&target=product&mode=SIMULATE"
            )
            assert sim_status == HTTP_OK
            sim_payload: Dict[str, Any] = json.loads(sim_bytes.decode("utf-8"))
            assert sim_payload["mode"] == "SIMULATE"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5.0)

    def test_forge_dashboard_and_js_diff_endpoints(self, tmp_path: Path) -> None:
        """Verify forge.py CLI, DashboardServer UI routes, and zero-exclusion JS diff/raw inspection."""
        from provider.dashboard.server import DashboardServer

        self.run_command(["tools/forge.py", "--help"])
        self.run_command(["tools/forge.py", "list-commits"])

        fb_dir = tmp_path / "feedback"
        fb_dir.mkdir(parents=True, exist_ok=True)
        server = DashboardServer(
            host=LOCALHOST,
            port=EPHEMERAL_PORT,
            repo_root=self.root_dir,
            sqlite_bug_file=tmp_path / "bugs.sqlite",
            sqlite_review_file=tmp_path / "code_review.sqlite",
            markdown_bugs_path=fb_dir / "BUGS.md",
            markdown_review_path=fb_dir / "CR.md",
            feedback_dir=fb_dir,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = server.get_url()

        try:
            for route in ("/", "/review", "/bugs"):
                st, _, body = _http_get(f"{base_url}{route}")
                assert st == HTTP_OK
                html = body.decode("utf-8")
                assert 'id="app-boot-config"' in html
                assert "onclick=" not in html

            rt_status, _, rt_bytes = _http_get(f"{base_url}/js/core/runtime_context.js")
            assert rt_status == HTTP_OK
            assert b"getRuntimeContext" in rt_bytes

            for js_rel in (
                "js/scope/main.js",
                "js/static/vendor/three/addons/controls/OrbitControls.js",
                "js/static/vendor/three/three.module.js",
            ):
                diff_status, _, diff_bytes = _http_get(f"{base_url}/api/diff?commit=working&file={js_rel}")
                assert diff_status == HTTP_OK
                diff_json: Dict[str, Any] = json.loads(diff_bytes.decode("utf-8"))
                assert diff_json["file_path"] == js_rel

                raw_status, _, raw_bytes = _http_get(f"{base_url}/api/raw?commit=working&file={js_rel}")
                assert raw_status == HTTP_OK
                assert len(raw_bytes) > 0
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5.0)

    def test_javascript_validation_and_parallel_unit_tests(self) -> None:
        """Verify validate_js.py and parallel Node ES module unit tests pass 100%."""
        self.run_command(["tools/validate_js.py"])

        node_bin = shutil.which("node")
        assert node_bin is not None, "node executable must be installed in environment"
        test_files = sorted(str(p) for p in (self.root_dir / "tests" / "js").glob("*.test.mjs"))
        assert len(test_files) > 0
        workers = min(os.cpu_count() or 4, MAX_NODE_CONCURRENCY)
        cmd = [node_bin, "--test", f"--test-concurrency={workers}", *test_files]
        res = subprocess.run(cmd, cwd=self.root_dir, capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"Node unit tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-s", "-v", "-n", "0"]))
