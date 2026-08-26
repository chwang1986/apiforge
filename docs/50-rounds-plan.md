# ApiForge 50 轮开发计划

> 目标：从一个最小微框架出发，50 轮迭代构建一个**生产级 API 工具服务框架**。
> 每轮 = 一个完整功能 + 测试 + 文档 + 可视化说明。
> 学生可以跟着每一轮动手仿写。

---

## 总目标

```
ApiForge = 让开发者用 3 行代码暴露一个带完整生产能力的 API 服务
```

最终成果：
- 生产级 API 框架（认证、限流、日志、监控）
- 开发体验一流（CLI、热重载、客户端 SDK 生成）
- 可观测性完备（metrics、tracing、structured logging）
- 部署即开即用（Docker、K8s、PyPI）
- 50 篇教程，每篇独立可学

---

## Phase 1：核心引擎强化（Round 1-10）

| Round | 功能 | 产出文件 | 学生学到 |
|-------|------|----------|----------|
| 01 | ✅ 项目骨架 + ApiForge 类 + @tool 装饰器 | `src/server.py` | 装饰器模式、FastAPI 基础 |
| 02 | ✅ 健康检查 + 版本端点 | `server.py` | 中间件 vs 端点 |
| 03 | ✅ 函数签名 → Pydantic 模型自动生成 | `src/_internal.py` | `inspect` + `create_model` |
| 04 | ✅ async 工具函数支持 | `src/_internal.py` | `isawaitable` 技巧 |
| 05 | ✅ 默认参数值 | `src/_internal.py` | 可选参数设计 |
| 06 | ✅ Router 模块（分组路由） | `src/router.py` | APIRouter 组合 |
| 07 | **统一错误响应格式** | `src/errors.py` | 异常处理器、错误码设计 |
| 08 | **请求参数高级校验** | `src/validators.py` | 自定义 validator、正则、范围 |
| 09 | **响应信封（Response Envelope）** | `src/response.py` | 统一响应结构、status/code/data |
| 10 | **请求日志中间件** | `src/middleware/logging.py` | ASGI 中间件、结构化日志 |

## Phase 2：生产安全（Round 11-20）

| Round | 功能 | 产出文件 | 学生学到 |
|-------|------|----------|----------|
| 11 | **CORS 中间件** | `src/middleware/cors.py` | 跨域策略、预检请求 |
| 12 | **限流中间件（Token Bucket）** | `src/middleware/rate_limit.py` | 算法实现、内存 vs 分布式 |
| 13 | **API Key 认证** | `src/middleware/auth.py` | 认证流程、key 生成、hash |
| 14 | **配置系统（env + .env）** | `src/config.py` | 12-Factor App、配置优先级 |
| 15 | **优雅关闭（Graceful Shutdown）** | `src/lifecycle.py` | lifespan、信号处理 |
| 16 | **依赖健康探测** | `src/health.py` | 依赖检查、超时、聚合 |
| 17 | **Request ID / Correlation ID** | `src/middleware/request_id.py` | 分布式追踪基础 |
| 18 | **Payload 大小限制** | `src/middleware/size_limit.py` | DoS 防护 |
| 19 | **响应压缩（gzip/br）** | `src/middleware/compression.py` | Content-Encoding |
| 20 | **安全头（Security Headers）** | `src/middleware/security.py` | CSP、HSTS、X-Frame |

## Phase 3：API 能力扩展（Round 21-30）

| Round | 功能 | 产出文件 | 学生学到 |
|-------|------|----------|----------|
| 21 | **GET 方法支持** | `src/server.py` 扩展 | query params vs body |
| 22 | **路径参数** | `src/_internal.py` 扩展 | `:param` 路由 |
| 23 | **Query 参数混合** | `src/_internal.py` 扩展 | body + query 组合 |
| 24 | **文件上传** | `src/upload.py` | multipart、大小限制 |
| 25 | **SSE 流式响应** | `src/streaming.py` | Server-Sent Events |
| 26 | **WebSocket 工具** | `src/ws.py` | 双向通信 |
| 27 | **工具管道（Pipeline）** | `src/pipeline.py` | 函数组合、中间变换 |
| 28 | **命名空间（Namespace）** | `src/namespace.py` | 路由前缀、标签分组 |
| 29 | **请求/响应变换器** | `src/transform.py` | 数据映射、序列化 |
| 30 | **OpenAPI 增强** | `src/openapi_ext.py` | 自定义 schema、examples |

## Phase 4：开发者体验（Round 31-40）

| Round | 功能 | 产出文件 | 学生学到 |
|-------|------|----------|----------|
| 31 | **Python 客户端 SDK 生成** | `src/codegen/client.py` | 代码生成、AST |
| 32 | **cURL 命令生成器** | `src/codegen/curl.py` | 从 OpenAPI 生成 |
| 33 | **forge CLI 工具** | `forge_cli.py` | typer/click、子命令 |
| 34 | **开发服务器（热重载）** | `src/devserver.py` | watchdog、自动重启 |
| 35 | **测试工具包** | `src/testing.py` | fixtures、mock、assert helpers |
| 36 | **基准测试工具** | `src/benchmark.py` | 并发、吞吐、延迟分布 |
| 37 | **代码模板（scaffold）** | `src/codegen/scaffold.py` | 项目脚手架 |
| 38 | **插件系统** | `src/plugins.py` | 钩子、注册、生命周期 |
| 39 | **工具元数据注解** | `src/annotations.py` | 装饰器链、元数据 |
| 40 | **API 版本管理** | `src/versioning.py` | 多版本共存、废弃策略 |

## Phase 5：可观测性与部署（Round 41-50）

| Round | 功能 | 产出文件 | 学生学到 |
|-------|------|----------|----------|
| 41 | **Prometheus Metrics** | `src/observability/metrics.py` | /metrics、histogram |
| 42 | **分布式追踪（OTel）** | `src/observability/tracing.py` | Span、Context |
| 43 | **JSON 结构化日志** | `src/observability/logging.py` | json logger、level 策略 |
| 44 | **审计日志** | `src/observability/audit.py` | 谁在何时调了什么 |
| 45 | **内嵌 Dashboard** | `src/dashboard.py` | 简单 HTML + JS |
| 46 | **Docker 支持** | `Dockerfile` + `docker-compose.yml` | 容器化 |
| 47 | **Kubernetes 部署模板** | `deploy/k8s/` | Deployment、Service、HPA |
| 48 | **PyPI 发布流程** | `pyproject.toml` + `Makefile` | 打包、版本、发布 |
| 49 | **集成测试套件** | `tests/integration/` | E2E、Docker 测试 |
| 50 | **完整文档 + 系列教程** | `docs/` 全量 | 知识体系化 |

---

## 每轮交付物标准

```
每轮 = 代码 + 测试 + 教程文档

1. 代码变更（src/ 下）
2. 测试用例（tests/test_round_XX.py）
3. 教程文档（docs/rounds/round-XX.md）
   - 目标 & 背景
   - 代码 walkthrough（逐行注释）
   - 运行演示（curl / 浏览器截图描述）
   - 架构图（ASCII）
   - 思考题（2-3 个）
4. git commit + push
```

---

## 当前进度

```
Phase 1:  ██████░░░░  6/10  (Round 1-6 ✅, Round 7-10 🔜)
Phase 2:  ░░░░░░░░░░  0/10
Phase 3:  ░░░░░░░░░░  0/10
Phase 4:  ░░░░░░░░░░  0/10
Phase 5:  ░░░░░░░░░░  0/10
Total:    █████░░░░░  6/50
```
