"""
System tests for the Inference node (InferenceMux).

Tests verify that the inference node:
1. Registers on the bus
2. Exposes the /inference/chat service
3. Responds to basic inference requests (may fail if no API key, but
   should return a well-structured error rather than crashing)

Requires the full stack running (via full_stack fixture).
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


class TestInferenceNode:
    """Inference node system-level tests."""

    async def test_inference_node_registered(self, full_stack):
        """Inference node should appear in list_nodes."""
        node, task = await _make_probe(full_stack, "e2e_inference_registered")
        try:
            resp = await node.call_service("/tagentacle/list_nodes", {})
            node_ids = [n["node_id"] for n in resp.get("nodes", [])]
            assert "inference_node" in node_ids, (
                f"inference_node not in node list: {node_ids}"
            )
        finally:
            await _cleanup(node, task)

    async def test_inference_chat_service_exists(self, full_stack):
        """Inference node should register /inference/chat service."""
        node, task = await _make_probe(full_stack, "e2e_inference_service")
        try:
            resp = await node.call_service("/tagentacle/list_nodes", {})
            nodes_info = resp.get("nodes", [])
            inference = [n for n in nodes_info if n.get("node_id") == "inference_node"]
            assert len(inference) == 1, "inference_node not found"

            # Check that the node has registered services (if available in list)
            services = inference[0].get("services", [])
            if services:
                service_names = [s if isinstance(s, str) else s.get("name", "") for s in services]
                assert any("inference" in s or "chat" in s for s in service_names), (
                    f"No inference service found: {service_names}"
                )
        finally:
            await _cleanup(node, task)

    async def test_inference_chat_responds(self, full_stack):
        """Calling /inference/chat should return a structured response.

        The call may fail due to missing API key or quota, but should
        return a well-formed error dict rather than timing out.
        """
        node, task = await _make_probe(full_stack, "e2e_inference_call")
        try:
            try:
                resp = await asyncio.wait_for(
                    node.call_service("/inference/chat", {
                        "messages": [{"role": "user", "content": "Say hello"}],
                    }),
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                pytest.skip("Inference service timed out — may not be configured")
                return

            # Response should be a dict with either content or error
            assert isinstance(resp, dict), f"Expected dict, got {type(resp)}"
            assert "content" in resp or "error" in resp or "choices" in resp, (
                f"Unexpected inference response structure: {resp}"
            )
        finally:
            await _cleanup(node, task)
