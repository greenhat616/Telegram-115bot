# -*- coding: utf-8 -*-
from typing import TypedDict

from app.models.enums import DownloadUrlType


class DownloadUserData(TypedDict, total=False):
    link: str
    dl_url_type: DownloadUrlType
    selected_main_category: str
    selected_path: str


class AvDownloadUserData(TypedDict, total=False):
    link: str
    dl_url_type: DownloadUrlType
    av_number: str
    dl_links: str
    selected_main_category: str
    selected_path: str


class SubscribeMovieUserData(TypedDict, total=False):
    movie_name: str
    tmdb_id: int
    sub_user: int
    selected_main_category: str
    selected_path: str


class RssUserData(TypedDict, total=False):
    rss_main_category: str
    rss_sub_category: str
    selected_category: dict
    selected_main_category: str
    selected_path: str


class VideoUserData(TypedDict, total=False):
    last_video_save_path: str
    video_rename_task_id: str


class CrawlUserData(TypedDict, total=False):
    date: str


class SyncUserData(TypedDict, total=False):
    selected_main_category: str


class RenameData(TypedDict):
    user_id: int
    action: str
    final_path: str
    resource_name: str
    selected_path: str
    link: str
    add2retry: bool
