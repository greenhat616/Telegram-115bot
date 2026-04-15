# -*- coding: utf-8 -*-

import sqlite3
from app import init
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class SqlLiteLib:
    def __init__(self, db_file: str = ""):
        db_path = db_file or init.DB_FILE
        self.conn: sqlite3.Connection = sqlite3.connect(db_path)
        self.cursor: sqlite3.Cursor = self.conn.cursor()
        self.logger = init.logger

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def execute_sql(self, sql: str, params: tuple = ()):
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"执行查询时发生错误: {e}, sql: {sql}")

    def query(self, sql: str, params: tuple = ()):
        self.cursor.execute(sql, params)
        res_list = self.cursor.fetchall()
        return res_list

    def query_all(self, sql: str, params: tuple = ()):
        """查询所有记录，返回字典列表"""
        try:
            self.cursor.execute(sql, params)
            columns = [description[0] for description in self.cursor.description]
            rows = self.cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            self.logger.error(f"执行查询时发生错误: {e}, sql: {sql}")
            return []

    def query_one(self, sql: str, params=None):
        try:
            self.cursor.execute(sql, params or ())
            res = self.cursor.fetchone()
            return res[0] if res else None
        except Exception as e:
            self.logger.error(f"执行查询时发生错误: {e}, sql: {sql}")
            return None

    def query_row(self, sql: str, params=None):
        try:
            self.cursor.execute(sql, params or ())
            res = self.cursor.fetchone()
            return res if res else None
        except Exception as e:
            self.logger.error(f"执行查询时发生错误: {e}, sql: {sql}")

    def query_row_dict(self, sql: str, params=None) -> dict | None:
        """查询单行，返回字典"""
        try:
            self.cursor.execute(sql, params or ())
            res = self.cursor.fetchone()
            if res is None:
                return None
            columns = [description[0] for description in self.cursor.description]
            return dict(zip(columns, res))
        except Exception as e:
            self.logger.error(f"执行查询时发生错误: {e}, sql: {sql}")
            return None

    def query_as(self, model: type[T], sql: str, params: tuple = ()) -> list[T]:
        """查询并返回 Pydantic 模型列表"""
        rows = self.query_all(sql, params)
        return [model.model_validate(row) for row in rows]

    def query_one_as(self, model: type[T], sql: str, params: tuple = ()) -> T | None:
        """查询单行并返回 Pydantic 模型"""
        row = self.query_row_dict(sql, params)
        return model.model_validate(row) if row else None

    def close(self):
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()
