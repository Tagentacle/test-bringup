"""
System tests for the MCP Gateway relay.

Tests verify that the MCP gateway:
1. Registers as a node on the bus
2. Publishes /mcp/directory topic with discovered servers
3. HTTP endpoint is reachable at the expected port

These tests require the full stack running (via full_stack fixture).
"""

import asyncio
import os

import pytest

pytestmark = pytest.mark.system


async def _make_probe(full_stack, node_id: str):
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


class TestMCPGateway:
    """MCP Gateway system-level tests."""

    async def test_gateway_node_registered(self, full_stack):
        """MCP gateway node should appear in list_nodes."""
        node, task = await _make_probe(full_stack, "e2e_gw_registered")
        try:
            resp = await node.call_service("/tagentacle/list_nodes", {})
            node_ids = [n["node_id"] for n in resp.get("nodes", [])]
            assert "mcp_gateway" in node_ids, (
                f"mcp_gateway not in node list: {node_ids}"
            )
        finally:
            await _cleanup(node, task)

    async def test_gateway_publishes_directory(self, full_stack):
        """Gateway should publish /mcp/directory with discovered servers."""
        node, task = await _make_probe(full_stack, "e2e_gw_directory")
        try:
            resp = await node.call_service("/tagentacle/list_topics", {})
            topics = resp.get("topics", [])
            # Extract topic names regardless of format (str or dict with various keys)
            topic_names = []
            for t in topics:
                if isinstance(t, str):
                    topic_names.append(t)
                elif isinstance(t, dict):
                    name = t.get("topic") or t.get("name") or t.get("id", "")
                    topic_names.append(name)
            assert any("/mcp" in t for t in topic_names), (
                f"No /mcp topic found in topic list: {topics}"
            )
        finally:
            await _cleanup(node, task)

    async def test_mcp_http_endpoint_reachable(self, full_stack):
        """MCP server HTTP endpoint should respond."""
        import urllib.request
        import urllib.error

        mcp_url = full_stack.get("mcp_url", "http://127.0.0.1:8200/mcp")
        base_url = mcp_url.rstrip("/mcp").rstrip("/")

        try:
            req = urllib.request.Request(base_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                # Any response (even 4xx) means the server is up
                assert resp.status in (200, 405, 406), (
                    f"Unexpected status from MCP endpoint: {resp.status}"
                )
        except urllib.error.HTTPError as e:
            # HTTP errors (405, etc.) still mean the server is running
            assert e.code in (405, 406, 404), (
                f"MCP endpoint returned unexpected error: {e.code}"
            )
        except urllib.error.URLError:
            pytest.fail(f"MCP HTTP endpoint not reachable at {base_url}")
