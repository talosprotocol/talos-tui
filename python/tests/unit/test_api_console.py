from __future__ import annotations

import inspect

from talos_tui.adapters.audit_http import HttpAuditAdapter
from talos_tui.adapters.gateway_http import HttpGatewayAdapter
from talos_tui.ui.screens.api_console import (
    TUI_API_OPERATIONS,
    build_operation_call,
)


def _public_async_method_names(cls: type[object]) -> set[str]:
    return {
        name
        for name, value in cls.__dict__.items()
        if not name.startswith("_") and inspect.iscoroutinefunction(value)
    }


def test_operation_registry_covers_all_public_gateway_and_audit_calls() -> None:
    gateway_methods = _public_async_method_names(HttpGatewayAdapter)
    audit_methods = _public_async_method_names(HttpAuditAdapter)

    registered_gateway = {
        operation.method_name
        for operation in TUI_API_OPERATIONS
        if operation.target == "gateway"
    }
    registered_audit = {
        operation.method_name
        for operation in TUI_API_OPERATIONS
        if operation.target == "audit"
    }

    assert registered_gateway == gateway_methods
    assert registered_audit == audit_methods


def test_build_operation_call_maps_primary_arg_and_json_payload() -> None:
    operation = next(
        item for item in TUI_API_OPERATIONS if item.id == "gateway_create_secret"
    )

    target, method_name, args, kwargs = build_operation_call(
        operation,
        primary_arg="openai-key",
        secondary_arg="",
        payload_text='{"value": "sk-test"}',
    )

    assert target == "gateway"
    assert method_name == "create_secret"
    assert args == ["openai-key", "sk-test"]
    assert kwargs == {}


def test_build_operation_call_handles_optional_audit_pagination_payload() -> None:
    operation = next(
        item for item in TUI_API_OPERATIONS if item.id == "audit_list_events"
    )

    target, method_name, args, kwargs = build_operation_call(
        operation,
        primary_arg="",
        secondary_arg="",
        payload_text='{"limit": 25, "before": "cursor_123"}',
    )

    assert target == "audit"
    assert method_name == "list_events"
    assert args == []
    assert kwargs == {"limit": 25, "before": "cursor_123"}


def test_build_operation_call_maps_mcp_server_payload() -> None:
    operation = next(
        item for item in TUI_API_OPERATIONS if item.id == "gateway_create_mcp_server"
    )

    target, method_name, args, kwargs = build_operation_call(
        operation,
        primary_arg="",
        secondary_arg="",
        payload_text='{"id": "filesystem", "name": "Filesystem", "endpoint": "stdio://fs"}',
    )

    assert target == "gateway"
    assert method_name == "create_mcp_server"
    assert args == [{"id": "filesystem", "name": "Filesystem", "endpoint": "stdio://fs"}]
    assert kwargs == {}


def test_build_operation_call_maps_mcp_policy_delete_primary_arg() -> None:
    operation = next(
        item for item in TUI_API_OPERATIONS if item.id == "gateway_delete_mcp_policy"
    )

    target, method_name, args, kwargs = build_operation_call(
        operation,
        primary_arg="policy-eng",
        secondary_arg="",
        payload_text="",
    )

    assert target == "gateway"
    assert method_name == "delete_mcp_policy"
    assert args == ["policy-eng"]
    assert kwargs == {}
