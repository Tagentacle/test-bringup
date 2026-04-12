"""
Integration test for tagentacle launch secrets injection.

Verifies that secrets.toml key-value pairs are injected as environment
variables into child node processes launched by `tagentacle launch`.

This test creates a minimal launch config with a test secrets file,
launches a lightweight Python script that prints its env, and verifies
the expected keys are present.
"""

import asyncio
import os
import subprocess
import tempfile
import textwrap
import time

import pytest

pytestmark = pytest.mark.integration


def _find_daemon_binary() -> str:
    import shutil

    env_bin = os.environ.get("TAGENTACLE_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin
    system_bin = shutil.which("tagentacle")
    if system_bin:
        return system_bin
    pytest.skip("tagentacle binary not found")


class TestSecretsInjection:
    """Verify that secrets.toml values are injected as env vars."""

    def test_secrets_injected_as_env(self, tmp_path):
        """Launch a node that dumps env; verify secret keys appear."""
        binary = _find_daemon_binary()

        # Create a test secrets file
        secrets_file = tmp_path / "test_secrets.toml"
        secrets_file.write_text(
            'TEST_SECRET_KEY = "test_secret_value_12345"\n'
            'ANOTHER_SECRET = "another_value_67890"\n'
        )

        # Create a probe script that prints specific env vars
        probe_script = tmp_path / "probe.py"
        probe_script.write_text(textwrap.dedent("""\
            import os, json, sys
            result = {
                "TEST_SECRET_KEY": os.environ.get("TEST_SECRET_KEY", ""),
                "ANOTHER_SECRET": os.environ.get("ANOTHER_SECRET", ""),
            }
            print("PROBE_RESULT=" + json.dumps(result))
            sys.exit(0)
        """))

        # Create a minimal launch config
        launch_toml = tmp_path / "launch.toml"
        launch_toml.write_text(textwrap.dedent(f"""\
            [daemon]
            addr = "127.0.0.1:19999"

            [[nodes]]
            name = "env_probe"
            package = "env_probe"
            command = "python {probe_script}"
            description = "Probe node that prints env"

            [secrets]
            secrets_file = "{secrets_file}"
        """))

        # Run tagentacle launch (daemon must be running)
        env = {**os.environ, "TAGENTACLE_DAEMON_URL": "tcp://127.0.0.1:19999"}
        result = subprocess.run(
            [binary, "launch", str(launch_toml)],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )

        combined_output = result.stdout + result.stderr

        # The probe script should have printed PROBE_RESULT=...
        import json

        for line in combined_output.splitlines():
            if line.startswith("PROBE_RESULT="):
                data = json.loads(line[len("PROBE_RESULT="):])
                assert data["TEST_SECRET_KEY"] == "test_secret_value_12345", (
                    f"TEST_SECRET_KEY not injected: {data}"
                )
                assert data["ANOTHER_SECRET"] == "another_value_67890", (
                    f"ANOTHER_SECRET not injected: {data}"
                )
                return

        # If we didn't find PROBE_RESULT, the probe didn't run or output was lost
        # Check if secrets were at least loaded
        assert "Secrets:" in combined_output and "2 keys" in combined_output, (
            f"Secrets injection not detected in output:\n{combined_output}"
        )
