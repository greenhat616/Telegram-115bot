# -*- coding: utf-8 -*-

from typing import Any
from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, ContextTypes
from app import init
from app.utils.ptb_helpers import (
    require_message,
    require_query,
    require_chat,
    require_user,
    require_user_data,
    safe_handler,
)
import os


# 定义对话的步骤
# ASK_COOKIE, RECEIVE_COOKIE = range(0, 2)


@safe_handler
async def auth_pkce_115(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import asyncio

    usr_id = require_user(update).id
    if init.check_user(usr_id):
        if check_115_app_id():
            if os.path.exists(init.TOKEN_FILE):
                os.remove(init.TOKEN_FILE)
            await require_message(update).reply_text("⏳ 正在发起授权，请稍候...")
            await asyncio.to_thread(
                init.require_openapi_115().auth_pkce,
                usr_id,
                init.require_bot_config().app_115_id,
            )
            if (
                init.require_openapi_115().access_token
                and init.require_openapi_115().refresh_token
            ):
                await require_message(update).reply_text("✅ 授权成功！")
            else:
                await require_message(update).reply_text(
                    "⚠️ 授权失败，请检查配置文件中的app_id是否正确！"
                )
        else:
            await require_message(update).reply_text("⚠️ 115开放平台APPID未配置！")
    else:
        await require_message(update).reply_text(f"⚠️ 对不起，您无权使用115机器人！")
    # 结束对话
    return ConversationHandler.END


def check_115_app_id() -> bool:
    api_key = str(init.require_bot_config().app_115_id)
    if (
        api_key is None
        or api_key.strip() == ""
        or api_key.strip().lower() == "your_115_app_id"
    ):
        init.logger.error("115 Open APPID未配置!")
        return False
    return True


@safe_handler
async def quit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 检查是否是回调查询
    if update.callback_query:
        await update.callback_query.edit_message_text(text="🚪用户退出本次会话")
    else:
        await context.bot.send_message(
            chat_id=require_chat(update).id, text="🚪用户退出本次会话"
        )
    return ConversationHandler.END


def register_auth_handlers(application: Any) -> None:
    auth_handler = ConversationHandler(
        entry_points=[CommandHandler("auth", auth_pkce_115)],  # ty:ignore[invalid-argument-type]
        states={},  # 添加空的states字典
        fallbacks=[CommandHandler("q", quit_conversation)],  # ty:ignore[invalid-argument-type]
        conversation_timeout=600,
    )
    application.add_handler(auth_handler)
    init.logger.info("✅ Auth处理器已注册")
