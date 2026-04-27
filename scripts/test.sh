#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Talos TUI Standardized Test Entrypoint
# =============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_DIR="$ROOT_DIR/python"
ARTIFACTS_DIR="$ROOT_DIR/artifacts/coverage"
RESULTS_DIR="$ROOT_DIR/artifacts/test"
VENV_DIR=""
COMMAND=${1:-"--unit"}
HOST_PYTHON="${TALOS_PYTHON:-python3}"

mkdir -p "$ARTIFACTS_DIR" "$RESULTS_DIR"

pick_python() {
    local candidates=()
    if [[ -n "${TALOS_PYTHON:-}" ]]; then
        candidates+=("${TALOS_PYTHON}")
    fi
    candidates+=(python3.13 python3.12 python3.11 python3 python3.14)

    local candidate
    for candidate in "${candidates[@]}"; do
        command -v "$candidate" >/dev/null 2>&1 || continue
        if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
        then
            echo "$candidate"
            return 0
        fi
    done

    echo "Talos TUI tests require Python >= 3.11. Set TALOS_PYTHON to a compatible interpreter." >&2
    exit 1
}

HOST_PYTHON="$(pick_python)"
PYTHON_TAG="$("$HOST_PYTHON" - <<'PY'
import sys
print(f"{sys.version_info[0]}.{sys.version_info[1]}")
PY
)"
VENV_DIR="$PYTHON_DIR/.venv-test-py${PYTHON_TAG}"

ensure_virtualenv() {
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        echo "Creating local TUI test virtualenv with $("$HOST_PYTHON" --version 2>&1)..."
        "$HOST_PYTHON" -m venv "$VENV_DIR"
    fi
}

ensure_virtualenv
PYTHON_BIN="$VENV_DIR/bin/python"

ensure_test_dependencies() {
    if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import importlib.util

required = ["pytest", "pytest_asyncio", "pytest_cov", "aioresponses", "textual", "talos_tui"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
raise SystemExit(0 if not missing else 1)
PY
    then
        return 0
    fi

    echo "Installing TUI test dependencies with $("$PYTHON_BIN" --version 2>&1)..."
    (
        cd "$PYTHON_DIR"
        PIP_DISABLE_PIP_VERSION_CHECK=1 "$PYTHON_BIN" -m pip install -r requirements.txt -r requirements-dev.txt -e .
    )
}

ensure_test_dependencies

run_unit() {
    echo "=== Running Unit Tests ==="
    (
        cd "$PYTHON_DIR"
        PYTHONPATH=src "$PYTHON_BIN" -m pytest tests/unit tests/integration tests/architecture
    )
}

run_smoke() {
    echo "=== Running Smoke Tests ==="
    set +e
    (
        cd "$PYTHON_DIR"
        PYTHONPATH=src "$PYTHON_BIN" -m pytest tests/ -m smoke --maxfail=1 -q
    )
    local status=$?
    set -e
    if [[ $status -eq 0 || $status -eq 5 ]]; then
        if [[ $status -eq 5 ]]; then
            echo "No smoke tests collected. Skipping."
        fi
        return 0
    fi
    return "$status"
}

run_coverage() {
    echo "=== Running Coverage (pytest-cov) ==="
    (
        cd "$PYTHON_DIR"
        PYTHONPATH=src "$PYTHON_BIN" -m pytest --cov=talos_tui --cov-fail-under=0 \
            --cov-report=xml:"$ARTIFACTS_DIR/coverage.xml" tests/
    )
}

case "$COMMAND" in
    --smoke)
        run_smoke
        ;;
    --unit)
        run_unit
        ;;
    --integration)
        echo "=== Running Integration Tests ==="
        (
            cd "$PYTHON_DIR"
            PYTHONPATH=src "$PYTHON_BIN" -m pytest tests/integration
        )
        ;;
    --coverage)
        run_coverage
        ;;
    --ci)
        run_smoke
        run_unit
        run_coverage
        ;;
    --full)
        run_smoke
        run_unit
        run_coverage
        ;;
    *)
        echo "Usage: $0 {--smoke|--unit|--integration|--coverage|--ci|--full}"
        exit 1
        ;;
esac

cat <<EOF > "$RESULTS_DIR/results.json"
{
  "repo_id": "tools-talos-tui",
  "command": "$COMMAND",
  "status": "pass",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
