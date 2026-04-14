# -*- coding: utf-8 -*-
from app.models.base import AppModel


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
