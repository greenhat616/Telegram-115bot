# -*- coding: utf-8 -*-
from typing import cast

from telegram import Update, Chat, User, Message, CallbackQuery
from telegram.ext import ContextTypes


def require_chat(update: Update) -> Chat:
    chat = update.effective_chat
    if chat is None:
        raise RuntimeError("handler requires effective_chat")
    return chat


def require_user(update: Update) -> User:
    user = update.effective_user
    if user is None:
        raise RuntimeError("handler requires effective_user")
    return user


def require_message(update: Update) -> Message:
    message = update.message
    if message is None:
        raise RuntimeError("handler requires message")
    return message


def require_query(update: Update) -> CallbackQuery:
    query = update.callback_query
    if query is None:
        raise RuntimeError("handler requires callback_query")
    return query


def require_message_parts(update: Update) -> tuple[Message, Chat, User]:
    return require_message(update), require_chat(update), require_user(update)


def require_callback_parts(update: Update) -> tuple[CallbackQuery, Chat, User]:
    return require_query(update), require_chat(update), require_user(update)


def require_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, object]:
    data = context.user_data
    if data is None:
        raise RuntimeError("PTB user_data must be initialized")
    return data
