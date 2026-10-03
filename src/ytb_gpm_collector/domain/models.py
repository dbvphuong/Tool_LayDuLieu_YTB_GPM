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
    # Thông tin kênh YouTube đã lưu trữ/cache từ phiên trước
    channel_id: Optional[str] = Field(default=None, description="ID kênh YouTube liên kết")
    channel_name: Optional[str] = Field(default=None, description="Tên kênh YouTube")
    is_authenticated: Optional[bool] = Field(default=None, description="Trạng thái đăng nhập YouTube Studio")
    last_collected_at: Optional[str] = Field(default=None, description="Thời điểm cào dữ liệu gần nhất")


class GpmStartResult(BaseModel):
    """Kết quả khởi động Profile từ GPM API."""
    success: bool
    profile_id: str
    remote_debugging_address: Optional[str] = None
    websocket_debugging_url: Optional[str] = None
    driver_path: Optional[str] = None
    message: Optional[str] = None


class ChannelIdentity(BaseModel):
    """Thông tin nhận diện kênh YouTube sau khi trích xuất từ YouTube Studio."""
    channel_id: str = Field(..., description="ID kênh YouTube (bắt đầu bằng UC...)")
    channel_name: str = Field(..., description="Tên kênh YouTube hiển thị")
    url: str = Field(default="", description="URL hiện tại của kênh trong Studio")
    is_authenticated: bool = Field(default=True, description="Trạng thái đã đăng nhập")


class ChannelCache(BaseModel):
    """Cache thông tin đăng nhập và kênh YouTube của một profile."""
    profile_id: str
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    is_authenticated: bool = False
    last_collected_at: Optional[str] = None
    notes: Optional[str] = None


class AppSessionState(BaseModel):
    """Lưu trữ cấu hình và trạng thái lựa chọn của phiên làm việc gần nhất."""
    selected_profile_ids: List[str] = Field(default_factory=list, description="Danh sách Profile được tích chọn gần nhất")
    video_selection_mode: str = Field(default="recent_count", description="Chế độ chọn video: recent_count hoặc date_range hoặc all")
    video_limit: int = Field(default=10, description="Số lượng video gần nhất cần lấy")
    date_range_preset: str = Field(default="28_days", description="Khoảng thời gian: 28_days, 90_days, custom...")
    custom_date_from: Optional[str] = Field(default=None, description="Ngày bắt đầu tùy chỉnh (YYYY-MM-DD)")
    custom_date_to: Optional[str] = Field(default=None, description="Ngày kết thúc tùy chỉnh (YYYY-MM-DD)")
    concurrency: int = Field(default=2, description="Số luồng chạy song song")
    api_port: int = Field(default=9495, description="Cổng GPM API đã dùng")


class RunHistoryRecord(BaseModel):
    """Bản ghi lịch sử một đợt chạy thu thập."""
    run_id: str
    profile_id: str
    profile_name: str
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    period: str = "28_days"
    video_count: int = 0
    status: str = "running"  # running, success, partial, failed
    output_dir: str
    started_at: str
    finished_at: Optional[str] = None
    error_message: Optional[str] = None
