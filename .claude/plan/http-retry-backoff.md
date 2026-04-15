# HTTP Retry with Exponential Backoff (httpx + tenacity)

## 任务类型
- [x] 后端

## 技术方案

**迁移 `requests` → `httpx`，引入 `tenacity` 实现重试策略。**

### 为什么选 httpx + tenacity

| 维度 | requests + urllib3 Retry | httpx + tenacity |
|------|--------------------------|------------------|
| Async 支持 | 无，必须 `asyncio.to_thread` | 原生 `AsyncClient`，未来可直接在 async handler 中使用 |
| 重试控制 | urllib3 Retry 在传输层，无法在 retry 间插入业务逻辑（如限流锁） | tenacity 在应用层，`before_sleep` 回调可插入任意逻辑 |
| 超时 API | `timeout=(connect, read)` 元组 | `httpx.Timeout(timeout, connect=connect)` 结构化对象 |
| 连接池 | 需要手动 Session + HTTPAdapter | `httpx.Client` 内置连接池 |
| 维护状态 | requests 已进入维护模式 | httpx 活跃开发 |
| 新增依赖 | 无 | +httpx, +tenacity（各 ~100KB） |

### 架构决策

1. **本次迁移范围**：`requests` → `httpx` 同步 Client（`httpx.Client`）。所有现有调用保持同步语义不变，不改动 `asyncio.to_thread` 结构。
2. **未来优化**：async handler 中可逐步迁移为 `httpx.AsyncClient` 直接调用，移除 `to_thread` 包装。本次不做。
3. **tenacity 策略分层**：
   - **115 API**：tenacity 装饰 `_make_api_request`，`before` 回调执行限流槽获取
   - **非 115 HTTP**：tenacity 装饰统一工具函数 `http_request`
4. **`handle_token_expiry`**：收窄为仅处理 token 语义，网络异常由 tenacity 在 `_make_api_request` 层处理

### 核心原则
- 可重试：`httpx.ConnectError`、`httpx.TimeoutException`、`httpx.RemoteProtocolError`、HTTP `500/502/503/504`
- 不可重试：所有 `4xx`（业务错误）
- 115 API：每次 retry attempt 重走限流锁 + 风控检查
- 指数退避：`wait_exponential(multiplier=1, min=1, max=30)` + jitter

---

## 实施步骤

### Step 1: 更新依赖

**文件**: `requirements.txt`

```diff
-Requests==2.32.5
+httpx>=0.28.1
+tenacity>=9.1.2
```

> `requests` 暂时保留（`seleniumbase` 可能间接依赖），但项目代码不再直接使用。

### Step 2: 新增 `app/utils/http_client.py` — 统一 HTTP 工具

新增文件，封装 httpx Client + tenacity 重试策略。

```python
# app/utils/http_client.py
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, wait_random,
    retry_if_exception_type, retry_if_result, before_sleep_log
)
import logging

logger = logging.getLogger(__name__)

# --- 可重试异常 ---
RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)

# --- 可重试 HTTP 状态码 ---
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

def _is_retryable_response(response):
    """tenacity retry_if_result 回调：判断响应是否需要重试"""
    if isinstance(response, httpx.Response):
        return response.status_code in RETRYABLE_STATUS_CODES
    return False

# --- 共享 Client（同步） ---
# 默认：连接池复用，适合大多数场景
_default_client = httpx.Client(
    timeout=httpx.Timeout(30.0, connect=5.0),
    follow_redirects=True,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
)

# 长 I/O：AI API、Flaresolverr 等
_long_io_client = httpx.Client(
    timeout=httpx.Timeout(120.0, connect=10.0),
    follow_redirects=True,
)

# --- 带重试的请求函数 ---

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=0.5, max=10) + wait_random(0, 0.5),
    retry=(
        retry_if_exception_type(RETRYABLE_EXCEPTIONS)
        | retry_if_result(_is_retryable_response)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def http_request(method, url, *, client=None, **kwargs):
    """通用带重试的 HTTP 请求（同步）"""
    c = client or _default_client
    return c.request(method, url, **kwargs)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.3, max=3),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def http_request_fast(method, url, **kwargs):
    """快速失败版：RSS 检查、Emby 通知等（最多 2 次，短退避）"""
    return _default_client.request(method, url, **kwargs)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=15) + wait_random(0, 1),
    retry=(
        retry_if_exception_type(RETRYABLE_EXCEPTIONS)
        | retry_if_result(_is_retryable_response)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def http_request_long(method, url, **kwargs):
    """长 I/O 版：AI API、Flaresolverr 等"""
    return _long_io_client.request(method, url, **kwargs)


# --- 便捷方法 ---
def get(url, **kwargs):
    return http_request("GET", url, **kwargs)

def post(url, **kwargs):
    return http_request("POST", url, **kwargs)
```

### Step 3: 重构 `app/core/open_115.py` — 115 API 专用重试

#### 3.1 替换 `import requests` → `import httpx`

```diff
-import requests
+import httpx
```

#### 3.2 收窄 `handle_token_expiry`（line 26-76）

**删除**泛 Exception 重试分支。只保留 token 语义处理：

```python
def handle_token_expiry(func):
    """装饰器：仅处理 token 过期（40140125），网络异常由 _make_api_request 的 tenacity 处理"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        response = func(self, *args, **kwargs)
        if isinstance(response, dict) and response.get('code') == 40140125:
            init.logger.info("Token需要刷新，正在刷新后重试...")
            self.refresh_access_token()
            time.sleep(0.5)
            response = func(self, *args, **kwargs)
            if isinstance(response, dict) and response.get('code') == 40140125:
                init.logger.warn("Token刷新后仍然失败")
        # 保留其他业务错误码的日志
        if isinstance(response, dict) and 'code' in response:
            code = response['code']
            if code in (40140116, 40140119):
                init.logger.warn("Access token 已过期，请重新授权！")
            elif code == 40140118:
                init.logger.warn("开发者认证已过期，请到115开放平台重新授权！")
            elif code == 40140110:
                init.logger.warn("应用已过期，请到115开放平台重新授权！")
            elif code == 40140109:
                init.logger.warn("应用被停用，请到115开放平台查询详细信息！")
            elif code == 40140108:
                init.logger.warn("应用审核未通过，请稍后再试！")
        return response
    return wrapper
```

#### 3.3 抽取 `_acquire_request_slot` + 用 tenacity 改造 `_make_api_request`

```python
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random, retry_if_exception_type

def _acquire_request_slot(self):
    """获取请求槽位（限流 + 风控）"""
    with self.lock:
        if self.check_risk():
            return False, {"code": -1, "message": "今日请求即将到达上限！请明日再试！"}
        min_interval = 0.5
        elapsed = time.time() - self.last_req_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_req_time = time.time()
        return True, None

# 115 API 专用可重试异常
_115_RETRYABLE = (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 0.5),
    retry=retry_if_exception_type(_115_RETRYABLE),
    reraise=True,
)
def _make_api_request(self, method, url, params=None, data=None, headers=None):
    # 每次 attempt（含重试）都重新走限流
    ok, risk_resp = self._acquire_request_slot()
    if not ok:
        return risk_resp
    if headers is None:
        headers = self._get_headers()

    response = httpx.request(method, url, headers=headers, params=params,
                             data=data, timeout=httpx.Timeout(30.0, connect=5.0))
    if response.status_code == 200:
        return response.json()
    if response.status_code in (500, 502, 503, 504):
        # 抛异常触发 tenacity 重试
        raise httpx.HTTPStatusError(
            f"Server error {response.status_code}",
            request=response.request, response=response
        )
    init.logger.warn(f"API请求失败: {response.status_code} - {response.text}")
    return {"code": response.status_code, "message": response.text}
```

**注意**：`httpx.HTTPStatusError` 加入 `_115_RETRYABLE` 元组，或单独判断。更简洁的做法是在 5xx 时构造一个自定义异常。

#### 3.4 115 认证请求补重试

- `refresh_access_token()` (line 239): `requests.post` → `httpx.post`，用 tenacity 装饰（max 2 次）
- `auth_pkce()` 的 `authDeviceCode`/`deviceCodeToToken` (line 127, 183): 同上
- QR 码状态轮询 (line 164): `requests.get` → `httpx.get`，**不加 retry**（已有业务循环）

### Step 4: 批量迁移非 115 HTTP 调用

所有 `requests.get/post` → `http_request` / `http_request_fast` / `http_request_long`：

| 文件 | 行号 | 迁移方式 | 重试策略 |
|------|------|----------|----------|
| `av_daily_update.py` | 40,54,75,117,294 | `http_request("GET", url, verify=False, ...)` | 默认 3次 |
| `subscribe_movie.py` | 30 | `http_request("GET", url, headers=..., timeout=...)` | 默认 3次 |
| `subscribe_movie.py` | 191 | `http_request("GET", url, headers=..., ...)` | 默认 3次 |
| `javbus.py` | 105,142 | `http_request("GET", url, ...)` (in executor) | 默认 3次 |
| `t66y.py` | 256 | `http_request("GET", rss_url, ...)` | 默认 3次 |
| `cover_capture.py` | 28,50 | `http_request("GET", url, headers=..., ...)` | 默认 3次 |
| `av_download_handler.py` | 225 | `http_request("GET", url, ...)` | 默认 3次 |
| `rss_handler.py` | 180 | `http_request_fast("GET", rss_host, timeout=...)` | 快速 2次 |
| `download_handler.py` | 283 | `http_request_fast("POST", url, headers=..., json=...)` | 快速 2次 |
| `ai.py` | 49 | `http_request_long("POST", url, json=..., headers=...)` | 长IO 2次 |
| `selenium_browser.py` | 269 | `http_request_long("POST", url, json=..., headers=..., timeout=...)` | 长IO 2次 |

**每个文件的改动**：
1. `import requests` → `from app.utils.http_client import http_request[_fast|_long]`
2. `requests.get(url, ...)` → `http_request("GET", url, ...)`
3. `requests.post(url, ...)` → `http_request("POST", url, ...)`
4. `requests.RequestException` → `httpx.HTTPError`
5. `timeout=(connect, read)` → `timeout=httpx.Timeout(read, connect=connect)`

**注意**：
- `av_daily_update.py:75`（`crawl_javbee` 分页）当前漏了 timeout，需补上
- `verify=False` 在 httpx 中语法相同
- `response.json()`, `.text`, `.status_code`, `.content` 无需改动

### Step 5: 清理 `asyncio.to_thread` 中的异常类型

上一轮 commit 中 handler 使用了 `asyncio.to_thread` 包装同步调用。如果被包装的函数现在抛 `httpx.*` 异常而非 `requests.*`，需要确保外层 catch 对齐。

检查点：
- `auth_handler.py` — 无显式 catch
- `sync_handler.py` — catch `Exception`，无需改
- `aria2_handler.py` — catch `Exception`，无需改
- `download_handler.py` — catch `Exception`，无需改
- `av_download_handler.py` — 无显式 catch（在 thread pool 里有 try/except Exception）
- `rss_handler.py` — `requests.RequestException` → `httpx.HTTPError`
- `javbus.py` — `requests.RequestException` → `httpx.HTTPError`

---

## 关键文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `requirements.txt` | 修改 | +httpx, +tenacity |
| `app/utils/http_client.py` | **新增** | httpx Client + tenacity 重试策略封装 |
| `app/core/open_115.py` | 修改 | requests→httpx, handle_token_expiry 收窄, _make_api_request 加 tenacity |
| `app/core/av_daily_update.py` | 修改 | 5 处迁移，补 L75 timeout |
| `app/core/subscribe_movie.py` | 修改 | 2 处迁移 |
| `app/core/javbus.py` | 修改 | 2 处迁移 + RequestException→HTTPError |
| `app/core/t66y.py` | 修改 | 1 处迁移 |
| `app/core/selenium_browser.py` | 修改 | 1 处迁移 |
| `app/handlers/download_handler.py` | 修改 | 1 处迁移 (Emby) |
| `app/handlers/av_download_handler.py` | 修改 | 1 处迁移 (Sukebei) |
| `app/handlers/rss_handler.py` | 修改 | 1 处迁移 + RequestException→HTTPError |
| `app/utils/ai.py` | 修改 | 1 处迁移 |
| `app/utils/cover_capture.py` | 修改 | 2 处迁移 |

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| httpx API 差异导致运行时错误 | httpx 与 requests 的 response API 高度兼容；主要差异是 timeout 格式和异常类型，逐文件检查 |
| 115 API 重试放大风控 | tenacity 的 `before` 每次重新走 `_acquire_request_slot()`，max 3 次 |
| POST 重试幂等性 | 已确认所有 POST 调用场景可安全重试 |
| seleniumbase 间接依赖 requests | requests 保留在 deps 中但项目代码不直接使用 |
| tenacity + handle_token_expiry 叠加 | handle_token_expiry 只处理 token，不捕获网络异常 |

## Commit 规划

1. `chore: add httpx and tenacity dependencies`
2. `feat: add http_client utility with tenacity retry policies`
3. `refactor: migrate open_115 from requests to httpx with tenacity retry`
4. `refactor: migrate all non-115 HTTP calls from requests to httpx`
5. `fix: align exception types after httpx migration`

## SESSION_ID（供 /ccg:execute 使用）
- CODEX_SESSION (analyzer): 019d8bb4-c42a-7120-a508-8373d045780a
- CODEX_SESSION (architect): 019d8bb4-e516-7dc2-898c-a8206b0061e0
