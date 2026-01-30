# Talos Protocol TUI

A terminal-based user interface for monitoring and inspecting the Talos Protocol network.

![Talos TUI](https://placeholder-image-url.com) (*Screenshot placeholder*)

## Features (v2 Redesign)

*   **Resilient State Machine**: Formal coordinator with exponential backoff, jitter, and absolute handshake budgets.
*   **Mechanized Contract Safety**: Runtime JSON Schema validation for all audit events and a startup version gate.
*   **Pure UI Projections**: Centralized `StateStore` with reactive dashboard and audit viewer, ensuring UI stability.
*   **Health & Freshness Tracking**: Real-time status bar and stale-data indicators for all service dependencies.
*   **Safe Execution**: Redacted secrets (REGEX-based), hard timeouts, and payload size capping.

## Installation

### From Source

```bash
cd tools/talos-tui/python
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Ensure you have a running Gateway and Audit service.

```bash
# Minimal run (defaults to localhost)
talos-tui

# Custom Endpoints
export TALOS_GATEWAY_URL="http://gateway:8000"
export TALOS_AUDIT_URL="http://auditService:8001"
talos-tui
```

## Development

### Architecture

The project implements a **Resilient Hexagonal Architecture**:

*   **`domain`**: Pure data models (View State).
*   **`ports`**: Protocol definitions for external services and configuration.
*   **`adapters`**: Resilient HTTP implementations with built-in retries and contract validation.
*   **`core`**: The brain of the TUI—contains the `StateStore` (reducer) and `Coordinator` (state machine).
*   **`ui`**: Textual screens that act as pure projections of the `StateStore`.

### Running Tests

```bash
cd tools/talos-tui/python
# Unit Tests (Resilience & State Logic)
pytest tests/unit

# Integration Tests (Network Safety & Mock Probes)
pytest tests/integration
```

### Developer Convenience

We provide a `Makefile` and helper scripts to simplify common tasks:

```bash
cd tools/talos-tui/python

# First time setup (creates venv, installs deps)
make setup

# Run the TUI (auto-activates venv)
../../scripts/tui_run.sh

# Run all tests
make test

# Run tests with coverage
make test-cov

# Lint code
make lint
```

## Deployment

### Docker

Build the image:
```bash
docker build -t talos-tui -f tools/talos-tui/Dockerfile tools/talos-tui
```

Run container:
```bash
docker run -it --rm \
  -e TALOS_GATEWAY_URL="http://host.docker.internal:8000" \
  -e TALOS_AUDIT_URL="http://host.docker.internal:8001" \
  talos-tui
```

### Helm

Install the chart:
```bash
helm install talos-tui tools/talos-tui/helm/talos-tui \
  --set env.TALOS_GATEWAY_URL="http://gateway-service:8000"
```

To access the TUI in the cluster:
```bash
# Find pod name
kubectl get pods -l app.kubernetes.io/name=talos-tui

# Attach to the running session (requires tty: true in deployment)
kubectl attach -it deployment/talos-tui -c talos-tui
```
