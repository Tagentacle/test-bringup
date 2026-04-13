"""
Integration tests for shell-mcp.

Tests ShellServer's local exec mode (no container runtime needed).
Container routing and TACL auth are tested separately when available.

Most tests exercise the internal methods directly without needing
a running daemon — only the bus-level e2e tests require it.
"""

import os

import pytest

pytestmark = pytest.mark.integration


class TestShellServerImport:
    """Verify shell-mcp package is importable."""

    def test_import(self):
        """ShellServer class can be imported."""
        ss = pytest.importorskip("shell_mcp", reason="shell-mcp not installed")
        assert hasattr(ss, "ShellServer")


class TestLocalExec:
    """Tests for _exec_local — local subprocess execution backend."""

    def _make_server(self, node_id="test_shell"):
        ss = pytest.importorskip("shell_mcp")
        return ss.ShellServer(
            node_id=node_id,
            mcp_port=0,
            auth_required=False,
        )

    def test_echo(self):
        """Basic echo command returns expected output."""
        server = self._make_server("test_echo")
        exit_code, stdout, stderr = server._exec_local("echo hello", os.getcwd())
        assert exit_code == 0
        assert "hello" in stdout

    def test_cwd(self):
        """Command runs in the specified working directory."""
        server = self._make_server("test_cwd")
        exit_code, stdout, _ = server._exec_local("pwd", "/tmp")
        assert exit_code == 0
        assert "tmp" in stdout.lower()

    def test_exit_code(self):
        """Non-zero exit codes are captured correctly."""
        server = self._make_server("test_exit")
        exit_code, _, _ = server._exec_local("exit 42", os.getcwd())
        assert exit_code == 42

    def test_stderr(self):
        """Standard error is captured separately."""
        server = self._make_server("test_stderr")
        exit_code, _, stderr = server._exec_local("echo error_msg >&2", os.getcwd())
        assert exit_code == 0
        assert "error_msg" in stderr

    def test_multiline_output(self):
        """Multi-line output is captured completely."""
        server = self._make_server("test_multi")
        exit_code, stdout, _ = server._exec_local(
            "echo line1 && echo line2 && echo line3", os.getcwd()
        )
        assert exit_code == 0
        assert "line1" in stdout
        assert "line2" in stdout
        assert "line3" in stdout

    def test_invalid_cwd(self):
        """Invalid working directory returns error gracefully."""
        server = self._make_server("test_bad_cwd")
        exit_code, _, stderr = server._exec_local("echo test", "/nonexistent_dir_xyz")
        assert exit_code != 0 or "not found" in stderr.lower()

    def test_pipe(self):
        """Shell pipes work in local mode."""
        server = self._make_server("test_pipe")
        exit_code, stdout, _ = server._exec_local(
            "echo 'hello world' | tr ' ' '_'", os.getcwd()
        )
        assert exit_code == 0
        assert "hello_world" in stdout


class TestSpaceResolution:
    """Tests for _resolve_space — target container resolution."""

    def _make_server(self, **kwargs):
        ss = pytest.importorskip("shell_mcp")
        return ss.ShellServer(
            node_id="test_space",
            mcp_port=0,
            auth_required=False,
            **kwargs,
        )

    def test_local_mode(self):
        """No JWT, no static container → None (local exec)."""
        server = self._make_server()
        assert server._resolve_space() is None

    def test_static_container(self):
        """With target_container set, resolve to that name."""
        server = self._make_server(target_container="my_container")
        assert server._resolve_space() == "my_container"


class TestCwdTracking:
    """Tests for per-session cwd state management."""

    def _make_server(self):
        ss = pytest.importorskip("shell_mcp")
        return ss.ShellServer(
            node_id="test_cwd_track",
            mcp_port=0,
            auth_required=False,
        )

    def test_default_local_cwd(self):
        """Local session defaults to os.getcwd()."""
        server = self._make_server()
        assert server._get_cwd("_local_") == os.getcwd()

    def test_default_container_cwd(self):
        """Container sessions default to '/'."""
        server = self._make_server()
        assert server._get_cwd("some_container") == "/"

    def test_set_and_get(self):
        """Setting cwd persists for the session."""
        server = self._make_server()
        server._set_cwd("_local_", "/tmp")
        assert server._get_cwd("_local_") == "/tmp"

    def test_session_isolation(self):
        """Different sessions have independent cwd state."""
        server = self._make_server()
        server._set_cwd("container_a", "/opt")
        server._set_cwd("container_b", "/var")
        assert server._get_cwd("container_a") == "/opt"
        assert server._get_cwd("container_b") == "/var"
        # Unset session still gets default
        assert server._get_cwd("container_c") == "/"


class TestExecRouting:
    """Tests for _exec dispatch logic."""

    def _make_server(self):
        ss = pytest.importorskip("shell_mcp")
        return ss.ShellServer(
            node_id="test_route",
            mcp_port=0,
            auth_required=False,
        )

    def test_local_route(self):
        """space=None routes to local subprocess."""
        server = self._make_server()
        exit_code, stdout, _ = server._exec(None, "echo routed", os.getcwd())
        assert exit_code == 0
        assert "routed" in stdout

    def test_container_route_no_runtime(self):
        """space='container' raises an error for missing container."""
        server = self._make_server()
        with pytest.raises(Exception):
            # Either RuntimeError (no runtime installed) or
            # container NotFound (runtime available but container doesn't exist)
            server._exec("nonexistent_container", "echo fail", "/")
