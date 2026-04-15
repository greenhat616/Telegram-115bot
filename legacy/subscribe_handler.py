# # -*- coding: utf-8 -*-

# import re
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
# import init
# from warnings import filterwarnings
# from telegram.warnings import PTBUserWarning
# import subscribe as sub2db
# from sqlitelib import *
# from telegram.helpers import escape_markdown

# filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

# SUBSCRIBE, SUBSCRIBE_OPERATE, ADD_SUBSCRIBE, VIEW_SUBSCRIBE, DEL_SUBSCRIBE = range(40, 45)


# async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     usr_id = update.message.from_user.id
#     if not init.check_user(usr_id):
#         await update.message.reply_text("⚠️ 对不起，您无权使用115机器人！")
#         return ConversationHandler.END

#     keyboard = [
#         [InlineKeyboardButton("添加订阅", callback_data="add_subscribe")],
#         [InlineKeyboardButton("浏览订阅", callback_data="view_subscribe")],
#         [InlineKeyboardButton("删除订阅", callback_data="del_subscribe")],
#         [InlineKeyboardButton("清空订阅", callback_data="clear_subscribe")],
#         [InlineKeyboardButton("退出", callback_data="quit")],
#     ]
#     reply_markup = InlineKeyboardMarkup(keyboard)
#     await context.bot.send_message(chat_id=update.effective_chat.id, text="❤️女优订阅：", reply_markup=reply_markup)
#     return SUBSCRIBE_OPERATE


# async def subscribe_operate(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     operate = query.data
#     if operate == "add_subscribe":
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="💡女优名称请与JavDb保持一致")
#         return ADD_SUBSCRIBE

#     if operate == "view_subscribe":
#         return await view_subscribe(update, context)

#     if operate == "del_subscribe":
#         actor_list = get_actors()
#         subscribe_text = ""
#         for item in actor_list:
#             markdown_v2 = escape_markdown(item[1], version=2)
#             subscribe_text += f"{item[0]}\\. {markdown_v2}\n"
#         subscribe_text = subscribe_text.strip()
#         init.logger.info(subscribe_text)
#         if not actor_list:
#             subscribe_text = "订阅列表为空。"
#         await context.bot.send_message(chat_id=update.effective_chat.id, text=subscribe_text, parse_mode="MarkdownV2")
#         if actor_list:
#             await context.bot.send_message(chat_id=update.effective_chat.id, text="💡 请输入要删除的ID")
#             return DEL_SUBSCRIBE

#     if operate == "clear_subscribe":
#         clear_subscribe()
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ 订阅列表已清空")
#         return SUBSCRIBE_OPERATE

#     if operate == "quit":
#         return await quit_conversation(update, context)

#     return SUBSCRIBE_OPERATE


# async def add_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     usr_id = update.message.from_user.id
#     actor_name = update.message.text
#     # 添加订阅女优
#     if add_subscribe_actor(actor_name, usr_id):
#         # 添加订阅到数据库
#         sub2db.add_subscribe2db(actor_name, usr_id)
#         await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ [{actor_name}]添加订阅成功！")
#         return SUBSCRIBE_OPERATE
#     else:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ [{actor_name}]已存在，请勿重复添加。")
#         return SUBSCRIBE_OPERATE


# async def view_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     actor_list = get_actors()
#     subscribe_text = ""
#     for item in actor_list:
#         markdown_v2 = escape_markdown(item[1], version=2)
#         subscribe_text += f"{item[0]}\\. {markdown_v2}\n"
#     subscribe_text = subscribe_text.strip()
#     init.logger.info(subscribe_text)
#     if not actor_list:
#         subscribe_text = "订阅列表为空。"
#     await context.bot.send_message(chat_id=update.effective_chat.id, text=subscribe_text, parse_mode="MarkdownV2")
#     return SUBSCRIBE_OPERATE


# async def del_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     try:
#         actor_id = int(update.message.text)
#         actor_name = get_actor_name(actor_id)
#         if actor_name:
#             del_subscribe_actor(actor_id)
#             # 删除订阅数据库
#             sub2db.del_sub_by_actor(actor_id, actor_name)
#             init.logger.info("[{actor_name}]删除订阅成功.")
#             await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ [{actor_name}]删除订阅成功！")
#             return SUBSCRIBE_OPERATE
#         else:
#             await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ 输入的ID有误，请检查！")
#             return DEL_SUBSCRIBE
#     except (ValueError, IndexError):
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ 请输入有效的数字ID！")
#         return DEL_SUBSCRIBE


# async def quit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     # 检查是否是回调查询
#     if update.callback_query:
#         await update.callback_query.edit_message_text(text="🚪用户退出本次会话")
#     else:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="🚪用户退出本次会话")
#     return ConversationHandler.END


# def add_subscribe_actor(actor_name, sub_user):
#     is_delete = check_and_restore_actor(actor_name)
#     if is_delete is not None:
#         if is_delete == 0:
#             init.logger.info(f"[{actor_name}]已存在，请勿重复添加.")
#             return False
#         else:
#             with SqlLiteLib() as sqlite:
#                 sql = f"update actor set is_delete=? where actor_name=?"
#                 params = (0, actor_name)
#                 sqlite.execute_sql(sql, params)
#             init.logger.info(f"[{actor_name}]已存在，已恢复订阅.")
#             return True
#     with SqlLiteLib() as sqlite:
#         sql = f'''INSERT INTO actor (actor_name, sub_user) VALUES (?,?)'''
#         params = (actor_name, sub_user)
#         sqlite.execute_sql(sql, params)
#         init.logger.info(f"[{actor_name}]添加订阅成功.")
#     return True


# def check_and_restore_actor(actor_name):
#     with SqlLiteLib() as sqlite:
#         sql = f"select is_delete from actor where actor_name=?"
#         params = (actor_name,)
#         result = sqlite.query_one(sql, params)
#         return result


# def get_actors():
#     actor_list = []
#     with SqlLiteLib() as sqlite:
#         sql = "select id,actor_name from actor where is_delete=?"
#         params = ("0",)
#         result = sqlite.query(sql, params)
#         for row in result:
#             item = [row[0], row[1]]
#             actor_list.append(item.copy())
#         return actor_list


# def get_actor_name(actor_id):
#     with SqlLiteLib() as sqlite:
#         sql = f"select actor_name from actor where id=?"
#         params = (actor_id,)
#         result = sqlite.query_one(sql, params)
#         if result:
#             return result
#         else:
#             return None


# def del_subscribe_actor(actor_id):
#     with SqlLiteLib() as sqlite:
#         sql = f"update actor set is_delete=? where id=?"
#         params = ("1", actor_id)
#         sqlite.execute_sql(sql, params)


# def clear_subscribe():
#     with SqlLiteLib() as sqlite:
#         sql = "update actor set is_delete=?"
#         params = ("1",)
#         sqlite.execute_sql(sql, params)
#         init.logger.info("All subscribe actors has been deleted.")
#     sub2db.del_all_subscribe()


# def register_subscribe_handlers(application):
#     sub_handler = ConversationHandler(
#         entry_points=[CommandHandler("sub", subscribe)],
#         states={
#             SUBSCRIBE_OPERATE: [CallbackQueryHandler(subscribe_operate)],
#             ADD_SUBSCRIBE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_subscribe)],
#             VIEW_SUBSCRIBE: [CallbackQueryHandler(view_subscribe)],
#             DEL_SUBSCRIBE: [MessageHandler(filters.TEXT & ~filters.COMMAND, del_subscribe)],
#         },
#         fallbacks=[CommandHandler("q", quit_conversation)],
#     )
#     application.add_handler(sub_handler)
