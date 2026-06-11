"""Smoke tests to verify documented README commands and CLI integrity."""

import os
import subprocess
import sys
import shutil
from typing import Optional
import pytest
from pathlib import Path


class TestSmoke:
    """Executes documented CLI commands and verifies outputs."""

    root_dir = Path(__file__).parent.parent
    build_dir: Path

    @pytest.fixture(autouse=True)
    def setup_build_dir(self, tmp_path):
        """Set up a temporary build directory for each test and print its location."""
        self.build_dir = tmp_path / "integration_build"
        self.build_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[INFO] Using temporary build directory: {self.build_dir}")
        yield

    def run_command(self, args: list[str], extra_env: Optional[dict[str, str]] = None):
        """Run a command using the current python interpreter."""
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        # Automatically redirect build.py output to our temporary directory
        if args and "src/build.py" in args[0] and "-out" not in args:
            args.extend(["-out", str(self.build_dir)])

        cmd = [sys.executable] + args
        result = subprocess.run(cmd, cwd=self.root_dir, capture_output=True, text=True, env=env)
        assert result.returncode == 0, (
            f"Command failed: {' '.join(cmd)}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        return result

    def test_build_all(self):
        """Verify build.py produces both diagrams and parts by default."""
        self.run_command(["src/build.py"])
        assert (self.build_dir / "exhaust_manifolds" / "exhaust_manifolds_diagram.svg").exists()
        assert (self.build_dir / "exhaust_manifolds" / "driver_left.stl").exists()

    def test_build_wildcard(self):
        """Verify building specific projects with wildcards."""
        self.run_command(["src/build.py", "exhaust_manifolds/*"])
        assert (self.build_dir / "exhaust_manifolds" / "driver_left.stl").exists()

    def test_build_fully_qualified_target(self):
        """Verify building a specific subassembly and mode via string format."""
        self.run_command(["src/build.py", "exhaust_manifolds/driver_left:part/print"])
        assert (self.build_dir / "exhaust_manifolds" / "driver_left.stl").exists()

    def test_build_diagram_only(self):
        """Verify diagram-only building with the -pno flag."""
        self.run_command(["src/build.py", "--parts=false", "exhaust_manifolds/*"])
        assert (self.build_dir / "exhaust_manifolds" / "exhaust_manifolds_diagram.svg").exists()
        assert not (self.build_dir / "exhaust_manifolds" / "driver_left.stl").exists()

    def test_diagram_options_integration(self):
        """Verify diagram options like show_hidden work via environment variables."""
        extra_env = {"VALVE_ACTUATOR_LIMITER__DIAGRAM_OPTIONS__SHOW_HIDDEN": "True"}
        self.run_command(["src/build.py", "valve_actuator_limiter/*", "-pno"], extra_env=extra_env)

        diag_path = self.build_dir / "valve_actuator_limiter" / "valve_actuator_limiter_diagram.svg"
        assert diag_path.exists()

    def test_config_commands(self):
        """Verify config.py commands run without error."""
        # Use a temporary env file to avoid source pollution
        env_file = self.build_dir / ".test.env"
        self.run_command(["src/config.py", "-e", str(env_file)])
        self.run_command(["src/config.py", "exhaust_manifolds/driver", "-e", str(env_file)])
        self.run_command(["src/config.py", "exhaust_manifolds/driver:config/text", "-e", str(env_file)])

    def test_view_commands(self):
        """Verify view.py commands execute correctly."""
        env = {"SMOKE_TEST": "1"}

        # Check target listing
        self.run_command(["src/view.py", "--list"], extra_env=env)

        # Check target visualization (Note: ocp_vscode may warn if no listener is active, but should return 0)
        self.run_command(["src/view.py", "exhaust_manifolds/driver"], extra_env=env)
        self.run_command(["src/view.py", "exhaust_manifolds/wire"], extra_env=env)
        self.run_command(["src/view.py", "exhaust_manifolds/*:part/print"], extra_env=env)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-s", "-v"]))
