"""
Integration tests for node events.

Verifies that the Daemon publishes connect/disconnect events to
/tagentacle/node_events when nodes join or leave.

Uses the real Node API:
  - node.subscribe(topic)(callback)
  - node.connect() / node.disconnect()
"""

import asyncio

import pytest


@pytest.mark.usefixtures("daemon")
class TestNodeEvents:
    """Node lifecycle event tests."""

    async def test_node_connect_event(self, make_node):
        """When a new node connects, /tagentacle/node_events should fire."""
        events = []
        done = asyncio.Event()

        # Observer subscribes to node events
        observer = await make_node("e2e_event_observer")

        @observer.subscribe("/tagentacle/node_events")
        async def on_event(msg):
            payload = msg.get("payload", msg)
            events.append(payload)
            if (
                payload.get("event") == "connected"
                and payload.get("node_id") == "e2e_newcomer"
            ):
                done.set()

        await asyncio.sleep(0.3)

        # New node connects — should trigger event
        _newcomer = await make_node("e2e_newcomer")

        await asyncio.wait_for(done.wait(), timeout=5.0)
        matching = [
            e
            for e in events
            if e.get("node_id") == "e2e_newcomer" and e.get("event") == "connected"
        ]
        assert len(matching) >= 1

    async def test_node_disconnect_event(self, make_node):
        """When a node disconnects, /tagentacle/node_events should fire."""
        from tagentacle_py_core import Node

        events = []
        done = asyncio.Event()

        observer = await make_node("e2e_dc_observer")

        @observer.subscribe("/tagentacle/node_events")
        async def on_event(msg):
            payload = msg.get("payload", msg)
            events.append(payload)
            if (
                payload.get("event") == "disconnected"
                and payload.get("node_id") == "e2e_leaver"
            ):
                done.set()

        await asyncio.sleep(0.3)

        # Create a node, connect, then disconnect
        leaver = Node("e2e_leaver")
        await leaver.connect()
        await asyncio.sleep(0.3)
        await leaver.disconnect()

        await asyncio.wait_for(done.wait(), timeout=10.0)
        matching = [
            e
            for e in events
            if e.get("node_id") == "e2e_leaver"
            and e.get("event") in ("disconnected", "unregistered")
        ]
        assert len(matching) >= 1
