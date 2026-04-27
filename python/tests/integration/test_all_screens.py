import pytest
import os
import sys
from talos_tui.ui.screens.dashboard import StatusDashboard
from talos_tui.ui.screens.audit import AuditViewer
from talos_tui.ui.screens.rbac import RbacManager
from talos_tui.ui.screens.secrets import SecretsManager
from talos_tui.ui.screens.config import ConfigManager
from talos_tui.ui.screens.governance import GovernanceViewer
from talos_tui.ui.screens.budgets import BudgetManager
from talos_tui.ui.screens.mcp import McpManager
from talos_tui.ui.screens.api_console import ApiConsole

@pytest.mark.asyncio
async def test_tui_all_screens_navigation():
    """
    Comprehensive integration test that visits every screen in the TUI
    to ensure there are no rendering crashes or routing failures.
    """
    # Force mock mode before import
    os.environ["TALOS_TUI_MOCK"] = "1"
    if "talos_tui.app" in sys.modules:
        del sys.modules["talos_tui.app"]
        
    from talos_tui.app import TalosTuiApp
    app = TalosTuiApp()

    async with app.run_test() as pilot:
        # Wait for app boot and mock handshakes
        await pilot.pause(2.0)
        
        # Define the navigation sequence
        # (key, expected_screen_class)
        navigation_sequence = [
            ("d", StatusDashboard),
            ("a", AuditViewer),
            ("r", RbacManager),
            ("s", SecretsManager),
            ("c", ConfigManager),
            ("g", GovernanceViewer),
            ("b", BudgetManager),
            ("m", McpManager),
            ("x", ApiConsole),
        ]
        
        for key, screen_cls in navigation_sequence:
            await pilot.press(key)
            await pilot.pause(0.2)
            assert isinstance(app.screen, screen_cls), f"Expected {screen_cls.__name__} after pressing '{key}', but got {app.screen.__class__.__name__}"
            
            # Simple check to ensure the screen has a Header or basic structure rendered
            # If the screen crashed, it wouldn't be fully mounted or would show an error
            assert app.screen.is_mounted, f"Screen {screen_cls.__name__} failed to mount properly."
