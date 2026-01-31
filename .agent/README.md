# Agent workspace: tools/talos-tui

This folder contains agent-facing context, tasks, workflows, and planning artifacts for this submodule.

## Current State
TUI tool is undergoing redesign focused on stability and contract alignment. Separation of side effects and UI state is a primary architecture theme.

## Expected State
Stable polling, resilient adapters, and full keyboard-accessible UI with strong tests. No handshake loops, no rendering bugs, and strict contract compliance.

## Behavior
Terminal UI for interacting with Talos services and audit streams. Acts as an operator tool with strong error handling and observability.

## How to work here
- Run/tests:
- Local dev:
- CI notes:

## Interfaces and dependencies
- Owned APIs/contracts:
- Depends on:
- Data stores/events (if any):

## Global context
See `.agent/context.md` for monorepo-wide invariants and architecture.
