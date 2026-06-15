"""Asset management schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AssetType = Literal["notebook", "smartphone", "tablet", "other"]
AssetStatus = Literal["active", "maintenance", "retired", "lost"]


class AssetHistoryOut(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    action: str
    holder_name: str | None
    holder_dept: str | None
    changed_by: str
    changed_at: datetime
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    notes: str | None


class AssetListItem(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    asset_tag: str | None
    asset_type: str
    brand: str | None
    model: str
    status: str
    holder_id: str | None
    holder_name: str | None
    holder_dept: str | None
    acquired_at: date | None
    created_at: datetime
    updated_at: datetime


class AssetOut(AssetListItem):
    serial_number: str | None
    warranty_until: date | None
    specs: dict[str, Any]
    compliance: dict[str, Any]
    notes: str | None
    created_by: str | None
    history: list[AssetHistoryOut] = Field(default_factory=list)


class AssetCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    asset_tag: str | None = Field(default=None, max_length=50)
    asset_type: AssetType
    brand: str | None = Field(default=None, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    serial_number: str | None = Field(default=None, max_length=100)
    status: AssetStatus = "active"
    acquired_at: date | None = None
    warranty_until: date | None = None
    specs: dict[str, Any] = Field(default_factory=dict)
    compliance: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)


class AssetUpdate(BaseModel):
    model_config = ConfigDict(strict=True)

    asset_tag: str | None = Field(default=None, max_length=50)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    serial_number: str | None = Field(default=None, max_length=100)
    status: AssetStatus | None = None
    acquired_at: date | None = None
    warranty_until: date | None = None
    specs: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AssetAssignIn(BaseModel):
    model_config = ConfigDict(strict=True)

    holder_id: str = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=500)


class AssetReturnIn(BaseModel):
    model_config = ConfigDict(strict=True)

    notes: str | None = Field(default=None, max_length=500)


class AssetListOut(BaseModel):
    model_config = ConfigDict(strict=True)

    items: list[AssetListItem]
    total: int
