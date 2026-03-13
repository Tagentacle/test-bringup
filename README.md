# test-bringup

Tagentacle 集成测试包 — 验证跨包交互和全生态运行。

## CI 分层定位

| Layer | 本包覆盖 | 说明 |
|-------|---------|------|
| Layer 1: lint | ✅ | ruff check + format (GHA 自动) |
| Layer 2: pkg test | ❌ | 各包自己的 tests/ |
| Layer 3: integration | ✅ | 跨包集成: daemon + SDK |
| Layer 4: system | ✅ | 全生态端到端 (手动/nightly) |

## 测试标记

```python
@pytest.mark.integration   # Layer 3: 需要 daemon + SDK
@pytest.mark.system         # Layer 4: 需要全量节点 + gateway
@pytest.mark.slow           # 耗时 >10s
```

## 目录结构

```
test-bringup/
├── tagentacle.toml           # 包清单 (声明依赖仓库)
├── pyproject.toml            # Python 项目配置 + pytest 设置
├── tests/
│   ├── conftest.py           # 共享 fixture (Daemon、make_node)
│   ├── test_pubsub.py        # @integration: pub/sub、扇出、隔离、顺序
│   ├── test_service.py       # @integration: ping、list、用户 service
│   ├── test_node_events.py   # @integration: 上线/离线事件
│   ├── test_schema.py        # @integration: 严格模式、非法消息、无 schema
│   ├── test_container_orchestrator.py  # @integration: 容器编排
│   ├── test_shell_server.py  # @integration: shell exec
│   └── test_full_stack.py    # @system: 全栈拓扑验收
└── .github/workflows/
    └── e2e.yml               # GHA: lint + Layer 3 integration
```

## 快速开始

```bash
# Layer 3: 集成测试 (需要 daemon)
tagentacle test --pkg .

# 或手动:
pytest tests/ -v -m "not system" --timeout=30

# Layer 4: 全栈 (需要全生态)
pytest tests/ -v -m system --timeout=120
```

## 依赖管理

- **pyproject.toml**: 仅声明 PyPI 依赖 (pytest, tagentacle-py-core)
- **tagentacle.toml**: 声明 workspace 内依赖 (由 `tagentacle setup dep` 解析)
- **跨包依赖不泄漏到 pyproject.toml** — `tagentacle setup dep --all` 处理
