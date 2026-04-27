import pytest
from unittest.mock import patch
import os
import sys
from talos_tui.ui.screens.dashboard import StatusDashboard
from talos_tui.ui.screens.audit import AuditViewer

@pytest.mark.asyncio
async def test_tui_app_navigation():
    # Force mock mode before import
    os.environ["TALOS_TUI_MOCK"] = "1"
    if "talos_tui.app" in sys.modules:
        del sys.modules["talos_tui.app"]
        
    from talos_tui.app import TalosTuiApp
    app = TalosTuiApp()
    
    async with app.run_test() as pilot:
        # Wait for app to be ready and push past the startup screen if needed
        # Startup screen will hit Mock adapters and transition to StatusDashboard
        await pilot.pause(2.0)
        
        # Test navigation to Audit
        await pilot.press("a")
        await pilot.pause(0.2)
        assert isinstance(app.screen, AuditViewer)
        
        # Test navigation to Dashboard
        await pilot.press("d")
        await pilot.pause(0.2)
        assert isinstance(app.screen, StatusDashboard)

