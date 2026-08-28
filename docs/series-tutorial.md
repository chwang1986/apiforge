# ApiForge 系列教程 📚

> 本教程是 ApiForge 框架 50 轮迭代的完整知识体系。从"把函数变成 API"开始，一路走到生产级部署。
> 建议按顺序阅读，每章对应一个可运行的示例与测试。

## 学习路径

```
第 1 章 核心      → 第 4 章 生产      → 第 5 章 可观测 → 第 6 章 部署
   (会用)             (能上线)            (看得见)        (跑得稳)
```

## 目录

### 第 1 章 · 核心引擎（Round 1-10）

| 章节 | 主题 | 你将学会 |
|------|------|----------|
| 1.1 | 30 秒上手 | `@forge.tool` 装饰器、第一个 API |
| 1.2 | 类型系统与参数 | Pydantic 动态模型、参数校验 |
| 1.3 | 统一错误处理 | `ToolError`、结构化错误响应 |
| 1.4 | 自定义校验器 | 装饰器校验、业务规则 |
| 1.5 | 响应封装 | envelope 模式、request_id |

**里程碑**：能独立写出一个带校验、错误处理、统一响应的服务。

```python
from src.server import ApiForge
from src.errors import ToolError

forge = ApiForge(name="MyService")

@forge.tool
def divide(a: float, b: float) -> float:
    """两数相除。"""
    if b == 0:
        raise ToolError("除数不能为零", code="DIV_BY_ZERO")
    return a / b

forge.run(port=8000)
# POST /tools/divide  {"a": 10, "b": 2}  →  5.0
```

### 第 2 章 · 生产安全（Round 11-20）

| 章节 | 主题 | 你将学会 |
|------|------|----------|
| 2.1 | CORS | 跨域策略配置 |
| 2.2 | 限流 | 令牌桶算法、429 响应 |
| 2.3 | 认证 | API Key、Bearer Token |
| 2.4 | 配置管理 | 环境变量、分层配置 |
| 2.5 | 生命周期钩子 | startup/shutdown |
| 2.6 | 健康检查 | `/health`、存活/就绪探针 |
| 2.7 | 请求追踪 ID | 全链路 X-Request-ID |
| 2.8 | 请求体限制 | 防 OOM |
| 2.9 | 压缩 | gzip 中间件 |
| 2.10 | 安全头 | CSP、HSTS 等 |

**里程碑**：服务具备上线所需的安全基线。

### 第 3 章 · 高级功能（Round 21-30）

| 章节 | 主题 | 你将学会 |
|------|------|----------|
| 3.1 | GET 方法与查询参数 | method 参数 |
| 3.2 | 路径参数 | `/tools/users/{id}` |
| 3.3 | 文件上传 | multipart |
| 3.4 | 流式响应 | SSE / StreamingResponse |
| 3.5 | WebSocket | 双向实时通信 |
| 3.6 | 中间件管道 | pipeline 编排 |
| 3.7 | 命名空间 | 多路由前缀 |
| 3.8 | 请求/响应变换 | before/after 钩子 |
| 3.9 | OpenAPI 增强 | summary、examples、tags |

### 第 4 章 · 开发者体验（Round 31-40）

| 章节 | 主题 | 你将学会 |
|------|------|----------|
| 4.1 | 客户端 SDK 生成 | 自动生成 Python 客户端 |
| 4.2 | cURL 生成 | 一键导出调试命令 |
| 4.3 | CLI 工具 | `forge init/client/curl` |
| 4.4 | 测试工具包 | `post_tool`/`get_tool` |
| 4.5 | 基准测试 | p50/p90/p99 延迟 |
| 4.6 | 项目脚手架 | 一键生成项目 |
| 4.7 | 插件系统 | 钩子注册、启停 |
| 4.8 | 热重载 | 文件监听、自动重启 |
| 4.9 | API Key 管理 | 生成/轮换/吊销 |
| 4.10 | 集成测试 | 多模块协同验证 |

### 第 5 章 · 可观测性（Round 41-45）

| 章节 | 主题 | 你将学会 |
|------|------|----------|
| 5.1 | Prometheus 指标 | Counter/Gauge/Histogram、`/metrics` |
| 5.2 | 分布式追踪 | Span、W3C traceparent |
| 5.3 | JSON 结构化日志 | context manager 作用域字段 |
| 5.4 | 审计日志 | 谁在何时调了什么 |
| 5.5 | 内嵌 Dashboard | HTML+JS 实时面板 |

**里程碑**：服务运行状态"看得见"——指标、追踪、日志、审计齐备。

### 第 6 章 · 部署与发布（Round 46-50）

| 章节 | 主题 | 你将学会 |
|------|------|----------|
| 6.1 | Docker | Dockerfile、compose、非 root |
| 6.2 | Kubernetes | Deployment/Service/Ingress/HPA |
| 6.3 | PyPI 发布 | pyproject 元数据、Makefile |
| 6.4 | E2E 测试 | 全栈端到端 |
| 6.5 | 文档体系 | 知识系统化 |

## 每轮交付物标准

```
每轮 = 代码 + 测试 + 文档
 1. 代码变更（src/ 下）
 2. 测试用例（tests/test_roundXX.py）
 3. 教程文档（docs/）
 4. git commit + push
```

## 环境要求

```
Python >= 3.11
依赖: fastapi, uvicorn, python-multipart
```

## 快速开始

```bash
# 安装
pip install -e ".[dev]"

# 运行示例
python examples/basic.py

# 运行测试
python -m pytest tests/ -v
```

## 附录

- 完整功能路线图：[50-rounds-plan.md](./50-rounds-plan.md)
- 用户指南：[user-guide.md](./user-guide.md)
- 设计教程：[design-tutorial.md](./design-tutorial.md)

---

*ApiForge — 把函数变成生产级 API 工具服务。* 🔨
