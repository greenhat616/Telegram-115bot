# -*- coding: utf-8 -*-

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from app import init
from typing import Any, cast
from app.utils.ptb_helpers import (
    require_message,
    require_query,
    require_chat,
    require_user,
    require_user_data,
    require_text,
    require_query_data,
    safe_handler,
)
import os
import uuid
from datetime import datetime
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning
from app.core.video_downloader import video_manager

filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)
# 过滤 Telethon 的异步会话实验性功能警告
filterwarnings(
    action="ignore", message="Using async sessions support is an experimental feature"
)


@safe_handler
async def save_video2115(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usr_id = require_user(update).id
    if not init.check_user(usr_id):
        await require_message(update).reply_text("⚠️ 对不起，您无权使用115机器人！")
        return

    if not init.tg_user_client:
        message = "⚠️ Telegram 用户客户端初始化失败，配置方法请参考\nhttps://github.com/qiqiandfei/Telegram-115bot/wiki/VideoDownload"
        await require_message(update).reply_text(message)
        return

    # 检查和建立 Telegram 用户客户端连接
    try:
        if not init.tg_user_client.is_connected():
            init.logger.info("🔄 正在验证 Telegram 用户客户端连接...")
            await init.tg_user_client.connect()

        if not await init.tg_user_client.is_user_authorized():
            await require_message(update).reply_text("❌ Telegram 用户客户端未授权！")
            return

    except Exception as e:
        init.logger.error(f"Telegram 用户客户端连接失败: {e}")
        await require_message(update).reply_text(f"❌ 连接失败: {str(e)}")
        return

    if update.message and require_message(update).video:
        video = require_message(update).video
        assert video is not None
        file_name = video.file_name or f"{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"

        # 获取扩展名
        _, file_ext = os.path.splitext(file_name)
        if not file_ext:
            file_ext = ".mp4"

        # 生成唯一任务ID
        task_id = str(uuid.uuid4())[:8]

        # 暂存视频信息到 context.user_data，使用 task_id 作为 key
        require_user_data(context)[f"video_{task_id}"] = {
            "file_name": file_name,
            "file_ext": file_ext,
            "file_size": video.file_size,
            "message_id": update.message.message_id,
            "chat_id": require_chat(update).id,
        }

        # 询问是否重命名
        keyboard = [
            [
                InlineKeyboardButton(
                    "使用默认名称", callback_data=f"video_rename_default_{task_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "自定义名称", callback_data=f"video_rename_custom_{task_id}"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=require_chat(update).id,
            text=f"📹 收到视频: {file_name}\n❓是否需要重命名？",
            reply_markup=reply_markup,
            reply_to_message_id=update.message.message_id,
        )


def _get_video_info(
    context: ContextTypes.DEFAULT_TYPE, task_id: str
) -> dict[str, Any] | None:
    raw = require_user_data(context).get(f"video_{task_id}")
    return cast(dict[str, Any], raw) if raw else None


@safe_handler
async def show_directory_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    task_id: str,
    edit_message: bool = False,
) -> None:
    """显示目录选择界面"""
    video_info = _get_video_info(context, task_id)
    if not video_info:
        if edit_message and update.callback_query:
            await update.callback_query.edit_message_text("❌ 任务已过期")
        else:
            await context.bot.send_message(
                chat_id=require_chat(update).id, text="❌ 任务已过期"
            )
        return

    file_name = video_info["file_name"]

    # 显示主分类
    keyboard = []

    # 添加上次保存路径按钮
    last_path = require_user_data(context).get("last_video_save_path")
    if last_path:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🚀 上次保存: {last_path}", callback_data=f"quick_last_{task_id}"
                )
            ]
        )

    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    f"📁 {category.display_name}",
                    callback_data=f"main_{category.name}_{task_id}",
                )
            ]
            for category in init.require_bot_config().category_folder
        ]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"📹 视频文件: {file_name}\n❓请选择要保存到哪个分类："

    if edit_message and update.callback_query:
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=require_chat(update).id,
            text=text,
            reply_markup=reply_markup,
            reply_to_message_id=require_message(update).message_id,
        )


@safe_handler
async def handle_rename_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """处理重命名输入"""
    task_id = require_user_data(context).get("video_rename_task_id")
    if not task_id:
        return

    new_name = require_text(update).strip()

    video_info = _get_video_info(context, str(task_id))
    if video_info:
        # 如果新名字没有扩展名，且我们有原扩展名
        if not os.path.splitext(new_name)[1]:
            file_ext = video_info.get("file_ext", ".mp4")
            new_name += file_ext

        video_info["file_name"] = new_name
        # 清除等待状态
        del require_user_data(context)["video_rename_task_id"]

        # 显示目录选择
        await show_directory_selection(update, context, str(task_id))


@safe_handler
async def handle_category_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = require_query(update)
    try:
        await query.answer()
    except Exception as e:
        # 忽略 "Query is too old" 错误，这通常发生在点击很久之前的按钮时
        init.logger.debug(f"Callback query answer failed: {e}")

    data = require_query_data(update)
    parts = data.split("_")
    action = parts[0]

    if action == "video" and len(parts) > 1 and parts[1] == "rename":
        # 处理重命名选择: video_rename_default_taskId 或 video_rename_custom_taskId
        # parts: ['video', 'rename', 'sub_action', 'task_id']
        if len(parts) < 4:
            return

        sub_action = parts[2]
        task_id = parts[3]

        if sub_action == "default":
            # 使用默认名称，直接显示目录选择
            await show_directory_selection(update, context, task_id, edit_message=True)

        elif sub_action == "custom":
            # 自定义名称，提示输入
            require_user_data(context)["video_rename_task_id"] = task_id
            await query.edit_message_text("⌨️ 请输入新的文件名（无需后缀）：")

    elif action == "main":
        # 选择主分类: main_categoryName_taskId
        category_name = parts[1]
        task_id = parts[2]

        sub_categories = [
            item.path_map
            for item in init.require_bot_config().category_folder
            if item.name == category_name
        ][0]

        keyboard = [
            [
                InlineKeyboardButton(
                    f"📁 {category.name}",
                    callback_data=f"sub_{category.path}_{task_id}",
                )
            ]
            for category in sub_categories
        ]
        keyboard.append([InlineKeyboardButton("返回", callback_data=f"back_{task_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❓请选择子分类：", reply_markup=reply_markup)

    elif action == "sub" or action == "quick":
        # 选择子分类: sub_path_taskId 或 quick_last_taskId
        save_path: str = ""
        task_id: str = ""

        if action == "sub":
            task_id = parts[-1]
            save_path = "_".join(parts[1:-1])
            # 记录本次保存路径
            require_user_data(context)["last_video_save_path"] = save_path
        elif action == "quick":
            task_id = parts[2]
            save_path = str(require_user_data(context).get("last_video_save_path", ""))
            if not save_path:
                await query.answer("上次保存路径已失效，请重新选择", show_alert=True)
                return

        video_info = _get_video_info(context, task_id)
        if not video_info:
            await query.edit_message_text("❌ 任务信息已过期")
            return

        # 获取原始消息对象
        try:
            # 确定 entity
            entity = None
            # 如果是私聊（chat_id == user_id），User Client 需要去获取和 Bot 的聊天记录
            if video_info["chat_id"] == require_user(update).id:
                # 动态获取 Bot 用户名，无需依赖配置文件
                try:
                    bot_info = await context.bot.get_me()
                    entity = f"@{bot_info.username}"
                except Exception as e:
                    init.logger.error(f"获取Bot信息失败: {e}")
                    # 回退到配置文件
                    entity = init.require_bot_config().bot_name
            else:
                # 群组情况，直接用 chat_id
                entity = video_info["chat_id"]

            if not entity:
                await query.edit_message_text("❌ 无法确定消息来源 (Entity unknown)")
                return

            # 尝试获取消息
            target_msg = None

            # 方法1: 精确 ID 获取 (Telethon get_messages with ids)
            try:
                assert init.tg_user_client is not None
                msg = await init.tg_user_client.get_messages(
                    entity, ids=video_info["message_id"]
                )
                if msg and msg.media:
                    target_msg = msg
            except Exception as e:
                init.logger.warning(f"精确获取消息失败: {e}")

            # 方法2: 遍历最近消息 (Fallback，兼容旧逻辑)
            if not target_msg:
                init.logger.info(
                    f"精确获取失败，尝试遍历最近消息 (ID: {video_info['message_id']})"
                )
                try:
                    # 获取最近 20 条消息
                    assert init.tg_user_client is not None
                    recent_msgs = await init.tg_user_client.get_messages(
                        entity, limit=20
                    )

                    # 2.1 优先寻找 ID 匹配的消息
                    for msg in recent_msgs:
                        if msg.id == video_info["message_id"] and msg.media:
                            target_msg = msg
                            break

                    # 2.2 如果没找到 ID，寻找最近的一条带视频的消息 (用户提到的"原来的写法")
                    if not target_msg:
                        for msg in recent_msgs:
                            if msg.media:
                                # 简单的校验：如果是视频/文件
                                target_msg = msg
                                init.logger.info(
                                    f"使用最近的媒体消息作为目标 (ID: {msg.id})"
                                )
                                break
                except Exception as e:
                    init.logger.error(f"遍历消息失败: {e}")

            if not target_msg:
                await query.edit_message_text(
                    f"❌ 无法获取原始视频消息 (Entity: {entity}, ID: {video_info['message_id']})"
                )
                return

            # 提交任务到管理器
            task_info = {
                "task_id": task_id,
                "file_name": video_info["file_name"],
                "file_size": video_info["file_size"],
                "save_path": save_path,
                "message": target_msg,
                "context": context,
                "chat_id": require_chat(update).id,
                "message_id": query.message.message_id if query.message else 0,
            }

            await video_manager.add_task(task_info)

            # 清理 user_data
            del require_user_data(context)[f"video_{task_id}"]

        except Exception as e:
            init.logger.error(f"提交任务失败: {e}")
            await query.edit_message_text(f"❌ 提交任务失败: {e}")

    elif action == "back":
        task_id = parts[1]
        keyboard = []

        # 添加上次保存路径按钮
        last_path = require_user_data(context).get("last_video_save_path")
        if last_path:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🚀 上次保存: {last_path}",
                        callback_data=f"quick_last_{task_id}",
                    )
                ]
            )

        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        f"📁 {category.display_name}",
                        callback_data=f"main_{category.name}_{task_id}",
                    )
                ]
                for category in init.require_bot_config().category_folder
            ]
        )
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❓请选择要保存到哪个分类：", reply_markup=reply_markup
        )

    elif action == "v" and parts[1] == "cancel":
        # 取消下载: v_cancel_taskId
        task_id = parts[2]
        success = await video_manager.cancel_task(task_id)
        if success:
            await query.edit_message_text("🛑 正在取消任务...")
        else:
            await query.answer("任务无法取消或已完成", show_alert=True)

    elif action == "cancel":
        # 保留旧逻辑以防万一，或者直接移除
        if len(parts) > 2 and parts[1] == "dl":
            task_id = parts[2]
            success = await video_manager.cancel_task(task_id)
            if success:
                await query.edit_message_text("🛑 正在取消任务...")


def register_video_handlers(application: Any) -> None:
    # 注册视频消息处理器
    application.add_handler(MessageHandler(filters.VIDEO, save_video2115))

    # 注册重命名输入处理器 (只处理文本，且非命令)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rename_input)
    )

    # 注册回调处理器
    # 添加 v_ 前缀支持，添加 rename 前缀支持
    application.add_handler(
        CallbackQueryHandler(
            handle_category_selection,
            pattern="^(main|sub|back|cancel|quick|v|video_rename)_",
        )
    )

    init.logger.info("✅ Video处理器已注册")
