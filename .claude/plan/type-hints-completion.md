# 📋 实施计划：Type Hints 补全与类型安全增强

## 任务类型
- [x] 后端 (→ codex)
- [ ] 前端 (→ codex)
- [ ] 全栈 (→ 并行)

## 技术方案

综合双模型分析，采用**渐进式 typed wrapper + 局部缓存**方案：

1. **`require_user_data()` 泛型支持**：采用 per-handler typed wrapper 模式（非 overload generic），因 ty 对复杂泛型支持不够成熟
2. **`require_bot_config()` 缓存**：函数级局部变量，不使用模块级缓存（配置支持热加载）
3. **`ty:ignore` 消除**：分类处理 —— Optional narrowing > TypedDict shape > ConversationHandler stub（最后处理）
4. **Type hints 补全**：按耦合度从低到高，叶子模块优先

---

## 实施步骤

### Step 1：定义缺失的 TypedDict 数据形状
**预期产物**：更新 `app/models/context.py`

- 补充 `VideoUserData`、`CrawlUserData`、`SyncUserData`、`AuthUserData` TypedDict
- 将 `video_handler` 的动态 `video_{task_id}` 键重构为嵌套结构 `video_tasks: dict[str, VideoTaskInfo]`
- `RenameData` 已有定义，确认与 `PendingTask` Pydantic model 的映射关系

```python
# app/models/context.py - 新增

class VideoUserData(TypedDict, total=False):
    last_video_save_path: str
    video_rename_task_id: str
    video_tasks: dict[str, VideoTaskInfo]  # 替代 video_{task_id} 动态键

class CrawlUserData(TypedDict, total=False):
    date: str

class SyncUserData(TypedDict, total=False):
    selected_main_category: str
```

### Step 2：新增 per-handler typed wrapper 函数
**预期产物**：更新 `app/utils/ptb_helpers.py`

为每个 handler 的 conversation 流提供独立的 typed data accessor：

```python
# app/utils/ptb_helpers.py - 新增

from app.models.context import (
    DownloadUserData, AvDownloadUserData, SubscribeMovieUserData,
    RssUserData, VideoUserData, CrawlUserData, SyncUserData,
)
from typing import cast

def require_download_data(context: ContextTypes.DEFAULT_TYPE) -> DownloadUserData:
    return cast(DownloadUserData, require_user_data(context))

def require_av_download_data(context: ContextTypes.DEFAULT_TYPE) -> AvDownloadUserData:
    return cast(AvDownloadUserData, require_user_data(context))

def require_subscribe_movie_data(context: ContextTypes.DEFAULT_TYPE) -> SubscribeMovieUserData:
    return cast(SubscribeMovieUserData, require_user_data(context))

def require_rss_data(context: ContextTypes.DEFAULT_TYPE) -> RssUserData:
    return cast(RssUserData, require_user_data(context))

def require_video_data(context: ContextTypes.DEFAULT_TYPE) -> VideoUserData:
    return cast(VideoUserData, require_user_data(context))

def require_crawl_data(context: ContextTypes.DEFAULT_TYPE) -> CrawlUserData:
    return cast(CrawlUserData, require_user_data(context))

def require_sync_data(context: ContextTypes.DEFAULT_TYPE) -> SyncUserData:
    return cast(SyncUserData, require_user_data(context))
```

同时新增 PTB Optional narrowing helpers：

```python
def require_text(update: Update) -> str:
    """获取 message.text，为 None 时抛出 RuntimeError"""
    text = require_message(update).text
    if text is None:
        raise RuntimeError("handler requires message.text")
    return text

def require_document(update: Update) -> Document:
    """获取 message.document，为 None 时抛出 RuntimeError"""
    doc = require_message(update).document
    if doc is None:
        raise RuntimeError("handler requires message.document")
    return doc

def require_query_data(update: Update) -> str:
    """获取 callback_query.data，为 None 时抛出 RuntimeError"""
    data = require_query(update).data
    if data is None:
        raise RuntimeError("handler requires callback_query.data")
    return data
```

### Step 3：补全叶子 utils 模块的 type hints
**预期产物**：更新 `app/utils/` 下所有文件

优先级顺序：
1. `app/utils/ai.py` — 5 个函数，全部缺失类型
2. `app/utils/aria2.py` — 7 个函数，全部缺失类型
3. `app/utils/message_queue.py` — 3 个函数，全部缺失类型
4. `app/utils/http_client.py` — 9 个函数，部分缺失返回类型
5. `app/utils/cover_capture.py` — 检查并补全
6. `app/utils/alioss.py` — 检查并补全
7. `app/utils/sqlitelib.py` — 部分已有，补全缺失的

示例标注：
```python
# app/utils/ai.py
def check_ai_api_available() -> bool: ...
def chat_completion(tip_words: str, max_tokens: int = 8192) -> dict[str, object] | None: ...
def get_movie_tmdb_name_with_ai(movie_desc: str) -> str | None: ...

# app/utils/aria2.py
def create_aria2_client(host: str, port: int, secret: str) -> aria2p.API | None: ...
def download_by_url(download_url: str, save_path: str = "") -> aria2p.Download | None: ...
def check_status_by_url(download_url: str) -> dict[str, object]: ...
def check_status_by_gid(gid: str) -> dict[str, object]: ...
def get_status(download: aria2p.Download) -> dict[str, object]: ...

# app/utils/message_queue.py
def add_task_to_queue(sub_user: int | str, post_url: str | None, message: str,
                      keyboard: InlineKeyboardMarkup | None = None,
                      retry_count: int = 0) -> bool: ...
async def queue_worker(loop: asyncio.AbstractEventLoop, token: str) -> None: ...

# app/utils/http_client.py
def http_request(method: str, url: str, **kwargs: object) -> httpx.Response: ...
def http_request_fast(method: str, url: str, **kwargs: object) -> httpx.Response: ...
def http_request_long(method: str, url: str, **kwargs: object) -> httpx.Response: ...
```

### Step 4：缓存 `require_bot_config()` 到局部变量
**预期产物**：更新以下文件中的重复调用

| 文件 | 当前调用次数 | 策略 |
|------|-------------|------|
| `app/core/offline_task_retry.py` | 37 | 每个顶层函数开头 `config = init.require_bot_config()` |
| `app/handlers/rss_handler.py` | 8 | 同上 |
| `app/handlers/sync_handler.py` | 6 | 同上 |
| `app/utils/ai.py` | 5 | `config = init.require_bot_config(); ai = config.ai` |
| `app/handlers/av_download_handler.py` | 5 | 同上 |
| `app/handlers/subscribe_movie_handler.py` | 4 | 同上 |
| `app/core/open_115.py` | ~10 | 在方法内缓存 |
| `app/core/sehua_spider.py` | ~8 | 同上 |
| `app/core/t66y.py` | ~5 | 同上 |
| `app/core/javbus.py` | ~3 | 同上 |
| `app/handlers/video_handler.py` | ~4 | 同上 |

缓存模式：
```python
# Before:
def chat_completion(tip_words, max_tokens=8192):
    url = init.require_bot_config().ai.api_url
    model = init.require_bot_config().ai.model
    api_key = init.require_bot_config().ai.api_key

# After:
def chat_completion(tip_words: str, max_tokens: int = 8192) -> dict[str, object] | None:
    config = init.require_bot_config()
    ai = config.ai
    url = ai.api_url
    model = ai.model
    api_key = ai.api_key
```

### Step 5：迁移 handlers 使用 typed wrapper
**预期产物**：更新所有 handler 文件

按 conversation domain 逐个迁移：

1. `app/handlers/download_handler.py` → `require_download_data(context)`
2. `app/handlers/av_download_handler.py` → `require_av_download_data(context)`
3. `app/handlers/subscribe_movie_handler.py` → `require_subscribe_movie_data(context)`
4. `app/handlers/rss_handler.py` → `require_rss_data(context)`
5. `app/handlers/sync_handler.py` → `require_sync_data(context)`
6. `app/handlers/crawl_handler.py` → `require_crawl_data(context)`
7. `app/handlers/video_handler.py` → `require_video_data(context)` + 重构动态键

迁移模式：
```python
# Before:
data = require_user_data(context)
data["rss_main_category"] = main_category  # ty sees: dict[str, object]

# After:
data = require_rss_data(context)
data["rss_main_category"] = main_category  # ty sees: RssUserData
```

video_handler 特殊处理 — 重构动态键：
```python
# Before:
require_user_data(context)[f"video_{task_id}"] = {...}
video_info = require_user_data(context).get(f"video_{task_id}")

# After:
data = require_video_data(context)
tasks = data.setdefault("video_tasks", {})
tasks[task_id] = VideoTaskInfo(...)
video_info = data.get("video_tasks", {}).get(task_id)
```

### Step 6：消除 `ty:ignore[unresolved-attribute]` — Optional narrowing
**预期产物**：更新 handler 文件，移除约 30 个 `ty:ignore[unresolved-attribute]`

使用 Step 2 新增的 narrowing helpers：

```python
# Before:
user_input = require_message(update).text.strip()  # ty:ignore[unresolved-attribute]

# After:
user_input = require_text(update).strip()
```

```python
# Before:
task_id = query.data.replace("retry_", "")  # ty:ignore[unresolved-attribute]

# After:
query_data = require_query_data(update)
task_id = query_data.replace("retry_", "")
```

```python
# Before:
file = await context.bot.get_file(require_message(update).document.file_id)  # ty:ignore
if file.file_size > 20 * 1024 * 1024:  # ty:ignore

# After:
doc = require_document(update)
file = await context.bot.get_file(doc.file_id)
if (file.file_size or 0) > 20 * 1024 * 1024:
```

### Step 7：消除 `ty:ignore[not-subscriptable]` — Dict shape typing
**预期产物**：更新 handler 文件，移除约 10 个 `ty:ignore[not-subscriptable]`

这些主要来自 `require_user_data()` 返回 `dict[str, object]` 导致的下标访问问题。
Step 5 迁移到 typed wrapper 后，这些将自动消除。

### Step 8：消除 `ty:ignore[invalid-assignment]` 和杂项
**预期产物**：更新少量文件

- `app/handlers/av_download_handler.py:188` — `bot_session['av_last_save']` 类型问题，需检查 `bot_session` 的 value type
- `app/init.py:249` — proxy tuple 赋值，需要 cast 或更精确的类型
- `app/core/open_115.py:1522` — 返回值类型问题，补全函数返回类型

### Step 9：补全 `app/core/` 模块的 type hints
**预期产物**：更新 core 模块函数签名

按文件大小和重要性排序：
1. `app/core/open_115.py` — 50+ 方法，最核心的 API 封装
2. `app/core/offline_task_retry.py` — 20+ 函数
3. `app/core/sehua_spider.py` — 20+ 函数
4. `app/core/av_daily_update.py` — 10+ 函数
5. `app/core/javbus.py` — 10+ 函数
6. `app/core/t66y.py` — 8+ 函数
7. `app/core/subscribe_movie.py` — 8+ 函数
8. `app/core/selenium_browser.py` — 15+ 方法
9. `app/core/video_downloader.py` — 10+ 方法
10. `app/core/scheduler.py` — 5 函数

### Step 10：补全 `app/init.py` 和 `app/115bot.py` 的 type hints
**预期产物**：更新启动和初始化模块

```python
# app/init.py
def create_logger() -> None: ...
def load_yaml_config() -> None: ...
def get_bot_token() -> str: ...
def create_tmp() -> None: ...
def check_user(user_id: int | str) -> bool: ...
def initialize_tg_usr_client() -> bool: ...
def initialize_115open() -> bool: ...
def create_tg_session_file() -> bool: ...
def init_aria2() -> None: ...
def init_db() -> None: ...
def init() -> None: ...
```

### Step 11：处理 `ConversationHandler` `invalid-argument-type` 残留
**预期产物**：尝试缩小范围，保留不可消除的

- 为 `register_*_handlers` 函数添加 `Application` 类型参数注解
- 尝试使用 PTB v22.7 的类型签名，看是否可以消除部分 `invalid-argument-type`
- **不可消除的保留为已知限制**，在 `pyproject.toml` 中维持现有抑制策略

### Step 12：运行 ty 检查 + 清理残余
**预期产物**：干净的 ty 检查报告

- 每完成一批（对应上面每 2-3 个 Step）运行一次 `ty check`
- 移除已解决的 `ty:ignore`
- 记录不可消除的残余，更新 `pyproject.toml` 中的抑制规则

---

## 关键文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/models/context.py` | 修改 | 新增 VideoUserData, CrawlUserData, SyncUserData TypedDict |
| `app/utils/ptb_helpers.py` | 修改 | 新增 per-handler typed wrappers + narrowing helpers |
| `app/utils/ai.py` | 修改 | 补全 type hints + 缓存 config |
| `app/utils/aria2.py` | 修改 | 补全 type hints |
| `app/utils/message_queue.py` | 修改 | 补全 type hints |
| `app/utils/http_client.py` | 修改 | 补全返回类型 |
| `app/utils/cover_capture.py` | 修改 | 补全 type hints |
| `app/handlers/download_handler.py` | 修改 | 迁移 typed data + narrowing + 缓存 config |
| `app/handlers/av_download_handler.py` | 修改 | 同上 |
| `app/handlers/subscribe_movie_handler.py` | 修改 | 同上 |
| `app/handlers/rss_handler.py` | 修改 | 同上 |
| `app/handlers/sync_handler.py` | 修改 | 同上 |
| `app/handlers/video_handler.py` | 修改 | 同上 + 重构动态键 |
| `app/handlers/crawl_handler.py` | 修改 | 同上 |
| `app/handlers/auth_handler.py` | 修改 | 补全 type hints |
| `app/handlers/offline_task_handler.py` | 修改 | 补全 type hints |
| `app/handlers/aria2_handler.py` | 修改 | 补全 type hints + 缓存 config |
| `app/core/open_115.py` | 修改 | 补全 50+ 方法 type hints + 缓存 config |
| `app/core/offline_task_retry.py` | 修改 | 补全 type hints + 缓存 config（37 处） |
| `app/core/sehua_spider.py` | 修改 | 补全 type hints + 缓存 config |
| `app/core/av_daily_update.py` | 修改 | 补全 type hints |
| `app/core/javbus.py` | 修改 | 补全 type hints |
| `app/core/t66y.py` | 修改 | 补全 type hints |
| `app/core/subscribe_movie.py` | 修改 | 补全 type hints |
| `app/core/selenium_browser.py` | 修改 | 补全 type hints |
| `app/core/video_downloader.py` | 修改 | 补全 type hints |
| `app/core/scheduler.py` | 修改 | 补全 type hints |
| `app/init.py` | 修改 | 补全 type hints |
| `app/115bot.py` | 修改 | 补全 type hints |

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| video_handler 动态键重构可能引入运行时 bug | 保持向后兼容的 fallback，先测试后切换 |
| ty (Red Knot) 对 TypedDict + cast 支持不完善 | 使用最简单的 cast 模式，避免复杂泛型 |
| 大批量修改可能引入拼写错误 | 每完成 2-3 步运行 ty check 验证 |
| ConversationHandler stub 无法完全消除 | 保留为已知限制，不强求 zero warnings |
| 函数局部缓存 config 可能导致长生命周期函数使用过时配置 | 对于定时任务等长生命周期函数保持每次调用获取最新 config |

## 统计预估

- 需补全 type hints 的函数：约 279 个（172 core + 46 utils + 38 handlers + 其他）
- 需缓存 config 的函数：约 40 个（跨 11 个文件）
- 需消除的 ty:ignore：约 70+ 处（约 30 可通过 narrowing 消除，10 通过 TypedDict 消除，15 为 PTB 限制保留，15 通过精确类型消除）
- 预计涉及文件：28 个 .py 文件

## SESSION_ID（供 /ccg:execute 使用）
- CODEX_SESSION: 019d8fa6-8e04-7630-b7e4-9dfe2d589885
- GEMINI_SESSION: 019d8fa6-b086-7081-b139-6410e563e2ca
