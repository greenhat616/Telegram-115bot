# -*- coding: utf-8 -*-
from datetime import date, datetime

from app.models.base import AppModel
from app.models.enums import DownloadFlag, DeleteFlag


class OfflineTaskRow(AppModel):
    id: int
    title: str
    save_path: str
    magnet: str
    is_download: DownloadFlag = DownloadFlag.NO
    retry_count: int = 1
    completed_at: datetime | None = None
    created_at: datetime


class OfflineTaskCreate(AppModel):
    title: str
    save_path: str
    magnet: str


class AvDailyUpdateRow(AppModel):
    id: int
    av_number: str
    publish_date: date
    title: str
    post_url: str
    pub_url: str
    magnet: str
    is_download: DownloadFlag = DownloadFlag.NO
    created_at: datetime


class AvDailyUpdateCreate(AppModel):
    av_number: str
    publish_date: date
    title: str
    post_url: str
    pub_url: str
    magnet: str


class SubMovieRow(AppModel):
    id: int
    movie_name: str
    tmdb_id: int
    size: str | None = None
    category_folder: str
    is_download: DownloadFlag = DownloadFlag.NO
    download_url: str | None = None
    sub_user: int
    post_url: str | None = None
    is_delete: DeleteFlag = DeleteFlag.NO
    created_at: datetime


class SubMovieCreate(AppModel):
    movie_name: str
    tmdb_id: int
    sub_user: int
    category_folder: str


class SehuaDataRow(AppModel):
    id: int
    section_name: str
    av_number: str
    title: str
    movie_type: str
    size: str
    magnet: str
    post_url: str
    publish_date: date
    pub_url: str
    image_path: str
    save_path: str
    is_download: DownloadFlag = DownloadFlag.NO
    created_at: datetime


class SehuaDataCreate(AppModel):
    section_name: str
    av_number: str
    title: str
    movie_type: str
    size: str
    magnet: str
    post_url: str
    publish_date: date
    pub_url: str
    image_path: str
    save_path: str


class T66yRow(AppModel):
    id: int
    section_name: str
    movie_info: str | None = None
    title: str
    magnet: str
    poster_url: str | None = None
    publish_date: date
    pub_url: str
    save_path: str
    is_download: DownloadFlag = DownloadFlag.NO
    created_at: datetime


class T66yCreate(AppModel):
    section_name: str
    title: str
    movie_info: str | None = None
    poster_url: str | None = None
    magnet: str
    publish_date: date
    pub_url: str
    save_path: str


class JavbusRow(AppModel):
    id: int
    av_number: str
    actress: str | None = None
    sub_category: str
    movie_info: str | None = None
    title: str
    magnet: str
    poster_url: str | None = None
    publish_date: date
    pub_url: str
    save_path: str
    is_download: DownloadFlag = DownloadFlag.NO
    created_at: datetime


class JavbusCreate(AppModel):
    av_number: str
    actress: str | None = None
    sub_category: str
    movie_info: str | None = None
    title: str
    magnet: str
    poster_url: str | None = None
    publish_date: date
    pub_url: str
    save_path: str
