#!/usr/bin/env bash
# Automated pre-commit verification suite for the hardware repository.
#
# Runs Python syntax compilation, Ruff formatting & linting, JavaScript
# compilation/zero-globals/template linting, parallel Node ES module unit tests,
# and the parallel pytest suite.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

FIX_MODE=0
QUICK_MODE=0
RUN_SLOW=0
RUN_SMOKE=0
PYTEST_ARGS=()

print_usage() {
    cat <<'EOF'
Usage: ./tools/verify.sh [options] [--] [pytest_args...]

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

Any additional arguments are forwarded directly to pytest (e.g. -k test_pcb).
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fix)
            FIX_MODE=1
            shift
            ;;
        --quick|--no-pytest)
            QUICK_MODE=1
            shift
            ;;
        --slow)
            RUN_SLOW=1
            shift
            ;;
        --smoke)
            RUN_SMOKE=1
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        --)
            shift
            PYTEST_ARGS+=("$@")
            break
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

START_TIME=$(date +%s)

# Raise open file descriptor limit if possible
ulimit -n 65536 2>/dev/null || true

# Resolve cq conda environment if not already active in PATH
if [[ "${CONDA_DEFAULT_ENV:-}" != "cq" ]]; then
    for candidate_bin in \
        "/workspace/miniforge3/envs/cq/bin" \
        "${HOME}/miniforge3/envs/cq/bin" \
        "${HOME}/mambaforge/envs/cq/bin" \
        "${HOME}/miniconda3/envs/cq/bin" \
        "${HOME}/anaconda3/envs/cq/bin" \
        "/opt/homebrew/Caskroom/miniforge/base/envs/cq/bin" \
        "/opt/homebrew/Caskroom/miniconda/base/envs/cq/bin" \
        "/usr/local/Caskroom/miniforge/base/envs/cq/bin" \
        "/home/ubuntu/miniforge3/envs/cq/bin" \
        "/root/miniforge3/envs/cq/bin"; do
        if [[ -d "${candidate_bin}" ]]; then
            export PATH="${candidate_bin}:${PATH}"
            break
        fi
    done
fi

export PYTHONPATH=".:tools:${PYTHONPATH:-}"
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=false"

TOTAL_STEPS=$((5 + (1 - QUICK_MODE) + RUN_SMOKE))
STEP=1

echo "🔍 [${STEP}/${TOTAL_STEPS}] Checking Python compilation syntax..."
python -m compileall -q .
STEP=$((STEP + 1))

if [[ "${FIX_MODE}" -eq 1 ]]; then
    echo "🎨 [${STEP}/${TOTAL_STEPS}] Formatting Python code with Ruff..."
    ruff format .
    STEP=$((STEP + 1))

    echo "🧹 [${STEP}/${TOTAL_STEPS}] Auto-fixing & checking Ruff lint rules..."
    ruff check --fix .
    ruff format --check .
    STEP=$((STEP + 1))
else
    echo "🎨 [${STEP}/${TOTAL_STEPS}] Checking code formatting..."
    ruff format --check .
    STEP=$((STEP + 1))

    echo "🧹 [${STEP}/${TOTAL_STEPS}] Checking linting rules..."
    ruff check .
    STEP=$((STEP + 1))
fi

echo "⚡ [${STEP}/${TOTAL_STEPS}] Checking JavaScript compilation & zero-globals lint rules..."
python tools/validate_js.py
STEP=$((STEP + 1))

NUM_CPUS=$(OMP_NUM_THREADS= nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
if [[ "${NUM_CPUS}" -gt 4 ]]; then
    PYTEST_WORKERS=4
else
    PYTEST_WORKERS="${NUM_CPUS}"
fi

echo "🧩 [${STEP}/${TOTAL_STEPS}] Running parallel JavaScript unit tests..."
node --test --test-concurrency="${PYTEST_WORKERS}" tests/js/*.test.mjs
STEP=$((STEP + 1))

if [[ "${QUICK_MODE}" -eq 0 ]]; then
    FINAL_PYTEST_ARGS=()
    PYTEST_JOINED=" ${PYTEST_ARGS[*]:-} "
    if [[ "${PYTEST_JOINED}" != *" -n "* ]] && [[ "${PYTEST_JOINED}" != *" -n="* ]] && [[ "${PYTEST_JOINED}" != *" --numprocesses"* ]]; then
        FINAL_PYTEST_ARGS+=("-n" "${PYTEST_WORKERS}")
    fi
    if [[ "${RUN_SLOW}" -eq 1 ]]; then
        if [[ "${PYTEST_JOINED}" != *" -m "* ]] && [[ "${PYTEST_JOINED}" != *" -m="* ]]; then
            FINAL_PYTEST_ARGS+=("-m" "slow or not slow")
        fi
        echo "🧪 [${STEP}/${TOTAL_STEPS}] Running full Python test suite (including @pytest.mark.slow)..."
    else
        echo "🧪 [${STEP}/${TOTAL_STEPS}] Running fast Python test suite (excluding slow CAD/physics)..."
    fi
    if [[ "${#PYTEST_ARGS[@]}" -gt 0 ]]; then
        FINAL_PYTEST_ARGS+=("${PYTEST_ARGS[@]}")
    fi
    pytest "${FINAL_PYTEST_ARGS[@]}"
    STEP=$((STEP + 1))
fi

if [[ "${RUN_SMOKE}" -eq 1 ]]; then
    echo "🔥 [${STEP}/${TOTAL_STEPS}] Running integration smoke test suite..."
    python tools/smoke.py
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "✅ Pre-commit verification PASSED in ${ELAPSED}s"
