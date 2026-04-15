# -*- coding: utf-8 -*-
from typing import cast

from telegram import Document, Update, Chat, User, Message, CallbackQuery
from telegram.ext import ContextTypes

from app.models.context import (
    AvDownloadUserData,
    CrawlUserData,
    DownloadUserData,
    RssUserData,
    SubscribeMovieUserData,
    SyncUserData,
    VideoUserData,
)


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


# ── Per-handler typed data wrappers ──────────────────────────────


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


# ── PTB Optional narrowing helpers ───────────────────────────────


def require_text(update: Update) -> str:
    text = require_message(update).text
    if text is None:
        raise RuntimeError("handler requires message.text")
    return text


def require_document(update: Update) -> Document:
    doc = require_message(update).document
    if doc is None:
        raise RuntimeError("handler requires message.document")
    return doc


def require_query_data(update: Update) -> str:
    data = require_query(update).data
    if data is None:
        raise RuntimeError("handler requires callback_query.data")
    return data
