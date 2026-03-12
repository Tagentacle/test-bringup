"""
End-to-end tests for node events.

Verifies that the Daemon publishes connect/disconnect events to
/tagentacle/node_events when nodes join or leave.
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

        async def on_event(msg):
            events.append(msg)
            if msg.get("event") == "connected" and msg.get("node_id") == "e2e_newcomer":
                done.set()

        await observer.subscribe("/tagentacle/node_events", on_event)
        await asyncio.sleep(0.2)

        # New node connects — should trigger event
        newcomer = await make_node("e2e_newcomer")

        await asyncio.wait_for(done.wait(), timeout=5.0)
        matching = [e for e in events if e.get("node_id") == "e2e_newcomer" and e.get("event") == "connected"]
        assert len(matching) >= 1

    async def test_node_disconnect_event(self, make_node, daemon_host, daemon_port):
        """When a node disconnects, /tagentacle/node_events should fire."""
        from tagentacle_py_core import Node

        events = []
        done = asyncio.Event()

        observer = await make_node("e2e_dc_observer")

        async def on_event(msg):
            events.append(msg)
            if msg.get("event") == "disconnected" and msg.get("node_id") == "e2e_leaver":
                done.set()

        await observer.subscribe("/tagentacle/node_events", on_event)
        await asyncio.sleep(0.2)

        # Create and immediately stop a node
        leaver = Node("e2e_leaver", host=daemon_host, port=daemon_port)
        await leaver.start()
        await asyncio.sleep(0.2)
        await leaver.stop()

        await asyncio.wait_for(done.wait(), timeout=10.0)
        matching = [e for e in events if e.get("node_id") == "e2e_leaver" and e.get("event") == "disconnected"]
        assert len(matching) >= 1
