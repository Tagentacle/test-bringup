"""
Shared fixtures for Tagentacle end-to-end tests.

The key fixture is `daemon` — it starts a real tagentacle daemon process,
waits until it's accepting connections, and tears it down after the test
session. All tests in this suite talk to a real daemon, not mocks.
"""

import asyncio
import os
import shutil
import signal
import subprocess
import time

import pytest


def _find_daemon_binary() -> str:
    """Locate the tagentacle daemon binary.

    Search order:
    1. TAGENTACLE_BIN environment variable
    2. Workspace release build: ../tagentacle/target/release/tagentacle
    3. Workspace debug build: ../tagentacle/target/debug/tagentacle
    4. System PATH: `tagentacle`
    """
    env_bin = os.environ.get("TAGENTACLE_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin

    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for profile in ("release", "debug"):
        candidate = os.path.join(workspace_root, "tagentacle", "target", profile, "tagentacle")
        if os.path.isfile(candidate):
            return candidate

    system_bin = shutil.which("tagentacle")
    if system_bin:
        return system_bin

    pytest.skip("tagentacle daemon binary not found — set TAGENTACLE_BIN or build with cargo")


def _wait_for_port(host: str, port: int, timeout: float = 10.0):
    """Block until a TCP port is accepting connections."""
    import socket

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Daemon did not start on {host}:{port} within {timeout}s")


@pytest.fixture(scope="session")
def daemon_binary() -> str:
    """Return the path to the daemon binary."""
    return _find_daemon_binary()


@pytest.fixture(scope="session")
def daemon_host() -> str:
    return os.environ.get("TAGENTACLE_HOST", "127.0.0.1")


@pytest.fixture(scope="session")
def daemon_port() -> int:
    return int(os.environ.get("TAGENTACLE_PORT", "19999"))


@pytest.fixture(scope="session")
def daemon(daemon_binary, daemon_host, daemon_port):
    """Start a real tagentacle daemon for the entire test session.

    Yields the subprocess.Popen object. Kills the daemon after all tests.
    """
    proc = subprocess.Popen(
        [daemon_binary, "daemon", "--addr", f"{daemon_host}:{daemon_port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_port(daemon_host, daemon_port, timeout=15.0)
    except TimeoutError:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        pytest.fail(
            f"Daemon failed to start.\n"
            f"stdout: {stdout.decode(errors='replace')}\n"
            f"stderr: {stderr.decode(errors='replace')}"
        )

    yield proc

    # Graceful shutdown
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture
async def make_node(daemon_host, daemon_port):
    """Factory fixture that creates connected Nodes and cleans them up.

    Usage:
        async def test_something(make_node):
            node = await make_node("my_test_node")
            ...
    """
    from tagentacle_py_core import Node

    nodes = []

    async def _factory(node_id: str, **kwargs) -> Node:
        node = Node(node_id, host=daemon_host, port=daemon_port, **kwargs)
        await node.start()
        nodes.append(node)
        return node

    yield _factory

    # Teardown all created nodes
    for node in nodes:
        try:
            await node.stop()
        except Exception:
            pass
