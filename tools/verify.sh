#!/usr/bin/env bash
set -euo pipefail

START_TIME=$(date +%s)

# Raise open file descriptor limit if possible
ulimit -n 65536 2>/dev/null || true

# Resolve cq conda environment if not already in PATH
if [ -d "/workspace/miniforge3/envs/cq/bin" ]; then
    export PATH="/workspace/miniforge3/envs/cq/bin:${PATH}"
elif [ -d "${HOME}/miniforge3/envs/cq/bin" ]; then
    export PATH="${HOME}/miniforge3/envs/cq/bin:${PATH}"
elif [ -d "/root/miniforge3/envs/cq/bin" ]; then
    export PATH="/root/miniforge3/envs/cq/bin:${PATH}"
fi

export PYTHONPATH=".:tools:${PYTHONPATH:-}"
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=false"

echo "🔍 [1/4] Checking Python compilation syntax..."
python -m compileall -q .

echo "🎨 [2/4] Checking code formatting..."
ruff format --check .

echo "🧹 [3/4] Checking linting rules..."
ruff check .

echo "🧪 [4/4] Running fast test suite (excluding slow CAD/physics)..."
NUM_CPUS=$(OMP_NUM_THREADS= nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
if [ "${NUM_CPUS}" -gt 4 ]; then
    PYTEST_WORKERS=4
else
    PYTEST_WORKERS="${NUM_CPUS}"
fi

if [[ "$*" == *"-n "* ]] || [[ "$*" == *"-n="* ]]; then
    pytest "$@"
else
    pytest -n "${PYTEST_WORKERS}" "$@"
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "✅ Pre-commit verification PASSED in ${ELAPSED}s"
