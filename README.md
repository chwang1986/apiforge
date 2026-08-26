# ApiForge 🔨

> 一个轻量级微框架，专注于向外部程序提供 API 工具服务。

## 核心理念

- **专注**：只做一件事——快速暴露 API 工具接口
- **轻量**：微框架，低依赖，易嵌入
- **面向外部**：为其他程序提供稳定的工具能力

## 技术路线

| 层面 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | 现代语法、性能提升 |
| Web 框架 | FastAPI | 异步、自动 OpenAPI 文档、类型提示友好 |
| 包管理 | uv | 极快的 Python 包管理器 |
| 代码规范 | ruff | lint + format 二合一 |
| 类型检查 | mypy | 静态类型检查 |
| 测试 | pytest | 标准测试框架 |
| 协议 | HTTP + JSON | 标准 RESTful API |

## 目录结构

```
apiforge/
├── README.md
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── server.py          # 核心：ApiForge 类 + @forge.tool 装饰器
│   ├── router.py          # 高级路由工具函数
│   └── middleware/
│       └── __init__.py
├── examples/
│   └── basic.py           # 示例：echo / add / reverse
├── tests/
│   └── test_basic.py      # 单元测试
└── docs/
    ├── 2026-08-26-batch-01.md  # 开发日志
    └── user-guide.md            # 用户上手手册
```

## 快速开始

```bash
cd apiforge

# 安装依赖
pip install fastapi "uvicorn[standard]"

# 运行示例
PYTHONPATH=. python examples/basic.py

# 访问 Swagger 文档
open http://localhost:8000/api/docs

# 运行测试
pip install pytest httpx
PYTHONPATH=. python -m pytest tests/ -v
```

## 核心用法

```python
from src.server import ApiForge

forge = ApiForge(name="MyService")

@forge.tool
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

forge.run(port=8000)
# → POST /tools/add  {"a": 1, "b": 2}  →  3
```

## 开发约定

- 遵循 PEP 8 代码风格（ruff 自动检查）
- 所有公开 API 必须有类型提示
- 每个工具接口提供 OpenAPI 文档描述
- 测试覆盖率目标 ≥ 80%
- 开发日志记录在 `docs/` 目录

---

*Forge your APIs.* 🎸
