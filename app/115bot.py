# -*- coding: utf-8 -*-

import os
import time
import asyncio
import threading
from typing import Any
from importlib.metadata import version as pkg_version

import httpx
from telegram import Update, BotCommand
from telegram.ext import ContextTypes, CommandHandler, Application
from telegram.request import HTTPXRequest
from telegram.helpers import escape_markdown

# 导入init模块（此时__init__.py已经设置了模块路径）
from app import init

from app.utils.message_queue import add_task_to_queue, queue_worker
from app.handlers.auth_handler import register_auth_handlers
from app.handlers.download_handler import register_download_handlers
from app.handlers.sync_handler import register_sync_handlers
from app.handlers.video_handler import register_video_handlers
from app.core.scheduler import start_scheduler_in_thread
from app.handlers.subscribe_movie_handler import register_subscribe_movie_handlers
from app.handlers.av_download_handler import register_av_download_handlers
from app.handlers.offline_task_handler import register_offline_task_handlers
from app.handlers.aria2_handler import register_aria2_handlers
from app.handlers.crawl_handler import register_crawl_handlers
from app.handlers.rss_handler import register_rss_handlers


# Polling 健康检查配置
_polling_health_failures = 0
_POLLING_HEALTH_FAILURE_LIMIT = 3  # 3 次失败后尝试重建
_POLLING_STALE_THRESHOLD = (
    105.0  # run_polling timeout(30) + read_timeout(60) + slack(15)
)
_polling_reconnect_attempts = 0
_MAX_RECONNECT_ATTEMPTS = 3  # 最多尝试重建 3 次


class PollingAwareHTTPXRequest(HTTPXRequest):
    """追踪 getUpdates 最后成功响应时间的 HTTPXRequest 子类"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.last_poll_ok_at = time.monotonic()
        self._consecutive_errors = 0

    async def do_request(self, *args: Any, **kwargs: Any) -> tuple[int, bytes]:
        try:
            result = await super().do_request(*args, **kwargs)
            self.last_poll_ok_at = time.monotonic()
            if self._consecutive_errors > 0:
                init.logger.info(
                    f"Polling request recovered after {self._consecutive_errors} consecutive errors."
                )
                self._consecutive_errors = 0
            return result
        except httpx.ConnectError as e:
            self._consecutive_errors += 1
            init.logger.warning(
                f"Polling ConnectError ({self._consecutive_errors}): {e}"
            )
            raise
        except httpx.TimeoutException as e:
            self._consecutive_errors += 1
            init.logger.warning(
                f"Polling TimeoutException ({self._consecutive_errors}): {e}"
            )
            raise


def get_version(md_format: bool = False) -> str:
    version = f"v{pkg_version('telegram-115bot')}"
    if md_format:
        return escape_markdown(version, version=2)
    return version


def get_help_info() -> str:
    version = get_version()
    help_info = f"""
<b>🍿 Telegram-115Bot {version} 使用手册</b>\n\n
<b>🔧 命令列表</b>\n
<code>/start</code> - 显示帮助信息\n
<code>/auth</code> - <i>115扫码授权 (解除授权后使用)</i>\n
<code>/reload</code> - <i>重载配置</i>\n
<code>/rl</code> - 查看重试列表\n
<code>/av</code> - <i>下载番号资源 (自动匹配磁力)</i>\n
<code>/csh</code> - <i>手动爬取涩花数据</i>\n
<code>/cjav</code> - <i>手动爬取javbee数据</i>\n
<code>/rss</code> - <i>rss订阅</i>\n
<code>/sm</code> - 订阅电影\n
<code>/sync</code> - 同步目录并创建软链\n
<code>/q</code> - 取消当前会话\n\n
<b>✨ 功能说明</b>\n
<u>电影下载：</u>
• 直接输入下载链接，支持磁力/ed2k/迅雷
• 离线超时可选择添加到重试列表
• 根据配置自动生成 <code>.strm</code> 软链文件\n
<u>重试列表：</u>
• 输入 <code>"/rl"</code>
• 查看当前重试列表，可根据需要选择是否清空\n
<u>AV下载：</u>
• 输入 <code>"/av 番号"</code>
• 支持批量下载，一行一个链接
• 支持接收txt文件下载，文件内容每行一个链接
• 自动检索磁力并离线,默认不生成软链（建议使用削刮工具生成软链）\n
<u>手动爬取涩花：</u>
• 输入 <code>"/csh"</code>
• 基于版块配置，爬取涩花昨日数据！\n
<u>手动爬取javbee：</u>
• 输入 <code>"/cjav yyyymmdd"</code>
• 日期格式为 <code>yyyymmdd</code>，例如：20250808
• 留空则默认爬取昨日数据\n
<u>RSS订阅：</u>
• 输入 <code>"/rss"</code>
• 将rsshub地址配置到config.yaml中
• 选择RSS类别并订阅\n
<u>电影订阅：</u>
• 输入 <code>"/sm 电影名称"</code>
• 自动监控资源更新, 发现更新后自动下载\n
<u>目录同步：</u>
• 输入 <code>"/sync"</code>
• 选择目录后会在对应的目录创建strm软链\n
<u>视频下载：</u>
• 直接转发视频给机器人，选择保存目录即可保存到115
"""
    return help_info


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_info = get_help_info()
    assert update.effective_chat is not None
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=help_info,
        parse_mode="html",
        disable_web_page_preview=True,
    )


async def reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    init.load_yaml_config()
    config = init.require_bot_config()
    init.logger.info("Reload configuration success:")
    init.logger.info(config.model_dump_json())
    assert update.effective_chat is not None
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="🔁重载配置完成！", parse_mode="html"
    )


def start_async_loop() -> None:
    """启动异步事件循环的线程"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    init.logger.info("事件循环已启动")
    try:
        token = init.require_bot_config().bot_token
        loop.create_task(queue_worker(loop, token))
        loop.run_forever()
    except Exception as e:
        init.logger.error(f"事件循环异常: {e}")
    finally:
        loop.close()
        init.logger.info("事件循环已关闭")


def send_start_message() -> None:
    version = get_version()
    if init.openapi_115 is None:
        return

    line1, line2, line3, line4 = init.openapi_115.welcome_message()
    if not line1:
        return
    line5 = escape_markdown(f"Telegram-115Bot {version} 启动成功！", version=2)
    if line1 and line2 and line3 and line4:
        formatted_message = f"""
{line1}
{line2}
{line3}
{line4}

{line5}

发送 `/start` 查看操作说明"""

        config = init.require_bot_config()
        add_task_to_queue(
            config.allowed_user,
            f"{init.IMAGE_PATH}/neuter010.png",
            message=formatted_message,
        )


def update_logger_level() -> None:
    import logging

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.Application").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.Updater").setLevel(logging.WARNING)
    logging.getLogger("telegram.Bot").setLevel(logging.WARNING)


def get_bot_menu() -> list[BotCommand]:
    return [
        BotCommand("start", "获取帮助信息"),
        BotCommand("auth", "115扫码授权"),
        BotCommand("reload", "重载配置"),
        BotCommand("rl", "查看重试列表"),
        BotCommand("av", "指定番号下载"),
        BotCommand("csh", "手动爬取涩花数据"),
        BotCommand("cjav", "手动爬取javbee数据"),
        BotCommand("rss", "RSS订阅"),
        BotCommand("sm", "订阅电影"),
        BotCommand("sync", "同步指定目录，并创建软链"),
        BotCommand("q", "退出当前会话"),
    ]


async def set_bot_menu(application: Application) -> None:
    """异步设置Bot菜单"""
    try:
        await application.bot.set_my_commands(get_bot_menu())
        init.logger.info("Bot菜单命令已设置!")
    except Exception as e:
        init.logger.error(f"设置Bot菜单失败: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """全局异常处理器，防止未捕获异常导致 polling 静默停止"""
    import traceback

    error_details = traceback.format_exc()
    init.logger.error(
        f"Unhandled exception in handler: {context.error}\n{error_details}"
    )
    # 尝试通知用户
    try:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ 处理请求时发生内部错误，请稍后重试。",
            )
    except Exception:
        pass


async def post_init(application: Application) -> None:
    """应用初始化后的回调"""
    await set_bot_menu(application)


async def polling_health_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    """检测 getUpdates 心跳，超时时尝试重建连接，多次重建失败后退出"""
    global _polling_health_failures, _polling_reconnect_attempts

    polling_request = context.application.bot_data.get("polling_request")
    if not isinstance(polling_request, PollingAwareHTTPXRequest):
        init.logger.warning(
            "Polling health check skipped: polling request monitor missing."
        )
        return

    polling_age = time.monotonic() - polling_request.last_poll_ok_at

    if polling_age <= _POLLING_STALE_THRESHOLD:
        if _polling_health_failures > 0:
            init.logger.info("Polling health check recovered.")
        _polling_health_failures = 0
        _polling_reconnect_attempts = 0
        return

    _polling_health_failures += 1
    init.logger.warning(
        f"Polling heartbeat stale ({_polling_health_failures}/{_POLLING_HEALTH_FAILURE_LIMIT}): "
        f"age={polling_age:.1f}s threshold={_POLLING_STALE_THRESHOLD:.1f}s"
    )

    if _polling_health_failures < _POLLING_HEALTH_FAILURE_LIMIT:
        return

    if _polling_reconnect_attempts < _MAX_RECONNECT_ATTEMPTS:
        _polling_reconnect_attempts += 1
        init.logger.warning(
            f"Attempting to reconnect polling ({_polling_reconnect_attempts}/{_MAX_RECONNECT_ATTEMPTS})..."
        )
        try:
            await polling_request.shutdown()
            await polling_request.initialize()
            polling_request.last_poll_ok_at = time.monotonic()
            _polling_health_failures = 0
            init.logger.info("Polling connection rebuilt successfully.")
            try:
                config = init.require_bot_config()
                await context.bot.send_message(
                    chat_id=config.allowed_user,
                    text="🔄 Telegram polling 连接已重建。",
                )
            except Exception:
                pass
            return
        except Exception as e:
            init.logger.error(f"Failed to reconnect polling: {e}")

    init.logger.error(
        f"Polling heartbeat stale {_POLLING_HEALTH_FAILURE_LIMIT} consecutive times "
        f"and {_MAX_RECONNECT_ATTEMPTS} reconnect attempts failed, exiting for Docker restart."
    )
    try:
        config = init.require_bot_config()
        await context.bot.send_message(
            chat_id=config.allowed_user,
            text=f"⚠️ Telegram polling 心跳连续 {_POLLING_HEALTH_FAILURE_LIMIT} 次超时且重建连接失败，进程即将退出。",
        )
    except Exception:
        pass

    await asyncio.sleep(1)
    os._exit(1)


def main() -> None:
    init.init()
    # 启动消息队列
    message_thread = threading.Thread(target=start_async_loop, daemon=True)
    message_thread.start()
    # 等待消息队列准备就绪
    import app.utils.message_queue as message_queue

    max_wait = 30  # 最多等待30秒
    wait_count = 0
    while True:
        if message_queue.global_loop is not None:
            init.logger.info("消息队列线程已准备就绪！")
            break
        time.sleep(1)
        wait_count += 1
        if wait_count >= max_wait:
            init.logger.error("消息队列线程未准备就绪，程序将退出。")
            exit(1)
    config = init.require_bot_config()
    init.logger.info("Starting bot with configuration:")
    init.logger.info(config.model_dump_json())
    # 调整telegram日志级别
    update_logger_level()

    token = config.bot_token
    # 常规 API 请求配置（sendMessage/sendPhoto 等）
    regular_request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=10.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=5.0,
    )
    # getUpdates 专用配置（禁用 keep-alive 防止半关闭连接）
    get_updates_request = PollingAwareHTTPXRequest(
        connection_pool_size=2,
        connect_timeout=10.0,
        read_timeout=60.0,
        write_timeout=30.0,
        pool_timeout=5.0,
        httpx_kwargs={
            "limits": httpx.Limits(
                max_connections=2,
                max_keepalive_connections=0,
            )
        },
    )
    application = (
        Application.builder()
        .token(token)
        .request(regular_request)
        .get_updates_request(get_updates_request)
        .post_init(post_init)
        .build()
    )
    # 存储 polling request 引用供健康检查使用
    application.bot_data["polling_request"] = get_updates_request
    # 注册全局异常处理器
    application.add_error_handler(error_handler)

    # 启动帮助
    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)
    # 重载配置
    reload_handler = CommandHandler("reload", reload)
    application.add_handler(reload_handler)

    # 初始化115open对象
    if not init.initialize_115open():
        init.logger.error("115 OpenAPI客户端初始化失败，程序无法继续运行！")
        add_task_to_queue(
            config.allowed_user,
            f"{init.IMAGE_PATH}/male023.png",
            message="❌ 115 OpenAPI客户端初始化失败，程序无法继续运行！\n请检查Token或115 AppID设置是否正确！",
        )
        # 等待消息队列处理完毕再退出
        while not message_queue.message_queue.empty():
            time.sleep(5)
        time.sleep(30)
        exit(1)

    # 注册Auth
    register_auth_handlers(application)
    # 注册下载
    register_download_handlers(application)
    # 注册电影订阅
    register_subscribe_movie_handlers(application)
    # 注册AV下载
    register_av_download_handlers(application)
    # 注册离线任务
    register_offline_task_handlers(application)
    # 注册Aria2
    register_aria2_handlers(application)
    # 手动爬虫
    register_crawl_handlers(application)
    # 注册RSS订阅
    register_rss_handlers(application)
    # 注册同步
    register_sync_handlers(application)
    # 注册视频
    register_video_handlers(application)

    # 注册 polling 健康检查任务
    if application.job_queue is not None:
        application.job_queue.run_repeating(
            polling_health_check,
            name="polling_health_check",
            interval=60,
            first=60,
            job_kwargs={"max_instances": 1, "coalesce": True},
        )
        init.logger.info("Polling health check registered (interval=60s)")
    else:
        init.logger.warning(
            "JobQueue unavailable, polling health check not registered."
        )

    init.logger.info(f"USER_AGENT: {init.USER_AGENT}")

    # 启动订阅线程（只启动一次）
    start_scheduler_in_thread()
    init.logger.info("订阅线程启动成功！")
    time.sleep(3)  # 等待订阅线程启动
    send_start_message()

    # Polling 重启配置
    max_polling_restarts = 5
    polling_restart_count = 0
    base_backoff = 5.0  # 初始退避秒数

    # 启动机器人轮询（带自动重启）
    while True:
        try:
            init.logger.info("Starting polling loop...")
            application.run_polling(
                poll_interval=0.5,
                timeout=30,
                drop_pending_updates=False,
            )
            # 正常退出（用户主动停止）
            break
        except KeyboardInterrupt:
            init.logger.info("程序已被用户终止（Ctrl+C）。")
            break
        except SystemExit:
            init.logger.info("程序正在退出。")
            break
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            polling_restart_count += 1
            backoff = min(base_backoff * (2 ** (polling_restart_count - 1)), 60.0)
            init.logger.warning(
                f"Polling exited due to network error ({polling_restart_count}/{max_polling_restarts}): {e}"
            )
            if polling_restart_count >= max_polling_restarts:
                init.logger.error(
                    f"Polling failed {max_polling_restarts} times, exiting for Docker restart."
                )
                break
            init.logger.info(f"Restarting polling in {backoff:.1f}s...")
            time.sleep(backoff)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            init.logger.error(f"Polling exited unexpectedly: {e}\n{error_details}")
            polling_restart_count += 1
            if polling_restart_count >= max_polling_restarts:
                init.logger.error(
                    f"Polling failed {max_polling_restarts} times with unexpected errors, exiting."
                )
                break
            backoff = min(base_backoff * (2 ** (polling_restart_count - 1)), 60.0)
            init.logger.info(f"Attempting restart in {backoff:.1f}s...")
            time.sleep(backoff)

    init.logger.info("机器人已停止运行。")


if __name__ == "__main__":
    main()
