# -*- coding: utf-8 -*-
from app.models.base import AppModel
from app.models.enums import DownloadFlag, DeleteFlag, StrmMode, LogLevel, DownloadUrlType
from app.models.config import BotConfig
from app.models.db import (
    OfflineTaskRow, OfflineTaskCreate,
    AvDailyUpdateRow, AvDailyUpdateCreate,
    SubMovieRow, SubMovieCreate,
    SehuaDataRow, SehuaDataCreate,
    T66yRow, T66yCreate,
    JavbusRow, JavbusCreate,
)
from app.models.context import (
    DownloadUserData, AvDownloadUserData,
    SubscribeMovieUserData, RssUserData, RenameData,
)
from app.models.dto import PendingTask, PendingPushTask, VideoTaskInfo
