# 实施计划：Pydantic v2 迁移 + 全量 Type Hints

## 任务类型
- [x] 后端 (→ codex)
- [ ] 前端 (→ codex)
- [ ] 全栈 (→ 并行)

## 技术方案

采用**边界优先混合迁移**策略：Pydantic 用于外部数据边界（YAML config、SQLite 行、任务载荷），TypedDict 用于 Telegram 会话状态，标准 annotations 用于内部逻辑。按依赖顺序逐层推进，每步后运行 `ty check` 验证。

### 核心设计决策

1. **Pydantic v2 BaseModel** 用于 config 和 DB 行模型（验证 + 序列化）
2. **TypedDict** 用于 `context.user_data`（部分填充、PTB 兼容）
3. **int enum (0/1)** 保留 `is_download` / `is_delete` 为 `DownloadFlag`/`DeleteFlag`，不转 `bool`
4. **date vs datetime**：`publish_date` 用 `date`，`created_at`/`completed_at` 用 `datetime`
5. **`import init` → `from app import init`**：修复包路径，消除 27 个 unresolved-import 错误
6. **不使用 pydantic-settings**：YAML 是唯一配置源，不需要环境变量覆盖语义

## 实施步骤

### Step 1: 修复包导入路径 — 消除 `unresolved-import` 错误

**目标：** 将所有 `import init` 替换为 `from app import init` 或 `import app.init as init`

**操作：**
- 全局替换 `import init` → `from app import init`（约 27 处）
- 全局替换 `from app.utils.sqlitelib import *` → `from app.utils.sqlitelib import SqlLiteLib`（消除 wildcard import）
- 确认 `app/__main__.py` 的 `sys.path` 设置兼容新导入方式
- 运行 `ty check` 验证 unresolved-import 错误消除

**预期产物：** 27 个 `unresolved-import` 错误消除

**风险：** 中等 — 可能暴露被 runtime path hack 隐藏的循环导入
**缓解：** 先改导入再做其他修改，逐文件测试启动

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/115bot.py:12` | 修改 | `import init` → `from app import init` |
| `app/core/*.py` (所有) | 修改 | 同上 |
| `app/handlers/*.py` (所有) | 修改 | 同上 + 移除 `from app.utils.sqlitelib import *` |
| `app/utils/sqlitelib.py:4` | 修改 | `import init` → `from app import init` |
| `app/__main__.py` | 检查 | 确认 sys.path 设置与新导入方式兼容 |

---

### Step 2: 添加 Pydantic 依赖 + 创建模型包结构

**目标：** 引入 pydantic，建立 `app/models/` 包

**操作：**
- `pyproject.toml` 添加 `pydantic>=2.0`
- 创建 `app/models/` 包结构

**包布局：**

```
app/models/
  __init__.py          # 统一导出
  base.py              # AppModel 基类 + ConfigDict
  enums.py             # DownloadFlag, DeleteFlag, StrmMode, LogLevel, DownloadUrlType
  config.py            # BotConfig 及所有嵌套配置模型
  db.py                # 6 个表的 Row + Create 模型
  context.py           # TypedDict 会话状态类型
  dto.py               # 任务载荷、API 响应 DTO
```

**预期产物：** 模型包框架就绪，尚未被其他模块引用

---

### Step 3: 实现配置模型 — 替换 `bot_config` 全局 dict

**目标：** `bot_config: dict` → `bot_config: BotConfig`

**核心模型（app/models/config.py）：**

```python
from pydantic import BaseModel, ConfigDict, Field

class PathMapItem(AppModel):
    name: str
    path: str

class CategoryFolderItem(AppModel):
    name: str
    display_name: str
    path_map: list[PathMapItem]

class CleanPolicyConfig(AppModel):
    switch: str = "on"
    less_than: str = "400M"

class AvDailyUpdateConfig(AppModel):
    enable: bool = False
    sync_time: str = "20:00"
    save_path: str = "/AV/日更"
    notify_me: bool = True
    sort_by_year_month: bool = False

class SehuaSectionConfig(AppModel):
    name: str
    save_path: str

class SehuaSpiderConfig(AppModel):
    enable: bool = False
    sync_time: str = "03:00"
    base_url: str = "www.sehuatang.net"
    sections: list[SehuaSectionConfig] = []
    notify_me: bool = True
    sort_by_year_month: bool = False

class SubConditionConfig(AppModel):
    zh_cn: bool = True
    dolby_vision: bool = False
    resolution_priority: list[int] = [2160, 1080]

class Aria2Config(AppModel):
    enable: bool = False
    device_name: str = "Aria2"
    host: str = ""
    port: int = 6800
    rpc_secret: str = ""
    download_path: str = "/Downloads"

class AIConfig(AppModel):
    api_url: str = ""
    api_key: str = ""
    model: str = ""

class JavbusCategoryConfig(AppModel):
    name: str
    route: str
    need_input: bool = False
    save_path: str

class JavbusRssConfig(AppModel):
    max_subscribe: int = 0
    timeout: int = 60
    category: list[JavbusCategoryConfig] = []
    notify_me: bool = True
    sort_by_year_month: bool = False

class T66ySectionConfig(AppModel):
    name: str
    save_path: str

class T66yRssConfig(AppModel):
    timeout: int = 60
    sections: list[T66ySectionConfig] = []
    notify_me: bool = True
    sort_by_year_month: bool = False

class RssHubConfig(AppModel):
    rss_host: str = ""
    javbus: JavbusRssConfig = JavbusRssConfig()
    t66y: T66yRssConfig = T66yRssConfig()

class BotConfig(AppModel):
    model_config = ConfigDict(protected_namespaces=(), extra="ignore")

    log_level: LogLevel = LogLevel.INFO
    bot_token: str
    allowed_user: int | str  # 兼容 int 和 str 两种配置方式
    bot_name: str | None = None
    bote_name: str | None = None  # 兼容拼写错误
    tg_api_id: int | None = None
    tg_api_hash: str | None = None
    app_115_id: str | None = Field(default=None, alias="115_app_id")

    clean_policy: CleanPolicyConfig = CleanPolicyConfig()
    category_folder: list[CategoryFolderItem] = []

    av_daily_update: AvDailyUpdateConfig = AvDailyUpdateConfig()
    sehua_spider: SehuaSpiderConfig = SehuaSpiderConfig()

    strm_mode: StrmMode = StrmMode.DISABLE
    strm_root: str = "/media/115"
    openlist_root: str = "/115"
    mount_root: str = "/CloudNAS/115"

    emby_server: str | None = None
    api_key: str | None = None

    sub_condition: SubConditionConfig = SubConditionConfig()
    aria2: Aria2Config = Aria2Config()
    ai: AIConfig = AIConfig()
    rsshub: RssHubConfig = RssHubConfig()

    selenium_timeout: int = 60
    offline_path: str | None = None
```

**迁移操作：**
- `app/init.py`: `bot_config = dict()` → `bot_config: BotConfig | None = None`
- `load_yaml_config()`: YAML dict → `BotConfig.model_validate(yaml_dict)`
- 全项目替换 `init.bot_config['key']` → `init.bot_config.key`（属性访问）
- 替换 `init.bot_config.get('key', default)` → 利用模型默认值

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/models/config.py` | 新建 | 所有配置模型 |
| `app/init.py:26` | 修改 | `bot_config` 类型改为 `BotConfig \| None` |
| `app/init.py:125-163` | 修改 | `load_yaml_config()` 使用 `BotConfig.model_validate()` |
| `app/init.py:280-288` | 修改 | `check_user()` 使用 typed config |
| `app/115bot.py` | 修改 | 所有 `bot_config[...]` → 属性访问 |
| `app/handlers/*.py` (所有) | 修改 | 所有 `bot_config.get(...)` → 属性访问 |
| `app/core/*.py` (所有) | 修改 | 同上 |

**风险：** 中高 — config 字段可能存在实际 YAML 中有但模型未覆盖的 key
**缓解：** `extra="ignore"` 初期容忍未建模字段；逐步补全

---

### Step 4: 实现 DB 行模型 — 替换 dict/tuple 返回值

**目标：** 6 个 SQLite 表的 Pydantic Row + Create 模型

**核心模型（app/models/db.py）：**

```python
from datetime import date, datetime
from app.models.enums import DownloadFlag, DeleteFlag

class OfflineTaskRow(AppModel):
    id: int
    title: str
    save_path: str
    magnet: str
    is_download: DownloadFlag = DownloadFlag.NO
    retry_count: int = 1
    completed_at: datetime | None = None
    created_at: datetime

class OfflineTaskCreate(AppModel):
    title: str
    save_path: str
    magnet: str

class AvDailyUpdateRow(AppModel):
    id: int
    av_number: str
    publish_date: date
    title: str
    post_url: str
    pub_url: str
    magnet: str
    is_download: DownloadFlag = DownloadFlag.NO
    created_at: datetime

class AvDailyUpdateCreate(AppModel):
    av_number: str
    publish_date: date
    title: str
    post_url: str
    pub_url: str
    magnet: str

class SubMovieRow(AppModel):
    id: int
    movie_name: str
    tmdb_id: int
    size: str | None = None
    category_folder: str
    is_download: DownloadFlag = DownloadFlag.NO
    download_url: str | None = None
    sub_user: int
    post_url: str | None = None
    is_delete: DeleteFlag = DeleteFlag.NO
    created_at: datetime

class SubMovieCreate(AppModel):
    movie_name: str
    tmdb_id: int
    sub_user: int
    category_folder: str

class SehuaDataRow(AppModel):
    id: int
    section_name: str
    av_number: str
    title: str
    movie_type: str
    size: str
    magnet: str
    post_url: str
    publish_date: date
    pub_url: str
    image_path: str
    save_path: str
    is_download: DownloadFlag = DownloadFlag.NO
    created_at: datetime

class SehuaDataCreate(AppModel):
    section_name: str
    av_number: str
    title: str
    movie_type: str
    size: str
    magnet: str
    post_url: str
    publish_date: date
    pub_url: str
    image_path: str
    save_path: str

class T66yRow(AppModel):
    id: int
    section_name: str
    movie_info: str | None = None
    title: str
    magnet: str
    poster_url: str | None = None
    publish_date: date
    pub_url: str
    save_path: str
    is_download: DownloadFlag = DownloadFlag.NO
    created_at: datetime

class T66yCreate(AppModel):
    section_name: str
    title: str
    movie_info: str | None = None
    poster_url: str | None = None
    magnet: str
    publish_date: date
    pub_url: str
    save_path: str

class JavbusRow(AppModel):
    id: int
    av_number: str
    actress: str | None = None
    sub_category: str
    movie_info: str | None = None
    title: str
    magnet: str
    poster_url: str | None = None
    publish_date: date
    pub_url: str
    save_path: str
    is_download: DownloadFlag = DownloadFlag.NO
    created_at: datetime

class JavbusCreate(AppModel):
    av_number: str
    actress: str | None = None
    sub_category: str
    movie_info: str | None = None
    title: str
    magnet: str
    poster_url: str | None = None
    publish_date: date
    pub_url: str
    save_path: str
```

**SqlLiteLib 增强（不破坏现有方法）：**

```python
# 新增泛型 typed 查询方法
from typing import TypeVar
from pydantic import BaseModel
T = TypeVar("T", bound=BaseModel)

def query_as(self, model: type[T], sql: str, params: tuple = ()) -> list[T]:
    """查询并返回 Pydantic 模型列表"""
    rows = self.query_all(sql, params)
    return [model.model_validate(row) for row in rows]

def query_one_as(self, model: type[T], sql: str, params: tuple = ()) -> T | None:
    """查询单行并返回 Pydantic 模型"""
    row = self.query_row_dict(sql, params)
    return model.model_validate(row) if row else None
```

**迁移操作：**
- 在 `SqlLiteLib` 中添加 `query_as()` 和 `query_one_as()` 方法
- 添加 `query_row_dict()` 方法（返回 `dict | None`）
- 逐模块将 `query_all()` 调用迁移到 `query_as(ModelRow, ...)`
- 优先迁移：`offline_task_retry.py`（使用最密集）、`av_daily_update.py`、`subscribe_movie.py`

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/models/db.py` | 新建 | 6 表 Row + Create 模型 |
| `app/utils/sqlitelib.py` | 修改 | 添加 `query_as()`, `query_one_as()`, `query_row_dict()` |
| `app/core/offline_task_retry.py` | 修改 | 使用 `OfflineTaskRow` 等模型 |
| `app/core/av_daily_update.py` | 修改 | 使用 `AvDailyUpdateRow`/`Create` |
| `app/core/subscribe_movie.py` | 修改 | 使用 `SubMovieRow`/`Create` |
| `app/core/sehua_spider.py` | 修改 | 使用 `SehuaDataRow`/`Create` |
| `app/core/javbus.py` | 修改 | 使用 `JavbusRow`/`Create` |
| `app/core/t66y.py` | 修改 | 使用 `T66yRow`/`Create` |
| `app/handlers/offline_task_handler.py` | 修改 | 使用 typed 查询 |

**风险：** 中等 — tuple 位置依赖可能在迁移过程中引入 bug
**缓解：** 新增 typed 方法平行存在，逐表迁移后删除旧调用

---

### Step 5: 实现会话状态类型 + 任务载荷 DTO

**目标：** `context.user_data` 添加 TypedDict 类型约束；任务载荷使用 Pydantic DTO

**会话状态 TypedDict（app/models/context.py）：**

```python
from typing import TypedDict, Any
from app.models.enums import DownloadUrlType

class DownloadUserData(TypedDict, total=False):
    link: str
    dl_url_type: DownloadUrlType
    selected_main_category: str
    selected_path: str

class AvDownloadUserData(TypedDict, total=False):
    link: str
    dl_url_type: DownloadUrlType
    av_number: str
    selected_main_category: str
    selected_path: str

class SubscribeMovieUserData(TypedDict, total=False):
    movie_name: str
    tmdb_id: int
    sub_user: int
    selected_main_category: str
    selected_path: str

class RssUserData(TypedDict, total=False):
    selected_main_category: str
    selected_path: str

class RenameData(TypedDict):
    user_id: int
    action: str
    final_path: str
    resource_name: str
    selected_path: str
    link: str
    add2retry: bool
```

**任务载荷 DTO（app/models/dto.py）：**

```python
class PendingTask(AppModel):
    user_id: int
    action: str
    final_path: str = ""
    resource_name: str = ""
    selected_path: str = ""
    link: str = ""
    add2retry: bool = False

class PendingPushTask(AppModel):
    path: str

class VideoTaskInfo(AppModel):
    file_name: str
    file_ext: str
    file_size: int
    message_id: int
    chat_id: int
```

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/models/context.py` | 新建 | TypedDict 会话类型 |
| `app/models/dto.py` | 新建 | 任务载荷 DTO |
| `app/handlers/download_handler.py` | 修改 | 使用 typed user_data, PendingTask |
| `app/handlers/av_download_handler.py` | 修改 | 使用 AvDownloadUserData |
| `app/handlers/subscribe_movie_handler.py` | 修改 | 使用 SubscribeMovieUserData |
| `app/handlers/rss_handler.py` | 修改 | 使用 RssUserData |
| `app/handlers/video_handler.py` | 修改 | 使用 VideoTaskInfo |
| `app/init.py` | 修改 | `pending_tasks: dict[str, PendingTask]` |

---

### Step 6: 全局变量类型标注 + init.py 重构

**目标：** 所有全局变量显式类型标注

**操作：**

```python
# app/init.py
from app.models.config import BotConfig
from app.utils.logger import Logger
from app.core.open_115 import OpenAPI_115
from telethon import TelegramClient

debug_mode: bool = False
logger: Logger | None = None
bot_config: BotConfig | None = None
openapi_115: OpenAPI_115 | None = None
tg_user_client: TelegramClient | None = None
aria2_client: Any = None  # aria2p 无类型 stub
CRAWL_SEHUA_STATUS: int = 0
CRAWL_JAV_STATUS: int = 0
bot_session: dict[str, str] = {}
pending_tasks: dict[str, PendingTask] = {}
pending_push_tasks: dict[str, PendingPushTask] = {}
```

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/init.py` | 修改 | 全局变量类型标注 |

---

### Step 7: 函数签名 Type Hints — 逐模块添加

**目标：** 所有函数/方法添加参数类型和返回类型

**优先顺序（按依赖层级从底向上）：**

1. **utils 层**（被其他所有模块依赖）
   - `app/utils/utils.py` — 纯工具函数
   - `app/utils/logger.py` — Logger 类方法
   - `app/utils/http_client.py` — HTTP 请求函数
   - `app/utils/sqlitelib.py` — 已在 Step 4 部分完成
   - `app/utils/message_queue.py` — 队列函数
   - `app/utils/aria2.py` — Aria2 工具
   - `app/utils/ai.py` — AI 相关
   - `app/utils/cover_capture.py` — 封面获取
   - `app/utils/alioss.py` — OSS 上传
   - `app/utils/fast_telethon.py` — Telethon 下载

2. **core 层**（业务逻辑）
   - `app/core/open_115.py` — OpenAPI_115 类（最大文件，分组标注）
   - `app/core/video_downloader.py` — VideoDownloadManager 类
   - `app/core/scheduler.py` — 调度器
   - `app/core/offline_task_retry.py` — 已在 Step 4 部分完成
   - `app/core/av_daily_update.py` — 同上
   - `app/core/subscribe_movie.py` — 同上
   - `app/core/sehua_spider.py`
   - `app/core/javbus.py`
   - `app/core/t66y.py`
   - `app/core/selenium_browser.py`

3. **handlers 层**（Telegram 处理器）
   - 所有 handler 函数签名已经有 `(update: Update, context: ContextTypes.DEFAULT_TYPE)` 
   - 需要添加返回类型 `-> int | None` 等
   - 标注内部 helper 函数

4. **入口层**
   - `app/115bot.py`
   - `app/__main__.py`

**OpenAPI_115 特殊处理：**
- 方法分组标注：纯 helper → 文件/路径 → HTTP 响应
- 仅建模最常用 API 响应（token payload、offline task item、file info）
- 其他响应暂用 `dict[str, Any]`

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/utils/*.py` (10 files) | 修改 | 函数签名 type hints |
| `app/core/*.py` (10 files) | 修改 | 函数签名 type hints |
| `app/handlers/*.py` (10 files) | 修改 | 返回类型 + helper 签名 |
| `app/115bot.py` | 修改 | 入口函数签名 |

---

### Step 8: 枚举迁移 + 清理

**目标：** 统一枚举定义到 `app/models/enums.py`

**操作：**
- 将 `DownloadUrlType` 从 `download_handler.py` 移至 `app/models/enums.py`
- 添加 `DownloadFlag`、`DeleteFlag`、`StrmMode`、`LogLevel` 枚举
- 更新所有引用

---

### Step 9: ty 错误扫尾 — 逐类修复

**目标：** 消除剩余 ty 诊断

**主要错误类型及修复策略：**

| 错误类型 | 数量 | 修复策略 |
|----------|------|---------|
| `unresolved-attribute` | 317 | 大部分被 Step 1-6 解决；剩余通过 `assert` 或 `if x is not None` narrowing |
| `invalid-argument-type` | 55 | 参数类型不匹配，逐个修复 |
| `unresolved-import` | 27 | Step 1 已解决 |
| `invalid-assignment` | 25 | 变量类型不一致，添加正确标注 |
| `not-subscriptable` | 20 | `None` 类型未 narrow，添加检查 |
| `unsupported-operator` | 4 | 类型推断问题 |
| `unresolved-reference` | 3 | 引用不存在的名称 |

**操作：**
- 逐文件运行 `ty check app/path/to/file.py`
- 对 `update.effective_chat` 添加 `assert update.effective_chat is not None`（PTB 框架保证）
- 对可选类型添加显式 narrowing

---

### Step 10: 验证与回归测试

**操作：**
1. `ty check` 全量运行，目标：0 error 或仅剩第三方库 stub 相关 warning
2. Bot 启动测试：`python -m app`
3. 关键功能手动验证：
   - 配置加载 (`load_yaml_config`)
   - 数据库初始化 (`init_db`)
   - 115 API 认证流程
   - 下载命令流程
   - 定时任务启动

---

## 关键文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `pyproject.toml` | 修改 | 添加 `pydantic>=2.0` |
| `app/models/__init__.py` | 新建 | 模型包入口 |
| `app/models/base.py` | 新建 | AppModel 基类 |
| `app/models/enums.py` | 新建 | 所有枚举 |
| `app/models/config.py` | 新建 | BotConfig + 嵌套配置模型 |
| `app/models/db.py` | 新建 | 6 表 Row + Create 模型 |
| `app/models/context.py` | 新建 | TypedDict 会话类型 |
| `app/models/dto.py` | 新建 | 任务载荷 DTO |
| `app/init.py` | 修改 | 全局变量类型 + config 加载重构 |
| `app/utils/sqlitelib.py` | 修改 | 添加 typed 查询方法 |
| `app/115bot.py` | 修改 | 导入修复 + type hints |
| `app/core/*.py` (10 files) | 修改 | 导入修复 + 模型使用 + type hints |
| `app/handlers/*.py` (10 files) | 修改 | 导入修复 + 模型使用 + type hints |
| `app/utils/*.py` (10 files) | 修改 | type hints |

## 风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|--------|---------|
| `import init` 修复暴露循环导入 | 中 | 逐文件修改并测试启动 |
| BotConfig 不覆盖所有 YAML 字段 | 中 | `extra="ignore"` 初期容忍 |
| SQLite 行到 Pydantic 转换丢失数据 | 中 | 保留旧方法并行，逐表迁移 |
| context.user_data TypedDict 不兼容 PTB 持久化 | 低 | TypedDict 向下兼容 dict |
| OpenAPI_115 响应模型不完整 | 中 | 仅建模常用响应，其余 `dict[str, Any]` |
| ty 检查器对第三方库（seleniumbase 等）报错 | 低 | `# type: ignore` 或 ty 配置排除 |

## SESSION_ID（供 /ccg:execute 使用）
- CODEX_SESSION: 019d8bd9-13c3-74e0-972c-0c2b1d5c92f1
- GEMINI_SESSION: 019d8bd9-4a6c-7661-b256-17eeb7710719
