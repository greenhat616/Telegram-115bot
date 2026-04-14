# -*- coding: utf-8 -*-
from pydantic import BaseModel, ConfigDict


class AppModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
