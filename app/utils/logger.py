# -*- coding: utf-8 -*-

import logging
import os


class Logger:
    def __init__(self, level: int = logging.INFO, log_dir: str = ""):
        """
        日志类构造函数
        :param level: 日志级别
        :param log_dir: 日志文件输出目录，为空则仅输出到控制台
        """
        self.logger = logging.getLogger()
        self.logger.setLevel(level)
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
        )

        # 设置控制台输出
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        ch.setLevel(level)
        self.logger.addHandler(ch)

        if log_dir:
            # 日志文件输出
            fs = logging.FileHandler(
                os.path.join(log_dir, "115bot.log"), encoding="utf-8", mode="w"
            )
            fs.setLevel(level)
            fs.setFormatter(fmt)
            self.logger.addHandler(fs)

    def debug(self, message):
        """
        调试消息
        :param message: 调试日志消息
        :return:
        """
        self.logger.debug(message)

    def info(self, message):
        """
        日志消息
        :param message: 日志消息
        :return:
        """
        self.logger.info(message)

    def warn(self, message):
        """
        告警消息
        :param message: 告警消息
        :return:
        """
        self.logger.warning(message)

    def warning(self, message):
        """
        告警消息
        :param message: 告警消息
        :return:
        """
        self.logger.warning(message)

    def error(self, message):
        """
        错误消息
        :param message: 错误消息
        :return:
        """
        self.logger.error(message)

    def cri(self, message):
        """
        关键消息
        :param message: 关键消息
        :return:
        """
        self.logger.critical(message)
