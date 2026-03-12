# test-bringup

Tagentacle 端到端（E2E）集成测试包。

## 定位

`test-bringup` 是一个纯测试包，不包含任何可运行的 Node。它的作用是：

1. **启动真实 Daemon** — 在测试开始前启动 `tagentacle` 二进制
2. **使用 SDK 创建 Node** — 通过 `tagentacle-py-core` / `tagentacle-py-mcp` 建立连接
3. **验证核心路径** — pub/sub、service RPC、schema 校验、节点生命周期事件

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
# 方式 1: 自动搜索 daemon（按 TAGENTACLE_BIN → workspace → PATH 顺序）
pytest -v

# 方式 2: 显式指定 daemon 路径
TAGENTACLE_BIN=/path/to/tagentacle pytest -v

# 方式 3: 只跑 pub/sub 相关测试
pytest -v tests/test_pubsub.py
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
├── tagentacle.toml          # 包清单（声明依赖仓库）
├── pyproject.toml            # Python 项目配置 + pytest 设置
├── tests/
│   ├── conftest.py           # Daemon fixture + Node 工厂
│   ├── test_pubsub.py        # 发布/订阅测试
│   ├── test_service.py       # Service RPC 测试
│   ├── test_node_events.py   # 节点事件测试
│   └── test_schema.py        # Schema 校验测试
└── .github/
    └── workflows/
        └── e2e.yml           # GitHub Actions E2E 流水线
```

## 覆盖的测试场景

| 文件               | 测试点                          |
| ------------------ | ------------------------------- |
| test_pubsub.py     | 单订阅、多订阅扇出、话题隔离、消息顺序 |
| test_service.py    | ping、list_nodes、list_topics、用户自定义 service |
| test_node_events.py| 节点上线事件、节点离线事件         |
| test_schema.py     | 严格模式校验、非法消息拒绝、无 schema 透传 |
