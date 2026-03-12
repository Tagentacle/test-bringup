# Copilot Instructions — test-bringup

## Project Overview
This is the **test package** for the Tagentacle ecosystem. It contains two layers:
- `tests/integration/` — Daemon + SDK integration tests (CI runs these)
- `tests/e2e/` — Full-stack E2E tests (require secrets + all ecosystem nodes)

## Architecture
- `tests/conftest.py` — Shared fixtures: daemon process, node factory
- `tests/integration/test_*.py` — Integration tests (Daemon + SDK only)
- `tests/e2e/conftest.py` — Full-stack fixture (launches via example-bringup)
- `tests/e2e/test_*.py` — Full-stack E2E tests

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
