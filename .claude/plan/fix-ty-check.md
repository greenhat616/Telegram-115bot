# 实施计划：修复全部 ty check 类型错误

## 任务类型
- [x] 后端 (→ codex)
- [ ] 前端 (→ codex)
- [ ] 全栈 (→ 并行)

## 技术方案

采用**边界收窄 + 集中式 accessor**策略，按基础设施层 → 应用层的顺序系统性消除 623 个 `ty check` 错误，而非逐文件零散修补。

### 错误分布（当前状态）

| 错误类型 | 数量 | 根因 |
|----------|------|------|
| `unresolved-attribute` | 498 | 全局单例 Optional + PTB Optional 字段 |
| `invalid-argument-type` | 63 | ConversationHandler 泛型不匹配 |
| `invalid-assignment` | 30 | `context.user_data` 为 None 时下标赋值 |
| `not-subscriptable` | 21 | `context.user_data` 为 None 时下标访问 |
| 其他 | 11 | 杂项（raise str、operator、iterable 等）|
| **合计** | **623** | |

### 核心设计决策（双模型共识）

1. **全局单例保持 `Optional` 类型声明**，但添加 `require_*()` accessor 函数返回非空值。不直接改成非 Optional（类型不诚实，启动阶段/reload 场景确实可能为 None）
2. **PTB Update 字段用专用 helper 收窄**（`require_message()`、`require_query()` 等），不用 decorator（ty 对装饰器的 narrowing 支持不够），不大面积 `# type: ignore`
3. **`context.user_data` 用 typed wrapper + 现有 TypedDict**，不裸写 `assert context.user_data is not None`
4. **ConversationHandler 用集中 wrapper/cast**，仅在 `register_*_handlers` 处理泛型摩擦；回调函数补明确返回类型
5. **ty 配置只做必要的**：`src.include/exclude` + 对 telethon 视需要做 `replace-imports-with-any`

---

## 实施步骤

### Step 1: ty 配置 — 建立检查基线

**目标：** 添加 `[tool.ty]` 配置，排除无关文件，建立可控的检查范围

**操作：**

在 `pyproject.toml` 末尾添加：

```toml
[tool.ty.src]
include = ["app", "create_tg_session_file.py"]

[tool.ty.rules]
# 暂时降级，在 Step 5 完成后可升回 error
# invalid-argument-type = "warn"

[tool.ty.analysis]
# 如 Step 6 后 telethon 仍有不可修复的 stub 问题，启用此项
# replace-imports-with-any = ["telethon.**"]
```

**预期效果：** 排除 `.venv`（ty 已默认排除）及非项目文件。错误数可能不变（ty 默认已排除 .venv），但建立了配置控制面。

| 文件 | 操作 | 说明 |
|------|------|------|
| `pyproject.toml` | 修改 | 添加 `[tool.ty]` 配置段 |

---

### Step 2: 全局单例 accessor — 消除 ~223 个 `unresolved-attribute`

**目标：** 为 `bot_config`、`openapi_115` 添加 `require_*()` accessor，将运行时不变量集中表达

**操作：**

在 `app/init.py` 中添加 accessor 函数：

```python
def require_bot_config() -> BotConfig:
    """获取已初始化的 BotConfig，未初始化时 AssertionError"""
    config = bot_config
    assert config is not None, "bot_config must be initialized before use"
    return config

def require_openapi_115() -> OpenAPI_115:
    """获取已初始化的 OpenAPI_115，未初始化时 AssertionError"""
    api = openapi_115
    assert api is not None, "openapi_115 must be initialized before use"
    return api
```

**全局替换规则：**

| 旧模式 | 新模式 | 影响 |
|--------|--------|------|
| `init.bot_config.xxx` | `config = init.require_bot_config()` + `config.xxx` | ~149 处 |
| `init.openapi_115.xxx()` | `api = init.require_openapi_115()` + `api.xxx()` | ~74 处 |

**重要：** 每个函数顶部只调用一次 `require_*()` 绑定到局部变量，函数体内使用局部变量。不要在每次属性访问处都调用 require。

**保留 Optional 的变量（不添加 accessor）：**
- `tg_user_client: TelegramClient | None` — 功能开关型，非所有场景必须
- `aria2_client: aria2p.API | None` — 同上

**预期效果：** 消除 ~223 个 `unresolved-attribute` 错误

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/init.py` | 修改 | 添加 `require_bot_config()`, `require_openapi_115()` |
| `app/115bot.py` | 修改 | 替换 `init.bot_config.xxx` → 局部变量 |
| `app/core/offline_task_retry.py` | 修改 | 替换 ~30 处引用 |
| `app/core/av_daily_update.py` | 修改 | 替换引用 |
| `app/core/subscribe_movie.py` | 修改 | 替换引用 |
| `app/core/sehua_spider.py` | 修改 | 替换引用 |
| `app/core/javbus.py` | 修改 | 替换引用 |
| `app/core/t66y.py` | 修改 | 替换引用 |
| `app/core/scheduler.py` | 修改 | 替换引用 |
| `app/handlers/*.py` (全部) | 修改 | 替换引用 |

---

### Step 3: PTB Update 收窄 helper — 消除 ~212 个 `unresolved-attribute`

**目标：** 为 PTB 的 Optional 字段提供统一收窄入口

**操作：**

新建 `app/utils/ptb_helpers.py`：

```python
from telegram import Update, Chat, User, Message, CallbackQuery

def require_chat(update: Update) -> Chat:
    """断言 effective_chat 存在（所有用户交互场景下均成立）"""
    chat = update.effective_chat
    assert chat is not None, "handler requires effective_chat"
    return chat

def require_user(update: Update) -> User:
    """断言 effective_user 存在"""
    user = update.effective_user
    assert user is not None, "handler requires effective_user"
    return user

def require_message(update: Update) -> Message:
    """断言 message 存在（用于命令/消息入口的 handler）"""
    message = update.message
    assert message is not None, "handler requires message"
    return message

def require_query(update: Update) -> CallbackQuery:
    """断言 callback_query 存在（用于回调入口的 handler）"""
    query = update.callback_query
    assert query is not None, "handler requires callback_query"
    return query

# 复合 helper，减少重复绑定
def require_message_parts(update: Update) -> tuple[Message, Chat, User]:
    """命令入口 handler 的标准收窄"""
    return require_message(update), require_chat(update), require_user(update)

def require_callback_parts(update: Update) -> tuple[CallbackQuery, Chat, User]:
    """回调入口 handler 的标准收窄"""
    return require_query(update), require_chat(update), require_user(update)
```

**Handler 改造模式：**

命令/消息入口 handler：
```python
async def start_d_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat, user = require_message_parts(update)
    if not init.check_user(user.id):
        await message.reply_text("⚠️ 对不起，您无权使用115机器人！")
        return ConversationHandler.END
    # ...
    await context.bot.send_message(chat_id=chat.id, text="...")
```

回调入口 handler：
```python
async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query, chat, user = require_callback_parts(update)
    await query.answer()
    selected = query.data
    # ...
```

**SeleniumBrowser 也需类似处理：**

在 `app/core/sehua_spider.py` 中，模块级 `browser: SeleniumBrowser | None = None` 的访问点添加局部 `assert browser is not None` 或函数内绑定后使用。

**预期效果：** 消除 ~212 个 `unresolved-attribute` + ~18 个 SeleniumBrowser 相关错误

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/utils/ptb_helpers.py` | 新建 | PTB 收窄 helper 函数 |
| `app/handlers/download_handler.py` | 修改 | 使用 helper（~87 errors） |
| `app/handlers/av_download_handler.py` | 修改 | 使用 helper（~71 errors） |
| `app/handlers/video_handler.py` | 修改 | 使用 helper（~52 errors） |
| `app/handlers/subscribe_movie_handler.py` | 修改 | 使用 helper（~50 errors） |
| `app/handlers/rss_handler.py` | 修改 | 使用 helper（~42 errors） |
| `app/handlers/sync_handler.py` | 修改 | 使用 helper（~28 errors） |
| `app/handlers/aria2_handler.py` | 修改 | 使用 helper（~19 errors） |
| `app/handlers/offline_task_handler.py` | 修改 | 使用 helper（~18 errors） |
| `app/handlers/crawl_handler.py` | 修改 | 使用 helper（~17 errors） |
| `app/handlers/auth_handler.py` | 修改 | 使用 helper（~15 errors） |
| `app/core/sehua_spider.py` | 修改 | browser narrowing（~18 errors） |

---

### Step 4: context.user_data typed wrapper — 消除 ~51 个 `invalid-assignment` + `not-subscriptable`

**目标：** 将 `context.user_data` 的 None 访问问题通过 typed wrapper 解决

**操作：**

在 `app/utils/ptb_helpers.py` 中追加：

```python
from typing import cast
from telegram.ext import ContextTypes
from app.models.context import (
    DownloadUserData, AvDownloadUserData,
    SubscribeMovieUserData, RssUserData
)

def require_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, object]:
    """断言 user_data 非空并返回"""
    data = context.user_data
    assert data is not None, "PTB user_data must be initialized"
    return data

def download_user_data(context: ContextTypes.DEFAULT_TYPE) -> DownloadUserData:
    data = context.user_data
    assert data is not None
    return cast(DownloadUserData, data)

def av_download_user_data(context: ContextTypes.DEFAULT_TYPE) -> AvDownloadUserData:
    data = context.user_data
    assert data is not None
    return cast(AvDownloadUserData, data)

def subscribe_user_data(context: ContextTypes.DEFAULT_TYPE) -> SubscribeMovieUserData:
    data = context.user_data
    assert data is not None
    return cast(SubscribeMovieUserData, data)

def rss_user_data(context: ContextTypes.DEFAULT_TYPE) -> RssUserData:
    data = context.user_data
    assert data is not None
    return cast(RssUserData, data)
```

**Handler 使用模式：**

```python
async def start_d_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = download_user_data(context)
    data["link"] = magnet_link
    data["dl_url_type"] = dl_url_type
```

**预期效果：** 消除 ~30 个 `invalid-assignment` + ~21 个 `not-subscriptable` = ~51 个错误

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/utils/ptb_helpers.py` | 修改 | 追加 user_data typed wrapper |
| `app/handlers/download_handler.py` | 修改 | 使用 `download_user_data()` |
| `app/handlers/av_download_handler.py` | 修改 | 使用 `av_download_user_data()` |
| `app/handlers/subscribe_movie_handler.py` | 修改 | 使用 `subscribe_user_data()` |
| `app/handlers/rss_handler.py` | 修改 | 使用 `rss_user_data()` |
| `app/handlers/crawl_handler.py` | 修改 | 使用 `require_user_data()` |

---

### Step 5: ConversationHandler 泛型修复 — 消除 ~63 个 `invalid-argument-type`

**目标：** 解决 ConversationHandler 构造参数的泛型不匹配

**操作：**

**5a. 给所有会话回调函数补明确返回类型：**

```python
# 之前
async def start_d_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ...
    return SELECT_MAIN_CATEGORY

# 之后
async def start_d_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ...
    return SELECT_MAIN_CATEGORY
```

**5b. 如果补返回类型后仍有泛型不匹配，在 register 函数处添加集中 wrapper：**

```python
from typing import cast
from telegram.ext import BaseHandler, ConversationHandler

type HandlerList = list[BaseHandler]  # type: ignore[type-arg]

def _make_conversation(
    *,
    entry_points: HandlerList,
    states: dict[object, HandlerList],
    fallbacks: HandlerList,
    **kwargs: object,
) -> ConversationHandler:
    return ConversationHandler(
        entry_points=entry_points,  # type: ignore[arg-type]
        states=states,  # type: ignore[arg-type]
        fallbacks=fallbacks,  # type: ignore[arg-type]
        **kwargs,
    )
```

**5c. 如果 wrapper 仍不够，使用 ty per-file overrides（最后手段）：**

```toml
[[tool.ty.overrides]]
include = [
  "app/handlers/auth_handler.py",
  "app/handlers/download_handler.py",
  "app/handlers/av_download_handler.py",
  "app/handlers/rss_handler.py",
  "app/handlers/subscribe_movie_handler.py",
  "app/handlers/sync_handler.py",
]
[tool.ty.overrides.rules]
invalid-argument-type = "warn"
```

**优先级：** 5a → 5b → 5c，逐级尝试，尽量在 5a 或 5b 阶段解决。

**预期效果：** 消除 ~63 个 `invalid-argument-type` 错误

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/handlers/download_handler.py` | 修改 | 回调返回类型 + register 函数 |
| `app/handlers/av_download_handler.py` | 修改 | 同上 |
| `app/handlers/rss_handler.py` | 修改 | 同上 |
| `app/handlers/subscribe_movie_handler.py` | 修改 | 同上 |
| `app/handlers/sync_handler.py` | 修改 | 同上 |
| `app/handlers/auth_handler.py` | 修改 | 同上 |
| `app/utils/ptb_helpers.py` | 修改 | 可能添加 ConversationHandler wrapper |
| `pyproject.toml` | 修改 | 视需要添加 overrides |

---

### Step 6: 杂项错误修复 — 消除 ~11 个零散错误

**目标：** 逐个修复剩余的非模式化错误

| 错误 | 位置 | 修复方式 |
|------|------|---------|
| `invalid-raise: Cannot raise str` | `app/handlers/download_handler.py:294` | `raise str(e)` → `raise Exception(str(e)) from e` |
| `invalid-raise: BaseException \| None` | `app/utils/http_client.py:77` | 添加 `assert outcome.exception() is not None` 或用 `if exc := outcome.exception(): raise exc` |
| `invalid-return-type` | `app/core/open_115.py:1522` | 检查函数签名与返回值的类型匹配 |
| `unsupported-operator: > on Optional[int]` | `app/handlers/av_download_handler.py:90` | `file.file_size` 可能为 None，添加 `assert file.file_size is not None` |
| `unsupported-operator: in on Optional[dict]` | `app/handlers/av_download_handler.py:128,188` | 已在 Step 4 中通过 typed wrapper 解决 |
| `not-iterable: TotalList \| Message \| None` | `app/handlers/video_handler.py:253,260` | 添加 `assert isinstance(recent_msgs, list)` |
| `invalid-await: TelegramClient` | `create_tg_session_file.py:122` | telethon 的 `client.start()` 返回类型问题，使用 `await client.start()  # type: ignore[misc]` |
| `no-matching-overload: bs4 find()` | `app/core/javbus.py:314` | 调整 find() 参数匹配重载签名 |

**预期效果：** 消除全部 ~11 个杂项错误

---

### Step 7: 全量验证 + 配置微调

**目标：** `ty check` 报 0 error

**操作：**

1. 运行 `ty check` 全量检查
2. 如有第三方 stub 残留问题（telethon），启用 `replace-imports-with-any`：
   ```toml
   [tool.ty.analysis]
   replace-imports-with-any = ["telethon.**"]
   ```
3. 运行 `python -m app` 确认启动正常
4. 对 `create_tg_session_file.py` 单独处理（独立脚本，少量 `# ty: ignore` 可接受）

---

## 关键文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `pyproject.toml` | 修改 | 添加 `[tool.ty]` 配置 |
| `app/init.py` | 修改 | 添加 `require_bot_config()`, `require_openapi_115()` |
| `app/utils/ptb_helpers.py` | 新建 | PTB 收窄 helper + user_data wrapper + ConversationHandler wrapper |
| `app/115bot.py` | 修改 | 使用 accessor + helper |
| `app/core/offline_task_retry.py` | 修改 | 使用 accessor + helper（最多改动） |
| `app/core/sehua_spider.py` | 修改 | browser narrowing + accessor |
| `app/core/javbus.py` | 修改 | accessor + bs4 修复 |
| `app/core/open_115.py` | 修改 | return type 修复 |
| `app/core/subscribe_movie.py` | 修改 | accessor |
| `app/core/av_daily_update.py` | 修改 | accessor |
| `app/core/scheduler.py` | 修改 | accessor |
| `app/core/t66y.py` | 修改 | accessor |
| `app/handlers/download_handler.py` | 修改 | 全套改造（87 errors） |
| `app/handlers/av_download_handler.py` | 修改 | 全套改造（71 errors） |
| `app/handlers/video_handler.py` | 修改 | helper + iterable 修复（52 errors） |
| `app/handlers/subscribe_movie_handler.py` | 修改 | 全套改造（50 errors） |
| `app/handlers/rss_handler.py` | 修改 | 全套改造（42 errors） |
| `app/handlers/sync_handler.py` | 修改 | helper 改造（28 errors） |
| `app/handlers/aria2_handler.py` | 修改 | helper 改造（19 errors） |
| `app/handlers/offline_task_handler.py` | 修改 | helper 改造（18 errors） |
| `app/handlers/crawl_handler.py` | 修改 | helper + user_data 改造（17 errors） |
| `app/handlers/auth_handler.py` | 修改 | helper 改造（15 errors） |
| `app/utils/http_client.py` | 修改 | invalid-raise 修复 |
| `create_tg_session_file.py` | 修改 | telethon typing 修复 |

## 预期错误消减

| Step | 消除错误数 | 剩余 | 说明 |
|------|-----------|------|------|
| Step 1 | ~0 | ~623 | 配置基线，不直接减少错误 |
| Step 2 | ~223 | ~400 | 全局单例 accessor |
| Step 3 | ~230 | ~170 | PTB Update 收窄 + SeleniumBrowser |
| Step 4 | ~51 | ~119 | context.user_data wrapper |
| Step 5 | ~63 | ~56 | ConversationHandler 泛型 |
| Step 6 | ~11 | ~45 | 杂项修复 |
| Step 7 | ~45 | 0 | 第三方残留 + 配置微调 |

## 风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|--------|---------|
| `require_*()` 在启动阶段 / reload 场景被误调用导致 AssertionError | 中 | 启动阶段代码保留显式 `if bot_config is not None` 判断；assert message 含上下文 |
| handler 改造量大，可能引入 runtime regression | 中 | 每 Step 后运行 bot 启动测试；改造不改变业务逻辑，仅添加 narrowing |
| ConversationHandler wrapper 中的 `type: ignore` 可能掩盖真实 bug | 低 | 限制在单个 wrapper 函数内，不扩散到业务代码 |
| telethon `replace-imports-with-any` 会丢失类型覆盖 | 低 | 项目中 telethon 使用点有限（~7 处），手动确保正确性 |
| ty 版本更新可能改变行为 | 低 | 在 `pyproject.toml` 中锁定 ty 版本或接受滚动更新 |

## SESSION_ID（供 /ccg:execute 使用）
- CODEX_SESSION: 019d8c4f-32c5-78b1-89bd-f7ebd2399ef8
- GEMINI_SESSION: 019d8c4f-60a0-7af0-ab52-a5fd72abe94e
