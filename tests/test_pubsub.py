"""
Integration tests for Topic Pub/Sub.

Verifies that messages published to a topic are delivered to all subscribers
through the real Tagentacle daemon.

Uses the real Node API:
  - node.subscribe(topic)(callback)   — decorator/callable style
  - await node.publish(topic, payload)
  - spin() runs in background via make_node fixture
"""

import asyncio

import pytest


@pytest.mark.integration
@pytest.mark.usefixtures("daemon")
class TestPubSub:
    """Basic publish-subscribe round-trip tests."""

    async def test_single_subscriber_receives_message(self, make_node):
        """Publish one message, verify one subscriber receives it."""
        received = asyncio.Event()
        received_data = {}

        pub = await make_node("e2e_pub_1")
        sub = await make_node("e2e_sub_1")

        @sub.subscribe("/test/e2e/basic")
        async def on_message(msg):
            payload = msg.get("payload", msg)
            received_data.update(payload)
            received.set()

        # Small delay to let subscription propagate through daemon
        await asyncio.sleep(0.3)

        await pub.publish("/test/e2e/basic", {"hello": "world", "seq": 1})

        await asyncio.wait_for(received.wait(), timeout=5.0)
        assert received_data["hello"] == "world"
        assert received_data["seq"] == 1

    async def test_multiple_subscribers(self, make_node):
        """Publish one message, verify all subscribers receive it."""
        count = 3
        events = [asyncio.Event() for _ in range(count)]

        pub = await make_node("e2e_pub_multi")
        subs = []
        for i in range(count):
            sub = await make_node(f"e2e_sub_multi_{i}")
            idx = i  # capture

            @sub.subscribe("/test/e2e/multi")
            async def on_msg(msg, _idx=idx):
                events[_idx].set()

            subs.append(sub)

        await asyncio.sleep(0.3)
        await pub.publish("/test/e2e/multi", {"fanout": True})

        await asyncio.wait_for(
            asyncio.gather(*(e.wait() for e in events)),
            timeout=5.0,
        )
        assert all(e.is_set() for e in events)

    async def test_no_cross_topic_delivery(self, make_node):
        """Messages on topic A should NOT be delivered to topic B subscribers."""
        wrong_topic_received = asyncio.Event()

        pub = await make_node("e2e_pub_iso")
        sub = await make_node("e2e_sub_iso")

        @sub.subscribe("/test/e2e/topic_b")
        async def should_not_fire(msg):
            wrong_topic_received.set()

        await asyncio.sleep(0.3)

        await pub.publish("/test/e2e/topic_a", {"data": "for_a_only"})

        # Wait a bit — the callback should NOT fire
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(wrong_topic_received.wait(), timeout=1.0)

    async def test_many_messages_ordered(self, make_node):
        """Publish N messages and verify they arrive in order."""
        n = 50
        received_seqs = []
        done = asyncio.Event()

        pub = await make_node("e2e_pub_order")
        sub = await make_node("e2e_sub_order")

        @sub.subscribe("/test/e2e/order")
        async def on_msg(msg):
            payload = msg.get("payload", msg)
            received_seqs.append(payload["seq"])
            if len(received_seqs) >= n:
                done.set()

        await asyncio.sleep(0.3)

        for i in range(n):
            await pub.publish("/test/e2e/order", {"seq": i})

        await asyncio.wait_for(done.wait(), timeout=10.0)
        assert received_seqs == list(range(n))
