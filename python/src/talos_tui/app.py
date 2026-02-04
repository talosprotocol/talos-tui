"""
Talos TUI Application Entry Point.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Any

from textual.app import App
from textual.binding import Binding
from textual.theme import Theme

from talos_tui.core.state import StateStore
from talos_tui.core.coordinator import Coordinator, TuiState
from talos_tui.core.contracts import ContractValidator

from talos_tui.adapters.gateway_http import HttpGatewayAdapter
from talos_tui.adapters.audit_http import HttpAuditAdapter
from talos_tui.adapters.mock import MockGatewayAdapter, MockAuditAdapter

from talos_tui.ui.screens.dashboard import StatusDashboard
from talos_tui.ui.screens.audit import AuditViewer
from talos_tui.ui.screens.startup import StartupScreen

# Configure logging early and REDIRECT to file
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    filename="talos-tui.log",
    filemode="a"
)
logger = logging.getLogger(__name__)

# Constants
GATEWAY_URL = os.getenv("TALOS_GATEWAY_URL", "http://localhost:8000")
AUDIT_URL = os.getenv("TALOS_AUDIT_URL", "http://localhost:8001")
USE_MOCK = os.getenv("TALOS_TUI_MOCK", "0") == "1"
CONTRACTS_ROOT = (
    Path(__file__).parent.parent.parent.parent.parent / "contracts"
)

TALOS_COMMAND_CENTER = Theme(
    name="talos-command-center",
    primary="#14FFEC",
    secondary="#7AA2F7",
    accent="#14FFEC",
    foreground="#E6EDF3",
    background="#0A0E14",
    success="#00FF9C",
    warning="#F1FA8C",
    error="#FF007A",
    surface="#161B22",
    panel="#161B22",
    dark=True,
)


class TalosTuiApp(App[None]):
    """
    Main TUI Application class.
    Manages the lifecycle, screens, and coordination logic.
    """
    TITLE = "TALOS COMMAND CENTER"
    CSS_PATH = "ui/talos.tcss"

    BINDINGS = [
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("a", "show_audit", "Audit Logs"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.store = StateStore()
        self.validator = ContractValidator(CONTRACTS_ROOT / "schemas")

        self.gateway: Any = None
        self.audit: Any = None

        self.coordinator: Optional[Coordinator] = None
        self.dashboard_screen = StatusDashboard(self.store)
        self.audit_screen = AuditViewer(self.store)

        if not USE_MOCK:
            # Type hint for mypy, though we import aiohttp later
            self._session: Any = None

    async def on_mount(self) -> None:
        """Initialize theme and start coordinator."""
        self.register_theme(TALOS_COMMAND_CENTER)
        self.theme = "talos-command-center"

        if USE_MOCK:
            self.gateway = MockGatewayAdapter()
            self.audit = MockAuditAdapter()
        else:
            import aiohttp  # pylint: disable=import-outside-toplevel
            # Shared session for all adapters
            self._session = aiohttp.ClientSession()
            self.gateway = HttpGatewayAdapter(
                GATEWAY_URL, self._session, validator=self.validator
            )
            self.audit = HttpAuditAdapter(
                AUDIT_URL, self._session, validator=self.validator
            )

        self.coordinator = Coordinator(
            self.store,
            self.gateway,
            self.audit,
            contracts_version_gate="1"
        )

        self.install_screen(self.dashboard_screen, name="dashboard")
        self.install_screen(self.audit_screen, name="audit")

        self.push_screen(StartupScreen(self.store))
        await self.coordinator.start()

        # Monitor coordinator state to trigger screen transitions
        self.set_interval(0.5, self._check_transitions)

    def _check_transitions(self) -> None:
        """Check for state changes to trigger navigation."""
        if not self.coordinator:
            return
        if (
            self.coordinator.state == TuiState.RUNNING and
            self.screen.__class__.__name__ == "StartupScreen"
        ):
            logger.info("Transitioning to dashboard")
            self.pop_screen()
            self.switch_screen("dashboard")

    def action_show_dashboard(self) -> None:
        """Switch to dashboard screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("dashboard")

    def action_show_audit(self) -> None:
        """Switch to audit screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("audit")

    async def on_unmount(self) -> None:
        """Cleanup resources on exit."""
        if self.coordinator:
            await self.coordinator.stop()
        if not USE_MOCK and hasattr(self, "_session"):
            await self._session.close()


def main() -> None:
    """Entry point for the application."""
    app = TalosTuiApp()
    app.run()
