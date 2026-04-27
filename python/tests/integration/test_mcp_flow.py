import pytest
import os
import sys
from textual.widgets import Input, Button, DataTable
from unittest.mock import patch

@pytest.mark.asyncio
async def test_tui_mcp_selenium_style_flow():
    """
    Selenium-style E2E functional test for the TUI MCP Manager Screen.
    Simulates user typing and clicking without calling inner methods directly.
    """
    # Force mock mode before import
    os.environ["TALOS_TUI_MOCK"] = "1"
    if "talos_tui.app" in sys.modules:
        del sys.modules["talos_tui.app"]
        
    from talos_tui.app import TalosTuiApp
    from talos_tui.ui.screens.mcp import McpManager
    app = TalosTuiApp()

    async with app.run_test() as pilot:
        # Wait for app boot and mock handshakes
        await pilot.pause(2.0)
        
        # Navigate to MCP screen
        await pilot.press("m")
        await pilot.pause(0.2)
        assert isinstance(app.screen, McpManager)
        
        # Find input widgets
        id_input = app.screen.query_one("#mcp-server-id", Input)
        name_input = app.screen.query_one("#mcp-server-name", Input)
        endpoint_input = app.screen.query_one("#mcp-server-endpoint", Input)
        
        # Simulate filling out the form
        id_input.value = "test-selenium-server"
        name_input.value = "Selenium Style Server"
        endpoint_input.value = "stdio://test"
        
        # Click the Add Server button
        add_button = app.screen.query_one("#btn-mcp-add-server", Button)
        await pilot.click("#btn-mcp-add-server")
        
        # Wait for refresh
        await pilot.pause(0.5)
        
        # Verify inputs were cleared (happens after successful add)
        assert id_input.value == ""
        assert name_input.value == ""
        assert endpoint_input.value == ""
        
        # Verify the table contains the new server
        table = app.screen.query_one("#mcp-servers-table", DataTable)
        
        # Extract all text from table rows
        rows_text = []
        for i in range(len(table.rows)):
            row = table.get_row_at(i)
            # row cells can be strings or rich Renderables
            row_text = " ".join([str(cell) for cell in row])
            rows_text.append(row_text)
            
        found = any("test-selenium-server" in rt for rt in rows_text)
        assert found, "New server 'test-selenium-server' not found in data table"
