# Copilot Instructions — test-bringup

## Project Overview
This is the **end-to-end integration test** package for the Tagentacle ecosystem.
It is NOT a library or runnable node — it only contains pytest-based tests.

## Architecture
- `tests/conftest.py` — Session-scoped fixtures: daemon process, node factory
- `tests/test_*.py` — Test modules grouped by feature (pubsub, service, schema, events)

## Key Dependencies
- **tagentacle daemon** (Rust binary) — started/stopped by the `daemon` fixture
- **tagentacle-py-core** — Python SDK for Node, pub/sub, service calls
- **tagentacle-py-mcp** (optional) — MCP bridge tests

## Running Tests
```bash
# Run all tests
pytest -v

# Specify daemon binary explicitly
TAGENTACLE_BIN=/path/to/tagentacle pytest -v
```

## Writing New Tests
1. Use the `make_node` fixture to create nodes — it handles cleanup automatically
2. Use `daemon` fixture (session-scoped) — one daemon per test session
3. All tests are async by default (`asyncio_mode = "auto"` in pyproject.toml)
4. Test timeout is 30s — keep tests focused and fast

## Dependency Version Management
- `pyproject.toml` pins minimum SDK versions
- When upstream tags a new release, create a branch → bump version constraint → run CI → merge
- Local dev uses `uv` path overrides to link workspace source

## Commit Convention
Follow Conventional Commits: `test:`, `fix:`, `ci:`, `docs:`
