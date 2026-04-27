from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Digits
from textual.containers import Grid, Container, Vertical, Horizontal
from textual.reactive import reactive

from talos_tui.core.state import StateStore, SourceState


class MetricCard(Container):
    """A premium card for displaying a single metric."""
    value = reactive("—")

    def __init__(self, title: str, id: str):
        self.title_text = title
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        yield Label(self.title_text.upper(), classes="metric-title")
        yield Label(self.value, classes="metric-value")

    def watch_value(self, new_value: str) -> None:
        try:
            w = self.query_one(".metric-value", Label)
            w.update(new_value)
            
            # Apply dynamic coloring
            if self.id == "threat_level":
                w.set_classes("metric-value " + (
                    "red" if new_value == "CRITICAL" else "amber" if new_value == "ELEVATED" else "green"
                ))
            elif self.id == "success_rate":
                try:
                    num = float(new_value)
                    w.set_classes("metric-value " + (
                        "green" if num > 95 else "amber" if num > 85 else "red"
                    ))
                except ValueError:
                    pass
        except Exception:
            pass

    def update_value(self, val: str) -> None:
        self.value = val


class StatusDashboard(Screen[None]):
    def __init__(self, store: StateStore):
        super().__init__()
        self.store = store

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dashboard_container"):
            with Horizontal(id="top-bar"):
                yield Label("NETWORK STATUS OVERVIEW", classes="title")
                with Horizontal(id="banners"):
                    yield Label("", id="stale-banner", classes="stale-warning")
                    yield Label("", id="security-alert", classes="security-warning")

            with Grid():
                yield MetricCard("Connected Peers", id="peers")
                yield MetricCard("Active Sessions", id="sessions")
                yield MetricCard("Latency p50 (ms)", id="p50")
                yield MetricCard("Latency p95 (ms)", id="p95")
                yield MetricCard("Success Rate (%)", id="success_rate")
                yield MetricCard("Threat Level", id="threat_level")

            with Horizontal(id="health-bar"):
                yield Label("GW: ", classes="health-label")
                yield Label("UNKNOWN", id="gw-health-status")
                yield Label(" | AUDIT: ", classes="health-label")
                yield Label("UNKNOWN", id="audit-health-status")

        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_view)

    def refresh_view(self) -> None:
        """Project current StateStore to UI"""
        m = self.store.metrics
        try:
            self.query_one("#peers", MetricCard).update_value(
                str(m.get("connected_peers", 0))
            )
            self.query_one("#sessions", MetricCard).update_value(
                str(m.get("active_sessions", 0))
            )
            self.query_one("#p50", MetricCard).update_value(
                f"{m.get('latency_p50_ms', 0.0):.1f}"
            )
            self.query_one("#p95", MetricCard).update_value(
                f"{m.get('latency_p95_ms', 0.0):.1f}"
            )

            # Success Rate and Threat Level
            success_rate = m.get("auth_success_rate", 1.0) * 100
            self.query_one("#success_rate", MetricCard).update_value(
                f"{success_rate:.1f}"
            )

            denial_rate = 100 - success_rate
            threat_level = "SECURE"
            if denial_rate > 15:
                threat_level = "CRITICAL"
            elif denial_rate > 5:
                threat_level = "ELEVATED"
            
            self.query_one("#threat_level", MetricCard).update_value(threat_level)

            # Health indicators
            self._update_health("gw-health-status", self.store.gateway)
            self._update_health("audit-health-status", self.store.audit)

            # Security Alert
            has_tampered = any(e.get("integrity", {}).get("failure_reason") == "CURSOR_MISMATCH" for e in self.store.audit_events)
            alert = self.query_one("#security-alert", Label)
            if threat_level == "CRITICAL" or has_tampered:
                alert.update("⚠️ SECURITY ALERT: COMPROMISE DETECTED")
                alert.display = True
            elif threat_level == "ELEVATED":
                alert.update("⚠️ ELEVATED THREAT LEVEL")
                alert.display = True
            else:
                alert.display = False

            # Stale banner
            gw_age = self.store.get_stale_since("gateway")
            if gw_age > 5.0 and gw_age != float('inf'):
                banner = self.query_one("#stale-banner", Label)
                banner.update(f"STALE DATA ({int(gw_age)}s old)")
                banner.display = True
            else:
                self.query_one("#stale-banner", Label).display = False

        except Exception:
            pass

    def _update_health(self, widget_id: str, state: SourceState) -> None:
        w = self.query_one(f"#{widget_id}", Label)
        if state.health_ok:
            w.update("ONLINE")
            w.styles.color = "green"
        else:
            w.update("OFFLINE" if state.error else "PENDING")
            w.styles.color = "red"
