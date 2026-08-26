# ApiForge 设计教程 — Step by Step

> 从空白项目到可用微框架，共 10 个步骤。
> 每一步都解释"为什么这样设计"，而不只是"怎么做"。

---

## 项目定位

```
ApiForge = 3 行代码暴露一个 API 工具服务
```

**核心约束：**
- 用户写业务函数（Python function）
- 框架负责：路由、参数校验、OpenAPI 文档、HTTP 服务
- 用户不写 Pydantic model，不写 FastAPI decorator

---

## Step 1：选择底层技术栈

### 决策过程

| 选项 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| FastAPI | 异步、自动文档、类型友好 | 依赖 pydantic | ✅ 选定 |
| Flask | 简单 | 无类型提示、无自动文档 | ❌ |
| aiohttp | 性能高 | 无自动文档、学习曲线陡 | ❌ |
| 纯 http.server | 零依赖 | 无文档、无校验、手写路由 | ❌ |

**选择 FastAPI 的核心理由：**
1. `get_type_hints()` + Pydantic 天然适配"函数签名 → 请求模型"的转换
2. 自动 OpenAPI 文档（对"给外部程序调用"的场景极其重要）
3. 中间件生态成熟（后续 CORS、限流、鉴权）

### 文件产出

```
pyproject.toml
├── dependencies: fastapi, uvicorn
├── dev: pytest, httpx, ruff, mypy
├── build-system: hatchling
└── tool config: ruff, mypy, pytest
```

---

## Step 2：设计核心 API — `ApiForge` 类

### 目标

用户只接触一个类：

```python
forge = ApiForge(name="MyService")
forge.run(port=8000)
```

### 类设计

```python
class ApiForge:
    name: str          # 服务名（出现在 OpenAPI title）
    description: str   # 服务描述
    version: str       # 版本号
    app: FastAPI       # 内部 FastAPI 实例（暴露给高级用户）
```

### 为什么用 class 而不是函数？

- 需要状态：`name`、`app` 实例
- 需要方法：`.tool` 装饰器、`.run()` 启动
- 天然支持 `forge.app` 暴露给高级路由场景
- 后续扩展（中间件、配置）有挂载点

---

## Step 3：实现 `@forge.tool` 装饰器 — 核心中的核心

### 设计目标

```python
@forge.tool
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b
```

这一行装饰器必须完成：
1. 解析函数签名 → 生成请求参数模型
2. 创建异步 handler 包装
3. 注册到 FastAPI 路由

### 实现分解

#### 3.1 解析函数签名 → Pydantic Model

```python
def build_request_model(func):
    hints = get_type_hints(func)          # {'a': float, 'b': float, 'return': float}
    sig = inspect.signature(func)         # (a: float, b: float)
    
    fields = {}
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        field_type = hints.get(name, Any)
        if param.default is inspect.Parameter.empty:
            fields[name] = (field_type, ...)      # 必填
        else:
            fields[name] = (field_type, param.default)  # 有默认值
    
    return create_model(f"{func.__name__.capitalize()}Request", **fields)
```

**关键设计决策：**
- 用 `create_model` 动态生成，避免用户手写 Pydantic
- 区分必填/可选（`...` vs 默认值）
- 排除 `self`/`cls`（支持绑定方法）

#### 3.2 创建异步 Handler

```python
def make_handler(model_cls, tool_func, tool_name, doc):
    async def handler(payload):
        result = tool_func(**payload.model_dump())
        if inspect.isawaitable(result):   # ← 关键：支持 async 工具函数
            result = await result
        return result
    return handler
```

**为什么需要 `isawaitable` 检查？**
- 用户可能写 `def add(...)` 或 `async def add(...)`
- 如果直接 `return await tool_func(...)` → 同步函数会报错
- 如果直接 `return tool_func(...)` → 异步函数返回 coroutine 对象
- 解法：先调用，再判断结果是否 awaitable

#### 3.3 注册路由

```python
def tool(self, func):
    path = f"/tools/{func.__name__}"
    self.app.add_api_route(
        path=path,
        endpoint=handler,
        methods=["POST"],
        name=tool_name,
        description=doc,
        tags=["tools"],
    )
    return func  # ← 不修改原函数
```

**为什么返回原函数？**
- 装饰器不应改变函数行为
- 用户仍可直接调用 `add(1, 2)` 而不经过 HTTP
- 方便单元测试

---

## Step 4：处理模块结构 — 避免循环导入

### 问题

```
src/__init__.py  →  import src.server
src/server.py    →  from src import __version__    ← 循环！
```

### 解法

```
src/
├── __init__.py      # from src._version import __version__; from src.server import ApiForge
├── _version.py      # __version__ = "0.1.0"         ← 无依赖
├── _internal.py     # build_request_model, make_handler  ← 只依赖 pydantic
├── server.py        # ApiForge 类                    ← 依赖 _version, _internal
└── router.py        # create_tool_router, register_tool ← 依赖 _internal
```

**设计原则：**
- `_version.py`：零依赖，谁都能安全导入
- `_internal.py`：共享逻辑，消除 server/router 的重复代码
- 下划线前缀 = 内部模块，不对外承诺 API 稳定性

---

## Step 5：健康检查端点

### 为什么需要？

- 运维：k8s liveness probe
- 调试：`curl /health` 确认服务活着
- 信息：返回 service name + version

```python
@self.app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": self.name, "version": self.version}
```

**设计决策：**
- 路径固定 `/health`（行业惯例）
- 独立于 `/tools/` 前缀（系统级 vs 业务级）
- 异步（虽然无 IO，但 FastAPI 推荐）

---

## Step 6：高级路由 — `router.py`

### 使用场景

```python
# 基础用法：@forge.tool 一个服务一个装饰器
# 高级用法：按版本/领域分组路由
```

```python
router = create_tool_router(prefix="/v2/tools", tags=["v2"])
app.include_router(router)
register_tool(router, my_func)
```

### 为什么不直接用 FastAPI 的 APIRouter？

- `register_tool` 自动做签名解析 → Pydantic 模型
- 保持一致的 POST 方法 + JSON body 约定
- 用户不需要知道 Pydantic 的存在

---

## Step 7：启动服务

```python
def run(self, host="0.0.0.0", port=8000, reload=False):
    if reload:
        raise ValueError("请使用 uvicorn CLI")
    uvicorn.run(self.app, host=host, port=port)
```

### 为什么 `reload=True` 抛异常？

- `uvicorn.run(app_object)` 不支持热重载（需要字符串导入路径）
- 与其静默失败，不如明确告知正确用法
- 用户应该用：`uvicorn examples.basic:forge --reload`

### 暴露 `forge.app` 的理由

高级用户可能想：
- 加自定义中间件
- 用 `include_router` 挂子路由
- 用 Starlette 的 lifespan 管理资源

---

## Step 8：测试策略

### 测试分层

```
┌─────────────────────────────────────────────────┐
│  E2E（未来）：真实 HTTP 请求                      │
├─────────────────────────────────────────────────┤
│  集成：TestClient + 完整 App                     │  ← 当前
├─────────────────────────────────────────────────┤
│  单元：单独测 build_request_model 等纯函数        │  ← 可扩展
└─────────────────────────────────────────────────┘
```

### 当前 13 个测试覆盖

| 类别 | 测试 | 验证点 |
|------|------|--------|
| 系统 | health | 基本可达 |
| 核心 | echo/add/reverse | 同步工具函数 |
| 核心 | add_negative | 边界值 |
| 校验 | missing_param | 422 行为 |
| 文档 | openapi_available | 路由注册 |
| 文档 | openapi_descriptions | docstring → summary |
| **新** | async_tool | **async 支持** |
| **新** | default_param | **默认值** |
| **新** | tool_exception | **异常 → 500** |
| **新** | router_register | **router 模块** |
| **新** | router_custom_path | **自定义路径** |

### 关键测试技巧

```python
# async 测试：用 TestClient 而非 pytest-asyncio
c = TestClient(f.app)  # 内部用 anyio 处理 async

# 异常测试：关闭 TestClient 的 raise 行为
c = TestClient(f.app, raise_server_exceptions=False)
```

---

## Step 9：代码规范与质量工具

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "UP", "B"]  # pycodestyle + pyflakes + isort + pyupgrade + bugbear

[tool.mypy]
strict = true  # 最严格模式
```

**为什么选 ruff 而不是 flake8 + isort + black？**
- 一个工具替代四个
- Rust 编写，速度 10-100x
- 零配置即可工作

**为什么 mypy strict？**
- 这是一个"给其他程序调用"的基础库
- 类型安全 = 调用方安全
- 强制标注返回值、参数、局部变量

---

## Step 10：文档策略

### 三层文档

```
README.md         →  什么 + 快速开始（30 秒上手）
docs/user-guide.md →  怎么用 + 常见问题（5 分钟掌握）
docs/design-tutorial.md →  为什么这样设计（30 分钟理解架构）
```

### 开发日志

```
docs/2026-08-26-batch-01.md  →  初始骨架
docs/2026-08-26-batch-02.md  →  审查优化
```

**为什么记录开发日志？**
- 回顾"为什么当时这样决策"
- 给未来贡献者上下文
- Vibe Coding 模式下，对话历史会丢失，日志是永久记录

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                        用户代码                                │
│                                                              │
│   forge = ApiForge(name="MyService")                          │
│   @forge.tool                                                 │
│   def add(a: float, b: float) -> float: ...                   │
│   forge.run(port=8000)                                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    ApiForge (server.py)                       │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────────────┐ │
│  │ __init__    │   │ @tool 装饰器  │   │ run()             │ │
│  │ 创建 App    │   │ 注册路由     │   │ 启动 uvicorn      │ │
│  │ 健康检查    │   │             │   │                   │ │
│  └──────┬──────┘   └──────┬───────┘   └───────────────────┘ │
│         │                 │                                   │
│         ▼                 ▼                                   │
│  ┌─────────────────────────────────┐                          │
│  │     _internal.py (共享逻辑)      │                          │
│  │  • build_request_model()        │                          │
│  │  • make_handler()               │                          │
│  └─────────────────────────────────┘                          │
│                                                              │
│  ┌─────────────────────────────────┐                          │
│  │     router.py (高级路由)         │                          │
│  │  • create_tool_router()         │                          │
│  │  • register_tool()              │                          │
│  └─────────────────────────────────┘                          │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI + Pydantic                         │
│                                                              │
│  • 路由匹配    • 参数校验    • OpenAPI 生成    • 中间件       │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Uvicorn (ASGI Server)                      │
│                                                              │
│  • HTTP 解析    • 异步事件循环    • WebSocket 支持            │
└──────────────────────────────────────────────────────────────┘
```

---

## 后续路线图

```
Phase 1 ✅ 核心骨架（已完成）
  ├─ ApiForge 类
  ├─ @tool 装饰器
  ├─ 健康检查
  ├─ 基础测试
  └─ 文档

Phase 2 🔜 生产能力
  ├─ 中间件（CORS、日志、限流）
  ├─ 统一错误响应格式
  ├─ 配置系统（环境变量 / .env）
  └─ 发布打包（pypi）

Phase 3 🚀 高级特性
  ├─ SSE / WebSocket 流式
  ├─ 工具链编排（A → B → C 管道）
  ├─ 认证（API Key / OAuth）
  └─ 可观测性（metrics / tracing）
```

---

## 核心设计原则总结

| 原则 | 体现 |
|------|------|
| **最少惊讶** | 函数签名即 API 契约，不需要额外声明 |
| **渐进增强** | 基础用 `@forge.tool`，高级用 `router.py` |
| **不隐藏底层** | `forge.app` 始终可访问，FastAPI 能力全开放 |
| **同步异步透明** | 用户写 `def` 或 `async def` 都行 |
| **内部去重** | `_internal.py` 消除重复，但对外 API 不变 |
| **快速失败** | `reload=True` 直接报错而非静默忽略 |

---

*从 0 到 ApiForge，10 步走完全程。* 🔨
