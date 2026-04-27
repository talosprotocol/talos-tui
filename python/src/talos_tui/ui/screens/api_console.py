"""Interactive API console for Talos TUI operators."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static


Target = Literal["gateway", "audit"]


@dataclass(frozen=True)
class ApiOperation:
    """Operator-facing description of a callable adapter operation."""

    id: str
    target: Target
    method_name: str
    label: str
    description: str


TUI_API_OPERATIONS = (
    ApiOperation(
        "gateway_get_version",
        "gateway",
        "get_version",
        "Gateway Version",
        "Fetch gateway version metadata.",
    ),
    ApiOperation(
        "gateway_get_health",
        "gateway",
        "get_health",
        "Gateway Health",
        "Fetch gateway readiness status.",
    ),
    ApiOperation(
        "gateway_get_metrics_summary",
        "gateway",
        "get_metrics_summary",
        "Gateway Metrics",
        "Fetch gateway metrics summary.",
    ),
    ApiOperation(
        "gateway_list_peers",
        "gateway",
        "list_peers",
        "Gateway Peers",
        "List connected peers.",
    ),
    ApiOperation(
        "gateway_list_sessions",
        "gateway",
        "list_sessions",
        "Gateway Sessions",
        "List active sessions.",
    ),
    ApiOperation(
        "gateway_list_rbac_roles",
        "gateway",
        "list_rbac_roles",
        "RBAC Roles",
        "List RBAC roles.",
    ),
    ApiOperation(
        "gateway_upsert_rbac_role",
        "gateway",
        "upsert_rbac_role",
        "Upsert RBAC Role",
        "Create or update an RBAC role. Payload expects role definition.",
    ),
    ApiOperation(
        "gateway_list_rbac_bindings",
        "gateway",
        "list_rbac_bindings",
        "RBAC Bindings",
        "List RBAC bindings.",
    ),
    ApiOperation(
        "gateway_upsert_rbac_binding",
        "gateway",
        "upsert_rbac_binding",
        "Upsert RBAC Binding",
        "Create or update an RBAC binding.",
    ),
    ApiOperation(
        "gateway_list_secrets",
        "gateway",
        "list_secrets",
        "Secrets",
        "List secret metadata.",
    ),
    ApiOperation(
        "gateway_create_secret",
        "gateway",
        "create_secret",
        "Create Secret",
        "Create a secret. Primary arg is the name. Payload expects {\"value\": \"...\"}.",
    ),
    ApiOperation(
        "gateway_delete_secret",
        "gateway",
        "delete_secret",
        "Delete Secret",
        "Delete a secret by name.",
    ),
    ApiOperation(
        "gateway_get_kek_status",
        "gateway",
        "get_kek_status",
        "KEK Status",
        "Fetch KEK rotation state.",
    ),
    ApiOperation(
        "gateway_rotate_all_secrets",
        "gateway",
        "rotate_all_secrets",
        "Rotate Secrets",
        "Start a global secret rotation.",
    ),
    ApiOperation(
        "gateway_get_rotation_status",
        "gateway",
        "get_rotation_status",
        "Rotation Status",
        "Fetch a rotation operation by primary arg op id.",
    ),
    ApiOperation(
        "gateway_export_config",
        "gateway",
        "export_config",
        "Export Config",
        "Export current platform config.",
    ),
    ApiOperation(
        "gateway_apply_config",
        "gateway",
        "apply_config",
        "Apply Config",
        "Apply config from JSON payload.",
    ),
    ApiOperation(
        "gateway_list_governance_logs",
        "gateway",
        "list_governance_logs",
        "Governance Logs",
        "List governance log entries.",
    ),
    ApiOperation(
        "gateway_get_telemetry_stats",
        "gateway",
        "telemetry_stats",
        "Telemetry Stats",
        "Fetch aggregated usage and latency telemetry.",
    ),
    ApiOperation(
        "gateway_get_audit_stats",
        "gateway",
        "audit_stats",
        "Audit Stats",
        "Fetch security and denial statistics.",
    ),
    ApiOperation(
        "gateway_list_budget_scopes",
        "gateway",
        "list_budget_scopes",
        "Budget Scopes",
        "List budget scopes.",
    ),
    ApiOperation(
        "gateway_list_virtual_keys",
        "gateway",
        "list_virtual_keys",
        "Virtual Keys",
        "List virtual keys.",
    ),
    ApiOperation(
        "gateway_list_teams",
        "gateway",
        "list_teams",
        "Teams",
        "List teams.",
    ),
    ApiOperation(
        "gateway_list_mcp_servers",
        "gateway",
        "list_mcp_servers",
        "MCP Servers",
        "List MCP servers.",
    ),
    ApiOperation(
        "gateway_create_mcp_server",
        "gateway",
        "create_mcp_server",
        "Create MCP Server",
        "Create an MCP server from JSON payload.",
    ),
    ApiOperation(
        "gateway_enable_mcp_server",
        "gateway",
        "enable_mcp_server",
        "Enable MCP Server",
        "Enable an MCP server by primary arg server id.",
    ),
    ApiOperation(
        "gateway_disable_mcp_server",
        "gateway",
        "disable_mcp_server",
        "Disable MCP Server",
        "Disable an MCP server by primary arg server id.",
    ),
    ApiOperation(
        "gateway_delete_mcp_server",
        "gateway",
        "delete_mcp_server",
        "Delete MCP Server",
        "Delete an MCP server by primary arg server id.",
    ),
    ApiOperation(
        "gateway_list_mcp_policies",
        "gateway",
        "list_mcp_policies",
        "MCP Policies",
        "List MCP policies. Primary arg optionally sets team_id.",
    ),
    ApiOperation(
        "gateway_upsert_mcp_policy",
        "gateway",
        "upsert_mcp_policy",
        "Upsert MCP Policy",
        "Create or replace an MCP policy from JSON payload.",
    ),
    ApiOperation(
        "gateway_delete_mcp_policy",
        "gateway",
        "delete_mcp_policy",
        "Delete MCP Policy",
        "Delete an MCP policy by primary arg policy id.",
    ),
    ApiOperation(
        "audit_get_version",
        "audit",
        "get_version",
        "Audit Version",
        "Fetch audit service version metadata.",
    ),
    ApiOperation(
        "audit_get_health",
        "audit",
        "get_health",
        "Audit Health",
        "Fetch audit service health.",
    ),
    ApiOperation(
        "audit_list_events",
        "audit",
        "list_events",
        "Audit Events",
        "List events. Payload may include {\"limit\": 25, \"before\": \"cursor\"}.",
    ),
)

_OPERATION_INDEX = {operation.id: operation for operation in TUI_API_OPERATIONS}


def _parse_payload(payload_text: str) -> dict[str, Any]:
    """Parse the operator JSON payload, treating empty input as an empty object."""

    if not payload_text.strip():
        return {}

    data = json.loads(payload_text)
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object.")
    return data


def build_operation_call(
    operation: ApiOperation,
    primary_arg: str,
    secondary_arg: str,
    payload_text: str,
) -> tuple[Target, str, list[Any], dict[str, Any]]:
    """Build a callable adapter invocation from free-form operator input."""

    del secondary_arg
    payload = _parse_payload(payload_text)
    target = operation.target
    method_name = operation.method_name

    if operation.id == "gateway_create_secret":
        value = payload.get("value")
        if not primary_arg.strip():
            raise ValueError("Primary arg must contain the secret name.")
        if not isinstance(value, str) or not value:
            raise ValueError("Payload must include a non-empty string `value`.")
        return target, method_name, [primary_arg.strip(), value], {}

    if operation.id in {
        "gateway_delete_secret",
        "gateway_get_rotation_status",
        "gateway_enable_mcp_server",
        "gateway_disable_mcp_server",
        "gateway_delete_mcp_server",
        "gateway_delete_mcp_policy",
    }:
        if not primary_arg.strip():
            raise ValueError("Primary arg is required for this operation.")
        return target, method_name, [primary_arg.strip()], {}

    if operation.id == "gateway_apply_config":
        return target, method_name, [payload], {}

    if operation.id in {"gateway_create_mcp_server", "gateway_upsert_mcp_policy"}:
        if not payload:
            raise ValueError("Payload must contain a JSON object for this operation.")
        return target, method_name, [payload], {}

    if operation.id == "gateway_list_mcp_policies":
        team_id = primary_arg.strip()
        return target, method_name, [], {"team_id": team_id} if team_id else {}

    if operation.id == "audit_list_events":
        kwargs: dict[str, Any] = {}
        if "limit" in payload:
            kwargs["limit"] = int(payload["limit"])
        if "before" in payload and payload["before"]:
            kwargs["before"] = payload["before"]
        return target, method_name, [], kwargs

    return target, method_name, [], {}


def _serialize_result(result: Any) -> str:
    """Format adapter return values for operator display."""

    if result is None:
        return json.dumps({"ok": True}, indent=2)

    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), indent=2, sort_keys=True)

    if isinstance(result, list):
        normalized = []
        for item in result:
            if hasattr(item, "model_dump"):
                normalized.append(item.model_dump())
            else:
                normalized.append(item)
        return json.dumps(normalized, indent=2, sort_keys=True)

    return json.dumps(result, indent=2, sort_keys=True)


class ApiConsole(Screen[None]):
    """Screen that exposes every TUI adapter call to the operator."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="api-console"):
            yield Static(
                "[bold cyan]OPERATOR API CONSOLE[/bold cyan]  "
                "[dim]Every gateway and audit adapter call is executable from here.[/dim]",
                id="api-console-title",
            )
            with Horizontal():
                yield Input(placeholder="Primary arg (name, id, or team_id)", id="api-primary-arg")
                yield Input(
                    placeholder="Secondary arg (reserved for future use)",
                    id="api-secondary-arg",
                )
            yield Input(
                placeholder='JSON payload, e.g. {"value": "sk-test"}',
                id="api-payload",
            )
            with Horizontal(id="api-groups"):
                with Container(classes="api-group-panel"):
                    yield Static("[bold]Gateway Calls[/bold]", classes="panel-title")
                    with VerticalScroll():
                        for operation in TUI_API_OPERATIONS:
                            if operation.target != "gateway":
                                continue
                            yield Button(
                                operation.label,
                                id=f"op-{operation.id}",
                                classes="api-op",
                            )
                with Container(classes="api-group-panel"):
                    yield Static("[bold]Audit Calls[/bold]", classes="panel-title")
                    with VerticalScroll():
                        for operation in TUI_API_OPERATIONS:
                            if operation.target != "audit":
                                continue
                            yield Button(
                                operation.label,
                                id=f"op-{operation.id}",
                                classes="api-op",
                            )
            yield Static("Select an operation to begin.", id="api-last-operation")
            with Container(id="api-response-panel"):
                yield Static("", id="api-response")
        yield Footer()

    @on(Button.Pressed, ".api-op")
    async def run_operation(self, event: Button.Pressed) -> None:
        """Execute the selected adapter operation."""

        op_id = event.button.id.removeprefix("op-")
        operation = _OPERATION_INDEX[op_id]

        primary_arg = self.query_one("#api-primary-arg", Input).value
        secondary_arg = self.query_one("#api-secondary-arg", Input).value
        payload_text = self.query_one("#api-payload", Input).value
        response_widget = self.query_one("#api-response", Static)

        try:
            target, method_name, args, kwargs = build_operation_call(
                operation,
                primary_arg=primary_arg,
                secondary_arg=secondary_arg,
                payload_text=payload_text,
            )
        except Exception as exc:
            response_widget.update(json.dumps({"error": str(exc)}, indent=2))
            self.notify(str(exc), title="API Console Failure", severity="error")
            return

        adapter = getattr(self.app, target, None)
        if adapter is None:
            self.notify(f"{target.title()} adapter is not connected.", severity="error")
            return

        self.query_one("#api-last-operation", Static).update(
            f"[bold]{operation.label}[/bold]  [dim]{operation.description}[/dim]"
        )
        response_widget.update("[dim]Running…[/dim]")

        try:
            result = await getattr(adapter, method_name)(*args, **kwargs)
            response_widget.update(_serialize_result(result))
            self.notify(f"{operation.label} completed.", title="API Console")
        except Exception as exc:  # pragma: no cover - UI guard
            response_widget.update(json.dumps({"error": str(exc)}, indent=2))
            self.notify(str(exc), title="API Console Failure", severity="error")
