"""
Integration tests for schema validation.

Verifies that Node-side schema validation (strict/warn/off modes) works
correctly when connected to a real Daemon.

Uses the real Node API:
  - node.schema_registry.register(topic, schema)
  - node.validation_mode = "strict"
"""

import asyncio

import pytest


@pytest.mark.integration
@pytest.mark.usefixtures("daemon")
class TestSchemaValidation:
    """Schema validation integration tests."""

    async def test_valid_payload_passes_strict(self, make_node):
        """A message matching the registered schema passes strict validation."""
        received = asyncio.Event()

        pub = await make_node("e2e_schema_pub")
        sub = await make_node("e2e_schema_sub")

        schema = {
            "type": "object",
            "properties": {
                "value": {"type": "integer"},
            },
            "required": ["value"],
        }
        pub.schema_registry.register("/test/e2e/typed", schema)
        pub.validation_mode = "strict"

        sub.schema_registry.register("/test/e2e/typed", schema)

        @sub.subscribe("/test/e2e/typed")
        async def on_msg(msg):  # noqa: ARG001
            received.set()

        await asyncio.sleep(0.3)

        # Valid payload — should pass
        await pub.publish("/test/e2e/typed", {"value": 42})
        await asyncio.wait_for(received.wait(), timeout=5.0)

    async def test_invalid_payload_rejected_strict(self, make_node):
        """A message NOT matching the schema is rejected in strict mode."""
        from tagentacle_py_core.schema import SchemaValidationError

        pub = await make_node("e2e_schema_strict")

        schema = {
            "type": "object",
            "properties": {
                "value": {"type": "integer"},
            },
            "required": ["value"],
        }
        pub.schema_registry.register("/test/e2e/strict_reject", schema)
        pub.validation_mode = "strict"

        with pytest.raises(SchemaValidationError):
            await pub.publish("/test/e2e/strict_reject", {"value": "not_an_int"})

    async def test_no_schema_no_validation(self, make_node):
        """Publishing to a topic with no registered schema always succeeds."""
        pub = await make_node("e2e_no_schema")
        sub = await make_node("e2e_no_schema_sub")

        received = asyncio.Event()

        @sub.subscribe("/test/e2e/untyped")
        async def on_msg(msg):  # noqa: ARG001
            received.set()

        await asyncio.sleep(0.3)

        # Any payload goes through
        await pub.publish("/test/e2e/untyped", {"anything": [1, "two", None]})
        await asyncio.wait_for(received.wait(), timeout=5.0)
