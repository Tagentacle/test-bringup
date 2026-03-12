# test-bringup

Tagentacle 端到端（E2E）集成测试包。

## 定位

`test-bringup` 是 Tagentacle 生态系统的测试包，包含两级测试：

### Integration Tests（`tests/integration/`）

启动 **Daemon + SDK**，验证核心通信路径：
- pub/sub、service RPC、schema 校验、节点生命周期事件
- CI 自动运行，轻量快速

### E2E Tests（`tests/e2e/`）

通过 `example-bringup` 启动 **完整生态**：
- Daemon → MCP Server → Inference → Memory → Agent → Frontend
- 验证全栈拓扑、节点发现、跨组件通信
- 需要 API key 等 secrets，手动/本地运行

## 依赖管理策略

本包通过 `pyproject.toml` 中的版本约束管理上游 SDK 版本：

```toml
dependencies = [
    "tagentacle-py-core >= 0.3.0",
]
```

**每当上游发布新 tag 时**，开一个 branch 更新版本约束 → 跑 CI → 绿了就合并。
这样可以在合并到 main 之前验证兼容性。

### 本地开发

本地开发时使用 `uv` 的 path override 直接链接 workspace 中的源码：

```toml
[tool.uv.sources]
tagentacle-py-core = { path = "../python-sdk-core", editable = true }
tagentacle-py-mcp  = { path = "../python-sdk-mcp",  editable = true }
```

## 快速开始

### 前置条件

- Python ≥ 3.10
- 已编译的 `tagentacle` daemon 二进制

### 运行测试

```bash
# 只跑集成测试（CI 默认）
pytest tests/integration -v

# 只跑 E2E（需要 secrets + 全生态包）
pytest tests/e2e -v --timeout=120

# 全部跑
pytest -v

# 显式指定 daemon 路径
TAGENTACLE_BIN=/path/to/tagentacle pytest tests/integration -v
```

### CI 手动触发

可以在 GitHub Actions 中手动触发 E2E 测试，并指定各组件的 git ref：

```
gh workflow run e2e.yml \
  -f daemon_ref=v0.4.0 \
  -f sdk_core_ref=v0.3.0 \
  -f sdk_mcp_ref=v0.4.0
```

## 目录结构

```
test-bringup/
├── tagentacle.toml              # 包清单（声明依赖仓库）
├── pyproject.toml                # Python 项目配置 + pytest 设置
├── tests/
│   ├── conftest.py               # 共享 fixture（Daemon、make_node）
│   ├── integration/              # 集成测试（Daemon + SDK）
│   │   ├── test_pubsub.py
│   │   ├── test_service.py
│   │   ├── test_node_events.py
│   │   └── test_schema.py
│   └── e2e/                      # 全栈 E2E 测试
│       ├── conftest.py           # full_stack fixture（example-bringup launcher）
│       └── test_full_stack.py    # 拓扑验证、节点发现、跨组件通信
└── .github/
    └── workflows/
        └── e2e.yml               # GitHub Actions CI 流水线
```

## 覆盖的测试场景

### Integration Tests

| 文件               | 测试点                          |
| ------------------ | ------------------------------- |
| test_pubsub.py     | 单订阅、多订阅扇出、话题隔离、消息顺序 |
| test_service.py    | ping、list_nodes、list_topics、用户自定义 service |
| test_node_events.py| 节点上线事件、节点离线事件         |
| test_schema.py     | 严格模式校验、非法消息拒绝、无 schema 透传 |

### E2E Tests

| 文件               | 测试点                          |
| ------------------ | ------------------------------- |
| test_full_stack.py | Daemon ping、全节点发现、MCP server 健康检查、Topic 发现、Memory 订阅 |
