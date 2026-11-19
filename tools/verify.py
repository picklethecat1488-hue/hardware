#!/usr/bin/env python3
"""Automated pre-commit verification suite for the hardware repository.

Executes in order:
  1. Python syntax compilation check (`python -m compileall -q .`)
  2. Ruff code formatting check      (`ruff format --check .` or `--fix`)
  3. Ruff lint rules check           (`ruff check .` or `--fix`)
  4. JS zero-globals & template lint (`python tools/validate_js.py`)
  5. Parallel JS ES module tests     (`node --test tests/js/*.test.mjs`)
  6. Parallel Python test suite      (`pytest`)
  7. Optional smoke test suite       (`python tools/smoke.py` when `--smoke` is passed)
"""

import glob
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

TARGET_NOFILE_LIMIT: int = 65536
MAX_PARALLEL_WORKERS: int = 4

USAGE_TEXT: str = """Usage: ./tools/verify.py [options] [--] [pytest_args...]

Automated pre-commit verification for the hardware repository:
  1. Python syntax compilation check (python -m compileall -q .)
  2. Ruff code formatting check      (ruff format --check .)
  3. Ruff lint rules check           (ruff check .)
  4. JS zero-globals & template lint (python tools/validate_js.py)
  5. Parallel JS ES module tests     (node --test tests/js/*.test.mjs)
  6. Parallel Python test suite      (pytest)

Options:
  --fix              Auto-format and auto-fix Ruff lint issues before checking
  --quick, --no-pytest
                     Run fast static & JS checks (steps 1-5) and skip pytest
  --slow             Include @pytest.mark.slow 3D CAD & physics simulation tests
  --smoke            Also run integration smoke tests (python tools/smoke.py)
  -h, --help         Show this help message and exit

Any additional arguments are forwarded directly to pytest (e.g. -k test_pcb)."""


def raise_nofile_limit() -> None:
    """Raise open file descriptor soft limit toward `TARGET_NOFILE_LIMIT` when supported."""
    if os.name != "posix":
        return
    import resource

    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        desired = min(TARGET_NOFILE_LIMIT, hard) if hard != resource.RLIM_INFINITY else TARGET_NOFILE_LIMIT
        if soft < desired:
            resource.setrlimit(resource.RLIMIT_NOFILE, (desired, hard))
    except (OSError, ValueError):
        pass


def build_verification_env() -> Dict[str, str]:
    """Build verification environment dictionary inheriting the active conda environment."""
    env = dict(os.environ)
    existing_py_path = env.get("PYTHONPATH", "")
    py_parts = [".", "tools"] + ([existing_py_path] if existing_py_path else [])
    env["PYTHONPATH"] = os.pathsep.join(py_parts)
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    env["NUMEXPR_NUM_THREADS"] = "1"
    env["XLA_FLAGS"] = "--xla_cpu_multi_thread_eigen=false"
    return env


def run_step(cmd: Sequence[str], *, cwd: Path, env: Dict[str, str]) -> None:
    """Run a verification command synchronously and exit immediately on non-zero status."""
    proc = subprocess.run(list(cmd), cwd=str(cwd), env=env, check=False)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def parse_cli_args(argv: Sequence[str]) -> Tuple[bool, bool, bool, bool, List[str]]:
    """Parse `./tools/verify.py` flags and collect passthrough `pytest` arguments."""
    fix_mode = False
    quick_mode = False
    run_slow = False
    run_smoke = False
    pytest_args: List[str] = []

    idx = 0
    tokens = list(argv)
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--fix":
            fix_mode = True
        elif tok in ("--quick", "--no-pytest"):
            quick_mode = True
        elif tok == "--slow":
            run_slow = True
        elif tok == "--smoke":
            run_smoke = True
        elif tok in ("-h", "--help"):
            print(USAGE_TEXT)
            sys.exit(0)
        elif tok == "--":
            pytest_args.extend(tokens[idx + 1 :])
            break
        else:
            pytest_args.append(tok)
        idx += 1

    return fix_mode, quick_mode, run_slow, run_smoke, pytest_args


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Execute hardware repository pre-commit verification pipeline."""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    fix_mode, quick_mode, run_slow, run_smoke, pytest_args = parse_cli_args(raw_argv)

    start_time = time.monotonic()
    repo_root = Path(__file__).resolve().parent.parent
    raise_nofile_limit()
    env = build_verification_env()
    python_exe = sys.executable

    total_steps = 5 + (0 if quick_mode else 1) + (1 if run_smoke else 0)
    step = 1

    print(f"🔍 [{step}/{total_steps}] Checking Python compilation syntax...")
    run_step([python_exe, "-m", "compileall", "-q", "."], cwd=repo_root, env=env)
    step += 1

    if fix_mode:
        print(f"🎨 [{step}/{total_steps}] Formatting Python code with Ruff...")
        run_step(["ruff", "format", "."], cwd=repo_root, env=env)
        step += 1

        print(f"🧹 [{step}/{total_steps}] Auto-fixing & checking Ruff lint rules...")
        run_step(["ruff", "check", "--fix", "."], cwd=repo_root, env=env)
        run_step(["ruff", "format", "--check", "."], cwd=repo_root, env=env)
        step += 1
    else:
        print(f"🎨 [{step}/{total_steps}] Checking code formatting...")
        run_step(["ruff", "format", "--check", "."], cwd=repo_root, env=env)
        step += 1

        print(f"🧹 [{step}/{total_steps}] Checking linting rules...")
        run_step(["ruff", "check", "."], cwd=repo_root, env=env)
        step += 1

    print(f"⚡ [{step}/{total_steps}] Checking JavaScript compilation & zero-globals lint rules...")
    run_step([python_exe, "tools/validate_js.py"], cwd=repo_root, env=env)
    step += 1

    cpu_count = os.cpu_count() or 4
    workers = min(cpu_count, MAX_PARALLEL_WORKERS)

    js_tests = sorted(glob.glob(str(repo_root / "tests" / "js" / "*.test.mjs")))
    print(f"🧩 [{step}/{total_steps}] Running parallel JavaScript unit tests...")
    if js_tests:
        run_step(["node", "--test", f"--test-concurrency={workers}", *js_tests], cwd=repo_root, env=env)
    step += 1

    if not quick_mode:
        final_pytest_args: List[str] = [python_exe, "-m", "pytest"]
        joined = f" {' '.join(pytest_args)} "
        if " -n " not in joined and " -n=" not in joined and " --numprocesses" not in joined:
            final_pytest_args.extend(["-n", str(workers)])
        if run_slow:
            if " -m " not in joined and " -m=" not in joined:
                final_pytest_args.extend(["-m", "slow or not slow"])
            print(f"🧪 [{step}/{total_steps}] Running full Python test suite (including @pytest.mark.slow)...")
        else:
            print(f"🧪 [{step}/{total_steps}] Running fast Python test suite (excluding slow CAD/physics)...")
        final_pytest_args.extend(pytest_args)
        run_step(final_pytest_args, cwd=repo_root, env=env)
        step += 1

    if run_smoke:
        print(f"🔥 [{step}/{total_steps}] Running integration smoke test suite...")
        run_step([python_exe, "tools/smoke.py"], cwd=repo_root, env=env)

    elapsed = int(time.monotonic() - start_time)
    print(f"✅ Pre-commit verification PASSED in {elapsed}s")
    print(f"Verification PASSED in {elapsed}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
