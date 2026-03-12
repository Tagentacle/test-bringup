"""
Fixtures for E2E (full-stack) tests.

These tests start the ENTIRE Tagentacle ecosystem via the bringup launcher:
  Daemon → MCP Server → Inference → Memory → Agent → Frontend

This is heavier than integration tests. CI should run these selectively.
"""

import asyncio
import os
import signal
import subprocess
import sys
import time

import pytest


def _find_bringup_launcher() -> tuple[str, str]:
    """Locate the example-bringup launcher and config.

    Returns (launcher_script, config_path).
    """
    workspace = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    launcher = os.path.join(workspace, "example-bringup", "launch", "system_launch.py")
    config = os.path.join(workspace, "example-bringup", "launch", "system_launch.toml")

    if not os.path.isfile(launcher):
        pytest.skip(f"example-bringup not found at {launcher}")
    if not os.path.isfile(config):
        pytest.skip(f"launch config not found at {config}")

    return launcher, config


@pytest.fixture(scope="session")
def full_stack():
    """Start the full Tagentacle ecosystem via example-bringup launcher.

    This is an expensive fixture — it launches:
      - Daemon
      - MCP Server (weather)
      - Inference node
      - Memory node
      - Agent node
      - Frontend (Gradio)

    Yields a dict with connection info, then tears down everything.
    """
    launcher, config = _find_bringup_launcher()

    # Check for required secrets (API keys etc)
    workspace = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    secrets_path = os.path.join(workspace, "example-bringup", "config", "secrets.toml")
    if not os.path.isfile(secrets_path):
        pytest.skip(
            f"E2E requires secrets.toml at {secrets_path}. "
            "Copy from secrets.toml.example and fill in API keys."
        )

    proc = subprocess.Popen(
        [sys.executable, launcher, config],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.path.join(workspace, "example-bringup"),
    )

    # Wait for the full stack to come up — this takes a while
    # We check that the daemon port AND the MCP server port are reachable
    import socket

    def _wait_port(host, port, timeout=30.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=1.0):
                    return True
            except OSError:
                time.sleep(0.5)
        return False

    daemon_ok = _wait_port("127.0.0.1", 19999, timeout=30)
    mcp_ok = _wait_port("127.0.0.1", 8200, timeout=45)

    if not daemon_ok or not mcp_ok:
        proc.kill()
        stdout = proc.communicate(timeout=10)[0]
        pytest.fail(
            f"Full stack failed to start (daemon={daemon_ok}, mcp={mcp_ok}).\n"
            f"Output:\n{stdout.decode(errors='replace')[-2000:]}"
        )

    yield {
        "daemon_host": "127.0.0.1",
        "daemon_port": 19999,
        "mcp_url": "http://127.0.0.1:8200/mcp",
    }

    # Graceful shutdown
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
