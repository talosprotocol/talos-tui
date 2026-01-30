from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Digits
from textual.containers import Grid, Container, Vertical, Horizontal
from textual.reactive import reactive
import time

from talos_tui.core.state import StateStore, SourceState

class MetricCard(Container):
    """A premium card for displaying a single metric."""
    value = reactive("0")
    
    def __init__(self, title: str, id: str):
        self.title_text = title
        super().__init__(id=id)
        
    def compose(self) -> ComposeResult:
        yield Label(self.title_text, classes="metric-title")
        with Vertical(classes="metric-value-container"):
            yield Digits(self.value, id="metric_digits", classes="metric-value")
        
    def watch_value(self, new_value: str) -> None:
        try:
            self.query_one("#metric_digits", Digits).update(new_value)
        except Exception:
            pass
            
    def update_value(self, val: str) -> None:
        self.value = val

class StatusDashboard(Screen):
    def __init__(self, store: StateStore):
        super().__init__()
        self.store = store

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dashboard_container"):
            with Horizontal(id="top-bar"):
                yield Label("NETWORK STATUS OVERVIEW", classes="title")
                yield Label("", id="stale-banner", classes="stale-warning")
            
            with Grid():
                yield MetricCard("Connected Peers", id="peers")
                yield MetricCard("Active Sessions", id="sessions")
                yield MetricCard("Latency p50 (ms)", id="p50")
                yield MetricCard("Latency p95 (ms)", id="p95")
            
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
            self.query_one("#peers", MetricCard).update_value(str(m.get("connected_peers", 0)))
            self.query_one("#sessions", MetricCard).update_value(str(m.get("active_sessions", 0)))
            self.query_one("#p50", MetricCard).update_value(f"{m.get('latency_p50_ms', 0.0):.1f}")
            self.query_one("#p95", MetricCard).update_value(f"{m.get('latency_p95_ms', 0.0):.1f}")
            
            # Health indicators
            self._update_health("gw-health-status", self.store.gateway)
            self._update_health("audit-health-status", self.store.audit)
            
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
