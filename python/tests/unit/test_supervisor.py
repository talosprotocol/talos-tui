import pytest
import asyncio
from unittest.mock import MagicMock
from talos_tui.core.coordinator import Coordinator
from talos_tui.core.state import StateStore

@pytest.mark.asyncio
async def test_coordinator_lifecycle():
    store = StateStore()
    gateway = MagicMock()
    audit = MagicMock()
    coord = Coordinator(store, gateway, audit)
    
    # Start (mocks handshake loop)
    # We don't want the infinite loop to block, so we'll mock spawn or make handshake exit
    coord.spawn = MagicMock() 
    
    await coord.start()
    assert coord.state.name == "HANDSHAKE_GATEWAY"
    
    await coord.stop()
    assert coord._stop_event.is_set()

@pytest.mark.asyncio
async def test_coordinator_task_management():
    store = StateStore()
    coord = Coordinator(store, MagicMock(), MagicMock())
    
    # Use the real spawn method
    async def dummy():
        await asyncio.sleep(0.01)
    
    task = coord.spawn(dummy())
    assert task in coord._tasks
    assert not task.done()
    
    await asyncio.sleep(0.02)
    assert task not in coord._tasks  # Should be discarded on done
