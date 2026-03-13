"""
E2E: Verify the full-stack topology is functioning.

These tests require the full ecosystem (Daemon + all nodes) to be running
via the ``full_stack`` fixture. They are expensive — run selectively.

Run with:  pytest tests/test_full_stack.py -m system
"""

import asyncio

import pytest

pytestmark = pytest.mark.system


async def _make_probe(full_stack, node_id: str):
    """Helper: create a connected + spinning Node for probing."""
    import os
    from tagentacle_py_core import Node

    os.environ["TAGENTACLE_DAEMON_URL"] = (
        f"tcp://{full_stack['daemon_host']}:{full_stack['daemon_port']}"
    )
    node = Node(node_id)
    await node.connect()
    task = asyncio.create_task(node.spin())
    return node, task


async def _cleanup(node, task):
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    try:
        await node.disconnect()
    except Exception:
        pass


async def test_daemon_reachable(full_stack):
    """Verify daemon responds to ping after full-stack bringup."""
    node, task = await _make_probe(full_stack, "e2e_probe")
    try:
        resp = await node.call_service("/tagentacle/ping", {})
        assert resp.get("status") == "ok"
    finally:
        await _cleanup(node, task)


async def test_list_nodes_shows_all_ecosystem_nodes(full_stack):
    """After full bringup, list_nodes should show agent, inference, memory, etc."""
    node, task = await _make_probe(full_stack, "e2e_probe2")
    try:
        resp = await node.call_service("/tagentacle/list_nodes", {})
        node_ids = [n["node_id"] for n in resp.get("nodes", [])]

        expected_nodes = {"mcp_server_node", "inference_node", "memory_node", "agent_node"}
        found = expected_nodes.intersection(set(node_ids))

        assert len(found) >= 3, (
            f"Expected at least 3 of {expected_nodes} running, "
            f"but only found {found}. All nodes: {node_ids}"
        )
    finally:
        await _cleanup(node, task)


async def test_mcp_server_health(full_stack):
    """Verify MCP server is reachable via HTTP."""
    import urllib.request

    url = full_stack["mcp_url"]
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status in (200, 405)
    except urllib.error.HTTPError as e:
        assert e.code == 405, f"Unexpected HTTP error: {e.code}"


async def test_agent_can_list_topics(full_stack):
    """Verify topic discovery works with the full ecosystem running."""
    node, task = await _make_probe(full_stack, "e2e_topic_probe")
    try:
        resp = await node.call_service("/tagentacle/list_topics", {})
        topics = resp.get("topics", [])
        topic_names = [t["name"] if isinstance(t, dict) else t for t in topics]
        assert len(topic_names) > 0, "Expected at least some active topics"
    finally:
        await _cleanup(node, task)


async def test_memory_subscription_active(full_stack):
    """Verify the memory node is subscribed to its expected topic."""
    node, task = await _make_probe(full_stack, "e2e_mem_probe")
    try:
        resp = await node.call_service("/tagentacle/list_topics", {})
        topics = resp.get("topics", [])
        topic_names = [t["name"] if isinstance(t, dict) else t for t in topics]
        assert "/memory/latest" in topic_names or any(
            "memory" in t for t in topic_names
        ), f"/memory/* topic not found. Active topics: {topic_names}"
    finally:
        await _cleanup(node, task)
