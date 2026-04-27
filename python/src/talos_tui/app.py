"""
Talos TUI Application Entry Point.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Any
from dotenv import load_dotenv

# Load .env from root or current dir
load_dotenv()
load_dotenv(Path(__file__).parent.parent.parent.parent.parent / ".env")

from textual.app import App
from textual.binding import Binding
from textual.theme import Theme

from talos_tui.core.state import StateStore
from talos_tui.core.coordinator import Coordinator, TuiState
from talos_tui.core.config import TuiAuthConfig
from talos_tui.core.contracts import ContractValidator

from talos_tui.adapters.gateway_http import HttpGatewayAdapter
from talos_tui.adapters.audit_http import HttpAuditAdapter
from talos_tui.adapters.token_broker import AsyncScopedJwtTokenBroker
from talos_tui.adapters.mock import MockGatewayAdapter, MockAuditAdapter

from talos_tui.ui.screens.dashboard import StatusDashboard
from talos_tui.ui.screens.audit import AuditViewer
from talos_tui.ui.screens.rbac import RbacManager
from talos_tui.ui.screens.secrets import SecretsManager
from talos_tui.ui.screens.config import ConfigManager
from talos_tui.ui.screens.governance import GovernanceViewer
from talos_tui.ui.screens.startup import StartupScreen
from talos_tui.ui.screens.budgets import BudgetManager
from talos_tui.ui.screens.mcp import McpManager
from talos_tui.ui.screens.api_console import ApiConsole

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
GATEWAY_URL = os.getenv("TALOS_GATEWAY_URL", "http://127.0.0.1:8000")
AUDIT_URL = os.getenv("TALOS_AUDIT_URL", "http://127.0.0.1:8001")
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
        Binding("r", "show_rbac", "RBAC"),
        Binding("s", "show_secrets", "Secrets"),
        Binding("c", "show_config", "Config"),
        Binding("g", "show_governance", "Gov"),
        Binding("b", "show_budgets", "Budgets"),
        Binding("m", "show_mcp", "MCP"),
        Binding("x", "show_api_console", "API"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.store = StateStore()
        self.validator = ContractValidator(CONTRACTS_ROOT / "schemas")
        self.auth_config = TuiAuthConfig.from_env()
        self.auth_broker: Optional[AsyncScopedJwtTokenBroker] = None

        self.gateway: Any = None
        self.audit: Any = None
        self._session: Any = None

        self.coordinator: Optional[Coordinator] = None
        self.dashboard_screen = StatusDashboard(self.store)
        self.audit_screen = AuditViewer(self.store)
        self.rbac_screen = RbacManager(self.store)
        self.secrets_screen = SecretsManager(self.store)
        self.config_screen = ConfigManager(self.store)
        self.governance_screen = GovernanceViewer(self.store)
        self.budgets_screen = BudgetManager(self.store)
        self.mcp_screen = McpManager(self.store)
        self.api_console_screen = ApiConsole()

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
            if not self.auth_config.admin_secret:
                raise RuntimeError(
                    "TUI live mode requires TALOS_TUI_ADMIN_SECRET or AUTH_ADMIN_SECRET "
                    "so it can mint scoped session JWTs before API requests."
                )
            self.auth_broker = AsyncScopedJwtTokenBroker(
                GATEWAY_URL,
                self._session,
                principal=self.auth_config.principal,
                admin_secret=self.auth_config.admin_secret,
                data_plane_token=self.auth_config.data_plane_token,
                ttl_seconds=self.auth_config.ttl_seconds,
                session_id=self.auth_config.session_id,
            )
            self.gateway = HttpGatewayAdapter(
                GATEWAY_URL,
                self._session,
                validator=self.validator,
                auth_broker=self.auth_broker,
                auth_permissions=self.auth_config.gateway_permissions,
            )
            self.audit = HttpAuditAdapter(
                AUDIT_URL,
                self._session,
                validator=self.validator,
                auth_broker=self.auth_broker,
                auth_permissions=self.auth_config.audit_permissions,
            )

        self.coordinator = Coordinator(
            self.store,
            self.gateway,
            self.audit,
            contracts_version_gate="1"
        )

        self.install_screen(self.dashboard_screen, name="dashboard")
        self.install_screen(self.audit_screen, name="audit")
        self.install_screen(self.rbac_screen, name="rbac")
        self.install_screen(self.secrets_screen, name="secrets")
        self.install_screen(self.config_screen, name="config")
        self.install_screen(self.governance_screen, name="governance")
        self.install_screen(self.budgets_screen, name="budgets")
        self.install_screen(self.mcp_screen, name="mcp")
        self.install_screen(self.api_console_screen, name="api-console")

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

    def action_show_rbac(self) -> None:
        """Switch to RBAC screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("rbac")

    def action_show_secrets(self) -> None:
        """Switch to Secrets screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("secrets")

    def action_show_config(self) -> None:
        """Switch to Config screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("config")

    def action_show_governance(self) -> None:
        """Switch to Governance screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("governance")

    def action_show_budgets(self) -> None:
        """Switch to Budgets screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("budgets")

    def action_show_mcp(self) -> None:
        """Switch to MCP screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("mcp")

    def action_show_api_console(self) -> None:
        """Switch to API console screen."""
        if self.coordinator and self.coordinator.state in (
            TuiState.RUNNING,
            TuiState.DEGRADED,
        ):
            self.switch_screen("api-console")

    async def on_unmount(self) -> None:
        """Cleanup resources on exit."""
        if self.coordinator:
            await self.coordinator.stop()
        if not USE_MOCK and self._session is not None:
            await self._session.close()


def main() -> None:
    """Entry point for the application."""
    app = TalosTuiApp()
    app.run()
