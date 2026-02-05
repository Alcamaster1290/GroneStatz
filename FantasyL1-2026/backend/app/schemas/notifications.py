from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

PlatformType = Literal["android", "ios"]


class PushDeviceRegisterIn(BaseModel):
    token: str = Field(min_length=20)
    platform: PlatformType
    device_id: str = Field(min_length=3, max_length=191)
    timezone: Optional[str] = Field(default=None, max_length=64)
    app_channel: str = Field(default="mobile", min_length=2, max_length=30)
    app_version: Optional[str] = Field(default=None, max_length=40)


class PushDeviceOut(BaseModel):
    id: int
    user_id: int
    platform: PlatformType
    device_id: str
    token: str
    timezone: Optional[str] = None
    app_channel: str
    app_version: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PushDeviceRegisterOut(BaseModel):
    ok: bool
    device: PushDeviceOut


class PushDeviceDeleteOut(BaseModel):
    ok: bool
    device_id: str
