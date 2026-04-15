# -*- coding: utf-8 -*-
from typing import Any

import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from app import init
from app.utils.ptb_helpers import require_message, require_query, require_chat, require_user, require_user_data, require_text, require_subscribe_movie_data
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning
from app.core.subscribe_movie import get_tmdb_id
from app.utils.sqlitelib import SqlLiteLib
from telegram.helpers import escape_markdown


filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

SUBSCRIBE, SUBSCRIBE_OPERATE, ADD_SUBSCRIBE, VIEW_SUBSCRIBE, DEL_SUBSCRIBE, SELECT_MAIN_CATEGORY, SELECT_SUB_CATEGORY = range(50, 57)




async def subscribe_moive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    usr_id = require_user(update).id
    if not init.check_user(usr_id):
        await require_message(update).reply_text("⚠️ 对不起，您无权使用115机器人！")
        return ConversationHandler.END
    config = init.require_bot_config()
    if config.x_app_id == "your_app_id" or config.x_app_id == "" or config.x_app_id is None \
        or config.x_api_key == "your_api_key" or config.x_api_key == "" or config.x_api_key is None:
        await require_message(update).reply_text("⚠️ 请先取得nullbrAPI接口的授权才能使用电影订阅功能！\n申请方法见配置文件。")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("添加订阅", callback_data="add_subscribe")],
        [InlineKeyboardButton("浏览订阅", callback_data="view_subscribe")],
        [InlineKeyboardButton("删除订阅", callback_data="del_subscribe")],
        [InlineKeyboardButton("清空订阅", callback_data="clear_subscribe")],
        [InlineKeyboardButton("退出", callback_data="quit")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=require_chat(update).id, text="🍿电影订阅：", reply_markup=reply_markup)
    return SUBSCRIBE_OPERATE


async def select_main_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = require_query(update)
    await query.answer()
    assert query.data is not None

    selected_main_category = query.data
    if selected_main_category == "cancel":
        return await quit_conversation(update, context)
    else:
        require_user_data(context)["selected_main_category"] = selected_main_category
        sub_categories = [
            item.path_map for item in init.require_bot_config().category_folder if item.name == selected_main_category
        ][0]

        # 创建子分类按钮
        keyboard = [
            [InlineKeyboardButton(f"📁 {category.name}", callback_data=category.path)] for category in sub_categories
        ]
        keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text("❓请选择分类保存目录：", reply_markup=reply_markup)

        return SELECT_SUB_CATEGORY


async def select_sub_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = require_query(update)
    await query.answer()

    # 获取用户选择的路径
    selected_path = query.data
    if selected_path == "cancel":
        return await quit_conversation(update, context)
    require_user_data(context)["selected_path"] = selected_path
    await query.edit_message_text(text=f"✅ 已选择保存目录：{selected_path}")
    
    # 获取之前保存的电影名称和用户ID
    movie_name = require_user_data(context)["movie_name"]
    sub_user = require_user_data(context)["sub_user"]
    tmbd_id = require_user_data(context)["tmdb_id"]
    
    # 添加订阅
    success, message = add_subscribe_movie(movie_name, tmbd_id, sub_user, selected_path)
    
    if success:
        await query.edit_message_text(f"✅ {message}")
    else:
        await query.edit_message_text(f"❌ {message}")
    return ConversationHandler.END



async def subscribe_operate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = require_query(update)
    await query.answer()
    assert query.data is not None
    operate = query.data
    if operate == "add_subscribe":
        await context.bot.send_message(chat_id=require_chat(update).id, text="💡请输入电影名称，电影名称请保持与TMDB一致！")
        return ADD_SUBSCRIBE
    
    if operate == "view_subscribe":
        return await view_subscribe(update, context)
    
    if operate == "del_subscribe":
        movie_list = get_subscribe_movie()
        subscribe_text = "点击TMDB\\_ID自动复制 \n"
        for item in movie_list:
            markdown_v2 = escape_markdown(item[1], version=2)
            subscribe_text += f"`{item[0]}`\\. {markdown_v2}\n"
        subscribe_text = subscribe_text.strip()
        if not movie_list:
            subscribe_text = "订阅列表为空。"
        await context.bot.send_message(chat_id=require_chat(update).id, text=subscribe_text, parse_mode="MarkdownV2")
        if movie_list:
            await context.bot.send_message(chat_id=require_chat(update).id, text="💡请输入要删除的ID")
            return DEL_SUBSCRIBE
        
    if operate == "clear_subscribe":
        clear_subscribe()
        await context.bot.send_message(chat_id=require_chat(update).id, text="✅ 订阅列表已清空！")
        return SUBSCRIBE_OPERATE
    
    if operate == "quit":
       return await quit_conversation(update, context)
    
    return SUBSCRIBE_OPERATE


async def add_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usr_id = require_user(update).id
    movie_name = require_text(update)
    # 先检查电影是否存在于TMDB（移至线程池避免阻塞主事件循环）
    tmdb_id = await asyncio.to_thread(get_tmdb_id, movie_name)
    if tmdb_id is None:
        await context.bot.send_message(
            chat_id=require_chat(update).id, 
            text=f"❌ 无法找到电影[{movie_name}]的TMDB信息, 请确认电影名称是否正确！"
        )
        return SUBSCRIBE_OPERATE
    
    # 保存电影名称到用户数据中，以便后续使用
    require_user_data(context)["movie_name"] = movie_name
    require_user_data(context)["sub_user"] = usr_id
    require_user_data(context)["tmdb_id"] = tmdb_id
    
    # 显示主分类（电影分类）
    keyboard = [
        [InlineKeyboardButton(f"📁 {category.display_name}", callback_data=category.name)]
        for category in init.require_bot_config().category_folder
    ]
    keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 发送新消息而不是编辑消息，因为这是普通消息触发的函数
    await context.bot.send_message(
        chat_id=require_chat(update).id, 
        text="❓请选择要保存到哪个分类：",
        reply_markup=reply_markup
    )
    return SELECT_MAIN_CATEGORY


async def view_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movie_list = get_subscribe_movie()
    subscribe_text = "点击TMDB\\_ID自动复制 \n"
    for item in movie_list:
        markdown_v2 = escape_markdown(item[1], version=2)
        subscribe_text += f"`{item[0]}`\\. {markdown_v2}\n"
    subscribe_text = subscribe_text.strip()
    init.logger.info(subscribe_text)
    if not movie_list:
        subscribe_text = "订阅列表为空。"   
    await context.bot.send_message(chat_id=require_chat(update).id, text=subscribe_text, parse_mode="MarkdownV2")
    return SUBSCRIBE_OPERATE


async def del_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tmdb_id = int(require_text(update))
        success, movie_name = check_tmdb_id(tmdb_id)
        if success:
            del_subscribe_movie(tmdb_id)
            init.logger.info("[{actor_name}]删除订阅成功.")
            await context.bot.send_message(chat_id=require_chat(update).id, text=f"✅ [{movie_name}]删除订阅成功！")
            return SUBSCRIBE_OPERATE
        else:
            await context.bot.send_message(chat_id=require_chat(update).id, text="❌ 输入的TMDB ID有误，请检查！")
            return DEL_SUBSCRIBE
    except (ValueError, IndexError):
        await context.bot.send_message(chat_id=require_chat(update).id, text="❌ 输入的TMDB ID有误，请检查！")
        return DEL_SUBSCRIBE


async def quit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 检查是否是回调查询
    if update.callback_query:
        await update.callback_query.edit_message_text(text="🚪用户退出本次会话")
    else:
        await context.bot.send_message(chat_id=require_chat(update).id, text="🚪用户退出本次会话")
    return ConversationHandler.END


def add_subscribe_movie(movie_name, tmdb_id, sub_user, category_folder):
    message = ""
    is_delete, is_download = get_is_delete_or_download(tmdb_id)
    # 判断是否下载过
    if is_download is not None:
        if int(is_download) == 1:
            message = f"[{movie_name}]订阅已下载，请勿重复添加."
            init.logger.info(message)
            return False, message
    save_path = get_category_folder(tmdb_id)
    if is_delete is not None:
        if int(is_delete) == 0:
            if save_path == category_folder:
                message = f"[{movie_name}]已存在，请勿重复添加."
            else:
                # 更新保存路径
                update_sub_movie_category_folder(tmdb_id, category_folder)
                message = f"[{movie_name}]更新保存路径[{save_path}]->[{category_folder}]."
            init.logger.info(message)
            return False, message
        else:
            with SqlLiteLib() as sqlite:
                sql = f"update sub_movie set is_delete=0, category_folder=? where tmdb_id=?"
                params = (category_folder, tmdb_id)
                sqlite.execute_sql(sql, params)
            message = f"[{movie_name}]已存在，已恢复订阅."
            init.logger.info(message)
            return True, message
    with SqlLiteLib() as sqlite:
        sql = f'''INSERT INTO sub_movie (movie_name, tmdb_id, sub_user, category_folder) VALUES (?,?,?,?)'''
        params = (movie_name, tmdb_id, sub_user, category_folder)
        sqlite.execute_sql(sql, params)
        message = f"[{movie_name}]添加订阅成功，将保存到 {category_folder}"
        init.logger.info(message)
    return True, message


def get_is_delete_or_download(tmdb_id):
    with SqlLiteLib() as sqlite:
        sql = "select is_delete, is_download from sub_movie where tmdb_id=?"
        params = (tmdb_id,)
        result = sqlite.query_row(sql, params)
        if result is not None:
            is_delete, is_download = result
            return is_delete, is_download
        else:
            return None, None      
    
def get_category_folder(tmdb_id):
    with SqlLiteLib() as sqlite:
        sql = f"select category_folder from sub_movie where tmdb_id=?"
        params = (tmdb_id,)
        result = sqlite.query_one(sql, params)
        return result
    
def check_tmdb_id(tmdb_id):
    with SqlLiteLib() as sqlite:
        sql = f"select movie_name from sub_movie where is_delete=0 and tmdb_id=?"
        params = (tmdb_id,)
        result = sqlite.query_one(sql, params)
        if result:
            return True, result
        else:
            return False, None
        
def update_sub_movie_category_folder(tmdb_id, category_folder):
    with SqlLiteLib() as sqlite:
        sql = f"update sub_movie set category_folder=? where is_delete=0 and tmdb_id=?"
        params = (category_folder, tmdb_id)
        sqlite.execute_sql(sql, params)


def del_subscribe_movie(tmdb_id):
    with SqlLiteLib() as sqlite:
        sql = f"update sub_movie set is_delete=? where tmdb_id=?"
        params = ("1", tmdb_id)
        sqlite.execute_sql(sql, params)


def clear_subscribe():
    with SqlLiteLib() as sqlite:
        sql = "update sub_movie set is_delete=?"
        params = ("1",)
        sqlite.execute_sql(sql, params)
        init.logger.info("All subscribe movies has been deleted.")
    
def get_subscribe_movie():
    movie_list = []
    with SqlLiteLib() as sqlite:
        sql = "select tmdb_id, movie_name from sub_movie where is_delete=? and is_download=?"
        params = ("0", "0")
        result = sqlite.query(sql, params)
        for row in result:
            item = [row[0], row[1]]
            movie_list.append(item.copy())
        return movie_list


def register_subscribe_movie_handlers(application: Any) -> None:
    sub_movie_handler = ConversationHandler(
        entry_points=[CommandHandler("sm", subscribe_moive)],  # ty:ignore[invalid-argument-type]
        states={
            SUBSCRIBE_OPERATE: [CallbackQueryHandler(subscribe_operate)],
            # ADD_SUBSCRIBE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_subscribe)],
            ADD_SUBSCRIBE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^(magnet:|ed2k://|ED2K://|thunder://)'), add_subscribe)],
            VIEW_SUBSCRIBE: [CallbackQueryHandler(view_subscribe)],
            # DEL_SUBSCRIBE: [MessageHandler(filters.TEXT & ~filters.COMMAND, del_subscribe)],
            DEL_SUBSCRIBE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^(magnet:|ed2k://|ED2K://|thunder://)'), del_subscribe)],
            SELECT_MAIN_CATEGORY: [CallbackQueryHandler(select_main_category)],
            SELECT_SUB_CATEGORY: [CallbackQueryHandler(select_sub_category)]
        },  # ty:ignore[invalid-argument-type]
        fallbacks=[CommandHandler("q", quit_conversation)],  # ty:ignore[invalid-argument-type]
        conversation_timeout=300,
    )
    application.add_handler(sub_movie_handler)
    init.logger.info("✅ Subscribe Movie处理器已注册")
