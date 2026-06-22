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

    def test_build_commands(self):
        """Verify build.py commands execute correctly with various options and wildcards."""
        # 1. Verify building all parts and diagrams by default
        self.run_command(["src/build.py"])
        assert (self.build_dir / "exhaust_manifolds" / "exhaust_manifolds_diagram.svg").exists()
        assert (self.build_dir / "exhaust_manifolds" / "driver_left.stl").exists()

        # 2. Verify wildcard building
        self.run_command(["src/build.py", "cat_fountain/*"])
        assert (self.build_dir / "cat_fountain" / "bowl.stl").exists()

        # 3. Verify building a specific subassembly and mode via string format
        self.run_command(["src/build.py", "valve_actuator_limiter/limiter:part/default"])
        assert (self.build_dir / "valve_actuator_limiter" / "limiter.stl").exists()

        # 4. Verify diagram-only building using the :diagram action suffix
        limiter_stl = self.build_dir / "valve_actuator_limiter" / "limiter.stl"
        if limiter_stl.exists():
            limiter_stl.unlink()
        self.run_command(["src/build.py", "valve_actuator_limiter/*:diagram"])
        assert (self.build_dir / "valve_actuator_limiter" / "valve_actuator_limiter_diagram.svg").exists()
        assert not limiter_stl.exists()

        # 5. Verify diagram options integration via environment variables
        extra_env = {"VALVE_ACTUATOR_LIMITER__DIAGRAM_OPTIONS__SHOW_HIDDEN": "True"}
        self.run_command(["src/build.py", "valve_actuator_limiter/*:diagram"], extra_env=extra_env)
        assert (self.build_dir / "valve_actuator_limiter" / "valve_actuator_limiter_diagram.svg").exists()

    def test_config_commands(self):
        """Verify config.py commands run without error."""
        # Use a temporary env file to avoid source pollution
        env_file = self.build_dir / ".test.env"
        self.run_command(["src/config.py", "-e", str(env_file)])
        self.run_command(["src/config.py", "exhaust_manifolds/driver", "-e", str(env_file)])
        self.run_command(["src/config.py", "exhaust_manifolds/driver:config/text", "-e", str(env_file)])

    def test_view_commands(self):
        """Verify view.py commands execute correctly."""
        # Check target listing
        self.run_command(["src/view.py", "--list", "--no-gui"])

        # Check target visualization (Note: ocp_vscode may warn if no listener is active, but should return 0)
        self.run_command(["src/view.py", "valve_actuator_limiter/limiter", "--no-gui"])
        self.run_command(["src/view.py", "valve_actuator_limiter/*:part/default", "--no-gui"])

        # Check simulation mode
        self.run_command(
            [
                "src/view.py",
                "cat_fountain/product:view/simulate",
                "--build-dir",
                str(self.build_dir),
                "-s",
                "1",
                "--no-gui",
            ]
        )

    def test_list_commands(self):
        """Verify list.py commands execute correctly."""
        # Check target listing
        self.run_command(["src/list.py", "targets"])
        self.run_command(["src/list.py", "targets", "exhaust_manifolds/*"])

        # Check outputs listing
        self.run_command(["src/list.py", "outputs"])
        self.run_command(["src/list.py", "outputs", "exhaust_manifolds/*"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-s", "-v"]))
