"""Domain models for GPM Profiles, Youtube Studio runs, and collected metrics."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class GpmProfile(BaseModel):
    """Thông tin Profile GPM-Login."""
    id: str = Field(..., description="ID định danh duy nhất của profile (GUID)")
    name: str = Field(..., description="Tên hiển thị của profile trên GPM")
    raw_proxy: Optional[str] = Field(default=None, description="Chuỗi cấu hình Proxy nguyên bản")
    proxy_host: Optional[str] = Field(default=None, description="Địa chỉ Host Proxy")
    proxy_port: Optional[int] = Field(default=None, description="Cổng Proxy")
    browser_type: Optional[str] = Field(default="Chrome", description="Loại nhân trình duyệt")
    browser_version: Optional[str] = Field(default=None, description="Phiên bản trình duyệt")
    group_id: Optional[str] = Field(default=None, description="ID nhóm profile")
    is_running: bool = Field(default=False, description="Trạng thái profile đang bật hay tắt")


class GpmStartResult(BaseModel):
    """Kết quả khởi động Profile từ GPM API."""
    success: bool
    profile_id: str
    remote_debugging_address: Optional[str] = None
    websocket_debugging_url: Optional[str] = None
    driver_path: Optional[str] = None
    message: Optional[str] = None
