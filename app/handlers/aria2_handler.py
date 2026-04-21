from typing import Any
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from pathlib import Path
import asyncio
import time
import os
from app import init
from app.utils.ptb_helpers import (
    require_message,
    require_query,
    require_chat,
    require_user,
    require_user_data,
    safe_handler,
)
from concurrent.futures import ThreadPoolExecutor
from app.utils.aria2 import download_by_url, check_status_by_url
from app.utils.message_queue import add_task_to_queue
from telegram.helpers import escape_markdown

aria2_download_check_executor = ThreadPoolExecutor(
    max_workers=10, thread_name_prefix="Aria2_Download"
)


@safe_handler
async def push2aria2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = require_query(update)
    await query.answer()
    assert query.data is not None

    data = query.data
    if data.startswith("push2aria2_"):
        # 检查是否是新的ID格式
        task_id = data[len("push2aria2_") :]
        save_path = ""
        if task_id in init.pending_push_tasks:
            # 从全局存储中获取数据
            task_data = init.pending_push_tasks[task_id]
            save_path = task_data.path
            init.logger.info(f"推送任务ID: {task_id}, 文件路径: {save_path}")
            # 清理已使用的任务数据
            del init.pending_push_tasks[task_id]
        else:
            init.logger.warn("❌ 无效的任务ID或任务已过期。")
            await query.answer("❌ 无效的任务ID或任务已过期。", show_alert=True)
            return
        try:
            if not save_path:
                init.logger.warn("❌ 无效的文件路径，无法推送到Aria2。")
                await query.answer(
                    "❌ 无效的文件路径，无法推送到Aria2。", show_alert=True
                )
                return
            device_name = init.require_bot_config().aria2.device_name or "Aria2"
            download_path_base = init.require_bot_config().aria2.download_path
            # 移至线程池避免阻塞主事件循环
            all_pushed, last_part = await asyncio.to_thread(
                _do_aria2_push,
                save_path,
                download_path_base,
                device_name,
                require_chat(update).id,
            )

            try:
                # 尝试编辑消息，处理不同的消息类型
                if all_pushed:
                    # 首先尝试编辑caption（适用于图片消息）
                    await query.edit_message_caption(
                        caption=f"✅ [{last_part}]已推送至{device_name}！"
                    )
                else:
                    await query.edit_message_caption(
                        caption=f"❌ [{last_part}]推送到{device_name}失败，请检查配置或稍后再试。"
                    )
            except Exception:
                try:
                    # 如果编辑caption失败，尝试编辑文本（适用于纯文本消息）
                    if all_pushed:
                        await query.edit_message_text(
                            f"✅ [{last_part}]已推送至{device_name}！"
                        )
                    else:
                        await query.edit_message_text(
                            f"❌ [{last_part}]推送到{device_name}失败，请检查配置或稍后再试。"
                        )
                except Exception:
                    # 如果都失败，使用answer显示结果
                    if all_pushed:
                        await query.answer(
                            f"✅ [{last_part}]已推送至{device_name}！", show_alert=True
                        )
                    else:
                        await query.answer(
                            f"❌ [{last_part}]推送到{device_name}失败，请检查配置或稍后再试。",
                            show_alert=True,
                        )

        except Exception as e:
            init.logger.error(f"推送到{device_name}失败: {e}")
            try:
                await query.edit_message_caption(
                    caption=f"❌ [{last_part if 'last_part' in locals() else '文件'}]推送到{device_name}失败: {str(e)}"
                )
            except Exception:
                try:
                    await query.edit_message_text(
                        f"❌ [{last_part if 'last_part' in locals() else '文件'}]推送到{device_name}失败: {str(e)}"
                    )
                except Exception:
                    await query.answer(
                        f"❌ 推送到{device_name}失败: {str(e)}", show_alert=True
                    )


def _do_aria2_push(
    save_path: str, download_path_base: str, device_name: str, chat_id: int
) -> tuple[bool, str]:
    """在工作线程中执行 Aria2 推送（同步阻塞操作）"""
    download_urls = init.require_openapi_115().get_file_download_url(save_path)
    init.logger.info(f"[{save_path}]目录发现{len(download_urls)}个文件需要下载")

    path = Path(save_path)
    last_part = path.parts[-1] if path.parts[-1] else path.parts[-2]
    download_dir = os.path.join(download_path_base, last_part)
    init.logger.info(f"推送到Aria2，下载目录: {download_dir}")
    all_pushed = True
    for download_url in download_urls:
        download = download_by_url(download_url, download_dir)
        if not download:
            all_pushed = False
            init.logger.error(f"推送到Aria2失败，下载链接: {download_url}")
        else:
            aria2_download_check_executor.submit(
                check_download_complete, download_url, chat_id, device_name
            )
        time.sleep(1)
    return all_pushed, last_part


def check_download_complete(
    download_url: str, user_id: int, device_name: str, check_interval: int = 10
) -> None:
    """检查下载任务是否完成"""
    message = ""
    while True:
        download_status = check_status_by_url(download_url)
        if download_status["status"] == "not_found":
            message = f"❌ [{download_status['name']}] 没有找到下载链接！"
            break
        elif download_status["status"] == "error":
            message = f"❌ [{download_status['name']}] 下载失败！"
            break
        elif download_status["status"] == "complete":
            message = f"✅ [{download_status['name']}] 已下载到{device_name}！"
            break
        elif download_status["status"] == "paused":
            message = f"⏸️ [{download_status['name']}] 下载已暂停！"
            break
        else:
            init.logger.debug(
                f" [{download_status['name']}], 下载状态: {download_status['status']}, 进度: {download_status.get('progress', 'N/A')}, 速度: {download_status.get('speed', 'N/A')}"
            )
            time.sleep(check_interval)
    message = escape_markdown(message, version=2)
    add_task_to_queue(user_id, None, message)


def register_aria2_handlers(application: Any) -> None:
    aria2_handler = CallbackQueryHandler(push2aria2, pattern=r"^push2aria2_.+")
    application.add_handler(aria2_handler)
    init.logger.info("✅ Aria2处理器已注册")
