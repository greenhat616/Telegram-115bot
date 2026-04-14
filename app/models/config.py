# -*- coding: utf-8 -*-
from pydantic import ConfigDict, Field

from app.models.base import AppModel
from app.models.enums import LogLevel, StrmMode


class PathMapItem(AppModel):
    name: str
    path: str


class CategoryFolderItem(AppModel):
    name: str
    display_name: str
    path_map: list[PathMapItem]


class CleanPolicyConfig(AppModel):
    switch: str = "on"
    less_than: str = "400M"


class AvDailyUpdateConfig(AppModel):
    enable: bool = False
    sync_time: str = "20:00"
    save_path: str = "/AV/日更"
    notify_me: bool = True
    sort_by_year_month: bool = False


class SehuaSectionConfig(AppModel):
    name: str
    save_path: str


class SehuaSpiderConfig(AppModel):
    enable: bool = False
    sync_time: str = "03:00"
    base_url: str = "www.sehuatang.net"
    sections: list[SehuaSectionConfig] = []
    notify_me: bool = True
    sort_by_year_month: bool = False


class SubConditionConfig(AppModel):
    zh_cn: bool = True
    dolby_vision: bool = False
    resolution_priority: list[int] = [2160, 1080]


class Aria2Config(AppModel):
    enable: bool = False
    device_name: str = "Aria2"
    host: str = ""
    port: int = 6800
    rpc_secret: str = ""
    download_path: str = "/Downloads"


class AIConfig(AppModel):
    api_url: str = ""
    api_key: str = ""
    model: str = ""


class JavbusCategoryConfig(AppModel):
    name: str
    route: str
    need_input: bool = False
    save_path: str


class JavbusRssConfig(AppModel):
    max_subscribe: int = 0
    timeout: int = 60
    category: list[JavbusCategoryConfig] = []
    notify_me: bool = True
    sort_by_year_month: bool = False


class T66ySectionConfig(AppModel):
    name: str
    save_path: str


class T66yRssConfig(AppModel):
    timeout: int = 60
    sections: list[T66ySectionConfig] = []
    notify_me: bool = True
    sort_by_year_month: bool = False


class RssHubConfig(AppModel):
    rss_host: str = ""
    javbus: JavbusRssConfig = JavbusRssConfig()
    t66y: T66yRssConfig = T66yRssConfig()


class BotConfig(AppModel):
    model_config = ConfigDict(protected_namespaces=(), extra="ignore")

    log_level: LogLevel = LogLevel.INFO
    bot_token: str
    allowed_user: int | str
    bot_name: str | None = None
    bote_name: str | None = None
    tg_api_id: int | None = None
    tg_api_hash: str | None = None
    app_115_id: str | None = Field(default=None, alias="115_app_id")

    # nullbr API
    x_app_id: str | None = None
    x_api_key: str | None = None

    # access/refresh tokens (runtime)
    access_token: str | None = None
    refresh_token: str | None = None

    clean_policy: CleanPolicyConfig = CleanPolicyConfig()
    category_folder: list[CategoryFolderItem] = []

    av_daily_update: AvDailyUpdateConfig = AvDailyUpdateConfig()
    sehua_spider: SehuaSpiderConfig = SehuaSpiderConfig()

    strm_mode: StrmMode = StrmMode.DISABLE
    strm_root: str = "/media/115"
    openlist_root: str = "/115"
    mount_root: str = "/CloudNAS/115"

    emby_server: str | None = None
    api_key: str | None = None

    sub_condition: SubConditionConfig = SubConditionConfig()
    aria2: Aria2Config = Aria2Config()
    ai: AIConfig = AIConfig()
    rsshub: RssHubConfig = RssHubConfig()

    selenium_timeout: int = 60
    offline_path: str | None = None
