"""
Integration tests for container-orchestrator.

Tests the ContainerRuntime abstraction and ContainerOrchestrator's
container operations when a real container runtime is available.

Requires: Podman/Docker installed AND podman-py/docker-py Python SDK.
Skip gracefully if no container runtime is detected.
"""

import pytest

# Skip entire module if container runtime is not usable
pytestmark = pytest.mark.integration


def _runtime_available() -> bool:
    """Check if ContainerRuntime can actually connect."""
    try:
        from container_runtime import ContainerRuntime

        rt = ContainerRuntime.connect()
        rt.close()
        return True
    except Exception:
        return False


skip_no_runtime = pytest.mark.skipif(
    not _runtime_available(),
    reason="Container runtime not available (need podman-py or docker-py + running daemon)",
)


class TestContainerRuntimeImport:
    """Import-only tests (no runtime needed)."""

    def test_import(self):
        """Verify the ContainerRuntime can be imported."""
        container_runtime = pytest.importorskip(
            "container_runtime",
            reason="container-orchestrator not installed",
        )
        assert hasattr(container_runtime, "ContainerRuntime")
        assert hasattr(container_runtime, "ContainerInfo")
        assert hasattr(container_runtime, "ExecResult")

    def test_orchestrator_import(self):
        """Verify ContainerOrchestrator can be imported."""
        orch_mod = pytest.importorskip(
            "orchestrator",
            reason="container-orchestrator not installed",
        )
        assert hasattr(orch_mod, "ContainerOrchestrator")


@skip_no_runtime
class TestContainerRuntime:
    """Tests for the ContainerRuntime abstraction layer."""

    def test_connect(self):
        """Verify we can connect to the auto-detected runtime."""
        cr = pytest.importorskip("container_runtime")
        rt = cr.ContainerRuntime.connect()
        assert rt.backend in ("podman", "docker")
        rt.close()

    def test_info(self):
        """Verify runtime info returns expected fields."""
        cr = pytest.importorskip("container_runtime")
        rt = cr.ContainerRuntime.connect()
        try:
            info = rt.info()
            assert isinstance(info, dict)
        finally:
            rt.close()

    def test_list_empty_filter(self):
        """List with a non-matching filter returns empty."""
        cr = pytest.importorskip("container_runtime")
        rt = cr.ContainerRuntime.connect()
        try:
            containers = rt.list(
                filters={"label": "tagentacle.test.nonexistent=true"}
            )
            assert isinstance(containers, list)
            assert len(containers) == 0
        finally:
            rt.close()


@skip_no_runtime
class TestContainerLifecycle:
    """Full container lifecycle tests (create → exec → stop → remove).

    These tests pull/use alpine:latest and create actual containers.
    Marked slow because they may need to pull the image.
    """

    @pytest.mark.slow
    def test_full_lifecycle(self):
        """Create → list → exec → stop → remove a container."""
        cr = pytest.importorskip("container_runtime")
        rt = cr.ContainerRuntime.connect()
        test_name = "tagentacle_test_lifecycle"

        # Ensure the image is available locally
        try:
            rt.client.images.pull("alpine:latest")
        except Exception:
            pytest.skip("Cannot pull alpine:latest (network unavailable?)")

        try:
            # Create
            container = rt.create(
                "alpine:latest",
                command=["sleep", "300"],
                name=test_name,
                labels={"tagentacle.managed": "true", "tagentacle.test": "true"},
            )
            assert container.name == test_name
            assert container.id

            # List — should include our container
            containers = rt.list(filters={"label": "tagentacle.test=true"})
            names = [c.name for c in containers]
            assert test_name in names

            # Exec
            result = rt.exec(test_name, "echo hello-from-test")
            assert result.exit_code == 0
            assert "hello-from-test" in result.stdout

            # Stop
            rt.stop(test_name, timeout=5)

            # Remove
            rt.remove(test_name, force=True)

            # Verify removed
            containers = rt.list(all=True, filters={"label": "tagentacle.test=true"})
            names = [c.name for c in containers]
            assert test_name not in names

        except Exception:
            # Cleanup on failure
            try:
                rt.remove(test_name, force=True)
            except Exception:
                pass
            raise
        finally:
            rt.close()


@skip_no_runtime
class TestOrchestratorOperations:
    """Test the orchestrator's sync container operation methods directly.

    These test the internal _create_container / _list_containers / etc.
    methods without the bus, verifying the business logic layer.
    """

    def test_create_missing_image(self):
        """_create_container returns error when image is missing."""
        pytest.importorskip("container_runtime")
        orch_mod = pytest.importorskip(
            "orchestrator", reason="container-orchestrator not installed"
        )
        orch = orch_mod.ContainerOrchestrator("test_orch_ops")

        # Connect runtime manually (bypass lifecycle)
        from container_runtime import ContainerRuntime

        orch.runtime = ContainerRuntime.connect()
        try:
            result = orch._create_container({})
            assert "error" in result
            assert "image" in result["error"].lower()
        finally:
            orch.runtime.close()

    def test_stop_missing_id(self):
        """_stop_container returns error when name/id is missing."""
        pytest.importorskip("container_runtime")
        orch_mod = pytest.importorskip("orchestrator")
        orch = orch_mod.ContainerOrchestrator("test_orch_stop")

        from container_runtime import ContainerRuntime

        orch.runtime = ContainerRuntime.connect()
        try:
            result = orch._stop_container({})
            assert "error" in result
        finally:
            orch.runtime.close()

    def test_remove_missing_id(self):
        """_remove_container returns error when name/id is missing."""
        pytest.importorskip("container_runtime")
        orch_mod = pytest.importorskip("orchestrator")
        orch = orch_mod.ContainerOrchestrator("test_orch_rm")

        from container_runtime import ContainerRuntime

        orch.runtime = ContainerRuntime.connect()
        try:
            result = orch._remove_container({})
            assert "error" in result
        finally:
            orch.runtime.close()

    def test_list_containers(self):
        """_list_containers returns a valid list structure."""
        pytest.importorskip("container_runtime")
        orch_mod = pytest.importorskip("orchestrator")
        orch = orch_mod.ContainerOrchestrator("test_orch_list")

        from container_runtime import ContainerRuntime

        orch.runtime = ContainerRuntime.connect()
        try:
            result = orch._list_containers({})
            assert "containers" in result
            assert "count" in result
            assert isinstance(result["containers"], list)
        finally:
            orch.runtime.close()

    def test_exec_missing_command(self):
        """_exec_in_container returns error when command is missing."""
        pytest.importorskip("container_runtime")
        orch_mod = pytest.importorskip("orchestrator")
        orch = orch_mod.ContainerOrchestrator("test_orch_exec")

        from container_runtime import ContainerRuntime

        orch.runtime = ContainerRuntime.connect()
        try:
            result = orch._exec_in_container({"name": "x"})
            assert "error" in result
            assert "command" in result["error"].lower()
        finally:
            orch.runtime.close()
