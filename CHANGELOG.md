# Changelog — test-bringup

All notable changes to **test-bringup** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-13

### Added
- **`test_container_orchestrator.py`**: 11 tests — import, runtime connect/info/list, full lifecycle, orchestrator service validation.
- **`test_shell_server.py`**: 16 tests — import, local exec (echo/cwd/exit code/stderr/multiline/pipe), space resolution, cwd tracking, exec routing.

### Changed
- **CI**: Migrated from pip to uv. Renamed workflow to "Integration Tests". Lint (Layer 1) + integration (Layer 3) jobs. Sibling checkout for uv.sources.
- **Markers**: `@e2e` → `@system` (aligns with CI Layer 4). Added marker descriptions.
- **`.gitignore`**: Added `.ruff_cache/`.
- **README**: Rewritten with CI layer alignment, dependency management policy.

### Removed
- Cross-package deps NOT added to `pyproject.toml` — resolved via `tagentacle setup dep`.

## [0.1.0] - 2026-03-12

### Added
- Initial release: integration test suite for Tagentacle ecosystem.
- Tests: `test_pubsub.py`, `test_service.py`, `test_node_events.py`, `test_schema.py`, `test_full_stack.py`.
- `conftest.py` with daemon auto-management and `make_node` factory.
- GitHub Actions CI workflow.
