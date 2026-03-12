"""
End-to-end tests for Service RPC.

Verifies that service calls go through the Daemon and return correct responses.
Covers both user-defined services and Daemon system services.
"""

import asyncio

import pytest


@pytest.mark.usefixtures("daemon")
class TestServiceRPC:
    """Service call/response round-trip tests."""

    async def test_system_service_ping(self, make_node):
        """Daemon system service /tagentacle/ping should always respond."""
        node = await make_node("e2e_ping")
        result = await node.call_service("/tagentacle/ping", {})

        assert "status" in result
        assert result["status"] == "ok"
        assert "uptime_s" in result
        assert "version" in result

    async def test_system_service_list_nodes(self, make_node):
        """list_nodes should include our test node."""
        node = await make_node("e2e_list_nodes_test")
        result = await node.call_service("/tagentacle/list_nodes", {})

        assert "nodes" in result
        node_ids = [n["node_id"] for n in result["nodes"]]
        assert "e2e_list_nodes_test" in node_ids

    async def test_system_service_list_topics(self, make_node):
        """After subscribing to a topic, list_topics should include it."""
        node = await make_node("e2e_list_topics_test")
        await node.subscribe("/test/e2e/listed_topic", lambda msg: None)
        await asyncio.sleep(0.1)

        result = await node.call_service("/tagentacle/list_topics", {})
        assert "topics" in result
        topic_names = [t["name"] for t in result["topics"]]
        assert "/test/e2e/listed_topic" in topic_names

    async def test_user_defined_service(self, make_node):
        """A node can advertise a service and another node can call it."""
        server = await make_node("e2e_svc_server")
        client = await make_node("e2e_svc_client")

        async def handler(request):
            return {"sum": request["a"] + request["b"]}

        await server.advertise_service("/test/e2e/add", handler)
        await asyncio.sleep(0.1)

        result = await client.call_service("/test/e2e/add", {"a": 3, "b": 7})
        assert result["sum"] == 10
