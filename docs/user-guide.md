# ApiForge 用户上手手册

> 版本：0.1.0 | 更新日期：2026-08-26

本手册帮助你快速启动、测试和使用 ApiForge 服务。

---

## 1. 环境准备

### 前置要求

- Python 3.11+
- pip（或使用 uv 管理依赖）

### 安装依赖

```bash
cd apiforge
pip install fastapi "uvicorn[standard]"
```

### 验证安装

```bash
python -c "import fastapi; import uvicorn; print('OK')"
```

---

## 2. 启动服务

### 方式一：运行示例（推荐新手）

```bash
cd apiforge
PYTHONPATH=. python examples/basic.py
```

看到以下输出表示启动成功：

```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 方式二：使用 uvicorn 直接启动（支持热重载）

```bash
cd apiforge
PYTHONPATH=. uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
```

> ⚠️ 注意：此方式加载的是模块级 `app`（空实例），适合调试框架本身。
> 若要加载自定义工具，请使用方式一或方式三。

### 方式三：自定义服务

创建你自己的 `my_service.py`：

```python
from src.server import ApiForge

forge = ApiForge(name="MyService", description="My custom tools")

@forge.tool
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    forge.run(host="127.0.0.1", port=9000)
```

```bash
PYTHONPATH=. python my_service.py
```

---

## 3. 测试 API

服务启动后，在另一个终端中执行以下测试。

### 3.1 健康检查

```bash
curl http://localhost:8000/health
```

**预期响应**：

```json
{
  "status": "ok",
  "service": "MyToolService",
  "version": "0.1.0"
}
```

### 3.2 Echo 工具（回显文本）

```bash
curl -X POST http://localhost:8000/tools/echo \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello ApiForge!"}'
```

**预期响应**：

```
Hello ApiForge!
```

### 3.3 Add 工具（两数相加）

```bash
curl -X POST http://localhost:8000/tools/add \
  -H "Content-Type: application/json" \
  -d '{"a": 3, "b": 4}'
```

**预期响应**：

```
7
```

### 3.4 Reverse 工具（反转字符串）

```bash
curl -X POST http://localhost:8000/tools/reverse \
  -H "Content-Type: application/json" \
  -d '{"text": "abcdef"}'
```

**预期响应**：

```
fedcba
```

### 3.5 参数校验（故意传错）

```bash
curl -X POST http://localhost:8000/tools/add \
  -H "Content-Type: application/json" \
  -d '{"a": 1}'
```

**预期响应**（422）：

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "b"],
      "msg": "Field required"
    }
  ]
}
```

### 3.6 查看 OpenAPI 文档

```bash
# Swagger UI（浏览器访问）
open http://localhost:8000/api/docs

# ReDoc（浏览器访问）
open http://localhost:8000/api/redoc

# JSON Schema
curl http://localhost:8000/api/openapi.json | python -m json.tool
```

### 3.7 使用 Python 调用

```python
import requests

r = requests.post(
    "http://localhost:8000/tools/add",
    json={"a": 10, "b": 32},
)
print(r.json())  # 输出: 42
```

或使用标准库（无第三方依赖）：

```python
import urllib.request
import json

req = urllib.request.Request(
    "http://localhost:8000/tools/echo",
    data=json.dumps({"message": "from Python"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
resp = urllib.request.urlopen(req)
print(resp.read().decode())  # 输出: from Python
```

---

## 4. 关闭服务

### 方式一：快捷键

在运行服务的终端中按 `Ctrl + C`，服务会优雅关闭：

```
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [xxxxx]
```

### 方式二：通过进程号

```bash
# 查找占用 8000 端口的进程
lsof -i :8000

# 终止
kill <PID>
```

### 确认已关闭

```bash
curl http://localhost:8000/health
# 应返回: Connection refused
```

---

## 5. 运行自动化测试

```bash
cd apiforge
pip install pytest httpx
PYTHONPATH=. python -m pytest tests/ -v
```

**预期输出**：

```
tests/test_basic.py::test_health PASSED
tests/test_basic.py::test_echo PASSED
tests/test_basic.py::test_add PASSED
tests/test_basic.py::test_add_negative PASSED
tests/test_basic.py::test_reverse PASSED
tests/test_basic.py::test_missing_param_returns_422 PASSED
tests/test_basic.py::test_openapi_available PASSED
tests/test_basic.py::test_openapi_has_tool_descriptions PASSED
8 passed
```

---

## 6. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: No module named 'src'` | 未设置 PYTHONPATH | 命令前加 `PYTHONPATH=.` |
| `Address already in use` | 端口 8000 被占用 | `lsof -i :8000` 找进程 kill 掉，或换端口 |
| 422 Unprocessable Entity | 请求体缺少必填字段 | 检查 JSON 是否包含所有参数 |
| 404 Not Found | 路径拼写错误 | 访问 `/api/docs` 查看正确路径 |
| `reload` 模式不生效 | 传对象给 uvicorn 不支持 reload | 使用 `uvicorn src.server:app --reload` |

---

## 7. 端点速查表

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/health` | — | 健康检查 |
| POST | `/tools/echo` | `message: str` | 回显文本 |
| POST | `/tools/add` | `a: float, b: float` | 两数相加 |
| POST | `/tools/reverse` | `text: str` | 反转字符串 |
| GET | `/api/docs` | — | Swagger UI |
| GET | `/api/redoc` | — | ReDoc |
| GET | `/api/openapi.json` | — | OpenAPI Schema |

---

*Happy Forging!* 🔨
