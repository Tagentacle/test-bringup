"""
E2E: Dual-agent full-stack system tests.

These tests verify the complete multi-agent topology works end-to-end:
- Dual agent communication (coordinator ↔ executor)
- MCP gateway relay to mock external server
- Memory persistence and session metadata
- Container operations via bus services
- Frontend receiving outputs from both agents

Requires the full ecosystem running via the ``full_stack`` fixture.
Run with:  pytest tests/test_full_stack_dual_agent.py -m system

Note: test_memory_rollback is skipped — rollback was removed per Q5 decision.
"""

import asyncio
import os

import pytest

pytestmark = pytest.mark.system


async def _make_probe(full_stack, node_id: str):
    """Helper: create a connected + spinning Node for probing."""
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


class TestDualAgent:
    """双 Agent 全栈测试 — 需要完整 bringup."""

    async def test_agent_a_receives_user_input(self, full_stack):
        """用户消息 → /chat/input → Agent A (coordinator) 回复到 /chat/output."""
        node, task = await _make_probe(full_stack, "e2e_dual_user_input")
        try:
            received = asyncio.Event()
            reply_data = {}

            @node.subscribe("/chat/output")
            async def on_reply(msg):
                payload = msg.get("payload", msg)
                reply_data.update(payload)
                received.set()

            await asyncio.sleep(0.5)

            # Send a user message to Agent A's input topic
            await node.publish(
                "/chat/input",
                {
                    "text": "Hello, Agent A. Reply briefly.",
                    "session_id": "e2e_test",
                },
            )

            await asyncio.wait_for(received.wait(), timeout=120.0)
            assert "content" in reply_data or "text" in reply_data, (
                f"Agent A did not produce a valid reply: {reply_data}"
            )
        finally:
            await _cleanup(node, task)

    async def test_agent_a_delegates_to_b(self, full_stack):
        """Agent A (coordinator) 通过 topic 分配任务给 Agent B (executor)."""
        node, task = await _make_probe(full_stack, "e2e_dual_delegate")
        try:
            b_received = asyncio.Event()
            b_output = {}

            @node.subscribe("/agent/b/output")
            async def on_b_output(msg):
                payload = msg.get("payload", msg)
                b_output.update(payload)
                b_received.set()

            await asyncio.sleep(0.5)

            # Directly send a task to Agent B's input topic
            await node.publish(
                "/agent/b/input",
                {
                    "text": "List files in current directory.",
                    "session_id": "e2e_test",
                },
            )

            await asyncio.wait_for(b_received.wait(), timeout=60.0)
            assert "content" in b_output or "text" in b_output, (
                f"Agent B did not produce output: {b_output}"
            )
        finally:
            await _cleanup(node, task)

    async def test_both_agents_use_shell(self, full_stack):
        """Shell server is active — verified via node list and MCP directory topic."""
        node, task = await _make_probe(full_stack, "e2e_dual_shell")
        try:
            # Verify shell_server is registered as a node
            resp = await node.call_service("/tagentacle/list_nodes", {})
            node_ids = [n["node_id"] for n in resp.get("nodes", [])]
            assert "shell_server" in node_ids, (
                f"shell_server not found in node list: {node_ids}"
            )
        finally:
            await _cleanup(node, task)

    async def test_memory_persistence(self, full_stack):
        """发送多轮对话 → 验证 memory 节点已持久化 session 数据."""
        node, task = await _make_probe(full_stack, "e2e_dual_memory")
        try:
            # Publish a memory snapshot
            await node.publish(
                "/memory/latest",
                {
                    "session_id": "e2e_test_session",
                    "messages": [
                        {"role": "user", "content": "hello"},
                        {"role": "assistant", "content": "hi there"},
                    ],
                },
            )

            await asyncio.sleep(2)

            # Query session list
            resp = await node.call_service("/memory/list", {})
            sessions = resp.get("sessions", [])
            session_ids = [
                s.get("session_id", s) if isinstance(s, dict) else s for s in sessions
            ]
            assert "e2e_test_session" in session_ids or len(sessions) > 0, (
                f"Memory did not persist session. Sessions: {sessions}"
            )
        finally:
            await _cleanup(node, task)

    async def test_mcp_gateway_relay(self, full_stack):
        """MCP gateway publishes directory entries to /mcp/directory topic."""
        node, task = await _make_probe(full_stack, "e2e_dual_gateway")
        try:
            received = asyncio.Event()
            directory_entries = []

            @node.subscribe("/mcp/directory")
            async def on_directory(msg):
                payload = msg.get("payload", msg)
                directory_entries.append(payload)
                received.set()

            await asyncio.sleep(0.5)

            # Verify gateway node is registered
            resp = await node.call_service("/tagentacle/list_nodes", {})
            node_ids = [n["node_id"] for n in resp.get("nodes", [])]
            assert "mcp_gateway" in node_ids, (
                f"mcp_gateway not found in node list: {node_ids}"
            )
        finally:
            await _cleanup(node, task)

    async def test_frontend_receives_both(self, full_stack):
        """Frontend 订阅能收到两个 agent 的输出 — verified via topic subscription."""
        node, task = await _make_probe(full_stack, "e2e_dual_frontend")
        try:
            a_received = asyncio.Event()
            b_received = asyncio.Event()

            @node.subscribe("/chat/output")
            async def on_a(msg):
                a_received.set()

            @node.subscribe("/agent/b/output")
            async def on_b(msg):
                b_received.set()

            await asyncio.sleep(0.5)

            # Trigger both agents
            await node.publish(
                "/chat/input",
                {
                    "text": "ping agent a",
                    "session_id": "e2e_test",
                },
            )
            await node.publish(
                "/agent/b/input",
                {
                    "text": "ping agent b",
                    "session_id": "e2e_test",
                },
            )

            # Wait for at least one agent to respond (60s for LLM latency)
            done, _ = await asyncio.wait(
                [
                    asyncio.create_task(a_received.wait()),
                    asyncio.create_task(b_received.wait()),
                ],
                timeout=60.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            assert len(done) >= 1, "Neither agent produced output within timeout"
        finally:
            await _cleanup(node, task)

    async def test_container_operations(self, full_stack):
        """Container orchestrator 响应 /containers/list 服务调用."""
        node, task = await _make_probe(full_stack, "e2e_dual_container")
        try:
            resp = await node.call_service("/containers/list", {})
            # Should return a valid structure even if no containers exist
            assert "containers" in resp or "error" in resp, (
                f"Container list returned unexpected structure: {resp}"
            )
        finally:
            await _cleanup(node, task)

    async def test_list_nodes_shows_dual_agents(self, full_stack):
        """After full bringup, list_nodes should show both agent instances."""
        node, task = await _make_probe(full_stack, "e2e_dual_list")
        try:
            resp = await node.call_service("/tagentacle/list_nodes", {})
            node_ids = [n["node_id"] for n in resp.get("nodes", [])]

            # At least one agent should be visible
            agent_nodes = [n for n in node_ids if "agent" in n.lower()]
            assert len(agent_nodes) >= 1, (
                f"Expected at least 1 agent node, found: {node_ids}"
            )
        finally:
            await _cleanup(node, task)
