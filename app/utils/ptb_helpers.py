# -*- coding: utf-8 -*-
import traceback
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from telegram import Document, Update, Chat, User, Message, CallbackQuery
from telegram.ext import ContextTypes, ConversationHandler

from app import init
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


def require_subscribe_movie_data(
    context: ContextTypes.DEFAULT_TYPE,
) -> SubscribeMovieUserData:
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


# ── Handler exception wrapper ────────────────────────────────────

T = TypeVar("T")
HandlerFunc = Callable[[Update, ContextTypes.DEFAULT_TYPE], Any]


def _extract_handler_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Extract context info from update for logging."""
    parts: list[str] = []

    # User info
    user = update.effective_user
    if user:
        parts.append(f"user={user.id}(@{user.username or 'N/A'})")

    # Chat info
    chat = update.effective_chat
    if chat:
        parts.append(f"chat={chat.id}(type={chat.type})")

    # Command/message info
    if update.message:
        if update.message.text:
            text = update.message.text
            if len(text) > 100:
                text = text[:100] + "..."
            parts.append(f"text={text!r}")
        if update.message.document:
            parts.append(f"document={update.message.document.file_name}")
    elif update.callback_query:
        parts.append(f"callback_data={update.callback_query.data!r}")

    # Command args from context
    if context.args:
        parts.append(f"args={context.args}")

    return " | ".join(parts)


def handler_error_boundary(
    handler_name: str | None = None,
    notify_user: bool = True,
    end_conversation: bool = True,
) -> Callable[[HandlerFunc], HandlerFunc]:
    """
    Decorator to wrap PTB handlers with unified exception handling.

    - Logs full context (user, chat, command, args) on error
    - Optionally notifies user of the error
    - Prevents exceptions from bubbling to the framework
    - Returns ConversationHandler.END if end_conversation=True
    """

    def decorator(func: HandlerFunc) -> HandlerFunc:
        name = handler_name or func.__name__

        @wraps(func)
        async def wrapper(
            update: Update, context: ContextTypes.DEFAULT_TYPE
        ) -> Any:
            try:
                return await func(update, context)
            except Exception as e:
                error_tb = traceback.format_exc()
                handler_ctx = _extract_handler_context(update, context)
                init.logger.error(
                    f"Handler [{name}] exception: {e}\n"
                    f"Context: {handler_ctx}\n"
                    f"Traceback:\n{error_tb}"
                )

                if notify_user:
                    try:
                        chat = update.effective_chat
                        if chat:
                            await context.bot.send_message(
                                chat_id=chat.id,
                                text=f"⚠️ 处理命令时发生错误，请稍后重试。\n错误: {type(e).__name__}",
                            )
                    except Exception:
                        pass

                if end_conversation:
                    return ConversationHandler.END
                return None

        return wrapper

    return decorator


def safe_handler(func: HandlerFunc) -> HandlerFunc:
    """Shorthand for @handler_error_boundary() with default settings."""
    return handler_error_boundary()(func)
