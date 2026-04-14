# -*- coding: utf-8 -*-
from enum import Enum, IntEnum


class DownloadFlag(IntEnum):
    NO = 0
    YES = 1


class DeleteFlag(IntEnum):
    NO = 0
    YES = 1


class StrmMode(str, Enum):
    DISABLE = "disable"
    STRM_LOCAL = "strm_local"
    STRM_REMOTE = "strm_remote"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DownloadUrlType(str, Enum):
    ED2K = "ED2K"
    THUNDER = "thunder"
    MAGNET = "magnet"
    HTTP = "http"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value
