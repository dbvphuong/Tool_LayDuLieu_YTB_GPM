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
    group_name: Optional[str] = Field(default=None, description="Tên nhóm profile trên GPM")
    is_running: bool = Field(default=False, description="Trạng thái profile đang bật hay tắt")
    note: Optional[str] = Field(default=None, description="Ghi chú của profile trên GPMLogin")
    # Thông tin kênh YouTube đã lưu trữ/cache từ phiên trước
    channel_id: Optional[str] = Field(default=None, description="ID kênh YouTube liên kết")
    channel_name: Optional[str] = Field(default=None, description="Tên kênh YouTube")
    is_authenticated: Optional[bool] = Field(default=None, description="Trạng thái đăng nhập YouTube Studio")
    last_collected_at: Optional[str] = Field(default=None, description="Thời điểm cào dữ liệu gần nhất")


class GpmGroup(BaseModel):
    """Thông tin Nhóm Profile trên GPM."""
    id: str = Field(..., description="ID định danh duy nhất của nhóm (GUID)")
    name: str = Field(..., description="Tên nhóm trên GPM")
    sort_order: Optional[int] = Field(default=0, description="Thứ tự sắp xếp của nhóm")


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
    selected_group_id: Optional[str] = Field(default=None, description="Nhóm profile được chọn gần nhất")


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


class StudioExportResult(BaseModel):
    """Kết quả một lần xuất báo cáo từ YouTube Studio."""
    success: bool
    channel_id: str
    channel_name: str
    date_preset: str = "28_days"
    raw_file_path: str
    evidence_image_path: Optional[str] = None
    file_size_bytes: int = 0
    exported_at: str
    message: Optional[str] = None


class ParsedVideoRow(BaseModel):
    """Bản ghi số liệu của một video trích xuất từ bảng báo cáo YouTube Studio."""
    video_id: str = Field(..., description="ID video YouTube hoặc chuỗi định danh nội dung")
    video_title: Optional[str] = Field(default=None, description="Tiêu đề video")
    publish_date: Optional[str] = Field(default=None, description="Thời gian xuất bản video")
    duration_seconds: Optional[float] = Field(default=None, description="Thời lượng video tính bằng giây")
    views: Optional[int] = Field(default=None, description="Số lượt xem")
    watch_time_hours: Optional[float] = Field(default=None, description="Thời gian xem tính bằng giờ")
    average_view_duration_seconds: Optional[float] = Field(default=None, description="Thời lượng xem trung bình (giây)")
    subscribers: Optional[int] = Field(default=None, description="Số người đăng ký mới hoặc ròng")
    impressions: Optional[int] = Field(default=None, description="Số lượt hiển thị hình thu nhỏ")
    ctr_percent: Optional[float] = Field(default=None, description="Tỷ lệ nhấp vào hình thu nhỏ (%)")
    estimated_revenue: Optional[float] = Field(default=None, description="Doanh thu ước tính (nếu có)")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Toàn bộ dữ liệu gốc của dòng")


class ParsedSummaryRow(BaseModel):
    """Bản ghi tổng số liệu toàn kênh (dòng Tổng / Total) từ bảng báo cáo."""
    label: str = Field(default="Tổng", description="Nhãn dòng tổng")
    views: Optional[int] = Field(default=None, description="Tổng lượt xem kênh")
    watch_time_hours: Optional[float] = Field(default=None, description="Tổng thời gian xem (giờ)")
    average_view_duration_seconds: Optional[float] = Field(default=None, description="Thời lượng xem trung bình chung (giây)")
    subscribers: Optional[int] = Field(default=None, description="Tổng số người đăng ký")
    impressions: Optional[int] = Field(default=None, description="Tổng lượt hiển thị")
    ctr_percent: Optional[float] = Field(default=None, description="Tỷ lệ nhấp trung bình kênh (%)")
    estimated_revenue: Optional[float] = Field(default=None, description="Tổng doanh thu (nếu có)")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Dữ liệu gốc của dòng tổng")


class ParsedDailyMetricRow(BaseModel):
    """Bản ghi số liệu theo ngày từ file Dữ liệu biểu đồ hoặc Tổng số."""
    date: str = Field(..., description="Ngày ghi nhận số liệu (YYYY-MM-DD)")
    video_id: Optional[str] = Field(default=None, description="ID video (nếu là số liệu chi tiết theo video)")
    video_title: Optional[str] = Field(default=None, description="Tiêu đề video")
    views: Optional[int] = Field(default=None, description="Số lượt xem trong ngày")
    watch_time_hours: Optional[float] = Field(default=None, description="Thời gian xem trong ngày (giờ)")
    duration_seconds: Optional[float] = Field(default=None, description="Thời lượng video (nếu có)")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Dữ liệu gốc của dòng")


class ParsedTableData(BaseModel):
    """Kết quả phân tích cú pháp một bảng báo cáo Studio (ví dụ: Dữ liệu trong bảng.csv hoặc sheet Excel)."""
    source_file: str = Field(..., description="Tên hoặc đường dẫn file nguồn")
    columns: List[str] = Field(default_factory=list, description="Danh sách cột gốc trong file")
    column_mapping: Dict[str, str] = Field(default_factory=dict, description="Bảng ánh xạ cột gốc -> trường chuẩn")
    unmapped_columns: List[str] = Field(default_factory=list, description="Danh sách cột chưa ánh xạ được")
    summary_row: Optional[ParsedSummaryRow] = Field(default=None, description="Dòng tổng (Tổng/Total) nếu có")
    video_rows: List[ParsedVideoRow] = Field(default_factory=list, description="Danh sách các dòng video chi tiết")
    total_raw_rows: int = Field(default=0, description="Tổng số dòng dữ liệu đọc được")


class StudioRawBundle(BaseModel):
    """Tập hợp tất cả dữ liệu đọc được từ gói báo cáo Studio (raw dir, zip file hoặc tập hợp CSV/XLSX)."""
    source_path: str = Field(..., description="Đường dẫn file zip hoặc thư mục raw chứa dữ liệu")
    table_data: Optional[ParsedTableData] = Field(default=None, description="Dữ liệu bảng chi tiết video")
    daily_chart_data: List[ParsedDailyMetricRow] = Field(default_factory=list, description="Dữ liệu biểu đồ theo ngày từng video")
    daily_totals_data: List[ParsedDailyMetricRow] = Field(default_factory=list, description="Dữ liệu tổng lượt xem theo ngày toàn kênh")
    discovered_files: List[str] = Field(default_factory=list, description="Danh sách tất cả file tìm thấy")


class NormalizedVideoRecord(BaseModel):
    """Bản ghi video đã được chuẩn hóa cho CSV và JSONL theo đặc tả kiến trúc."""
    channel_id: str = Field(..., description="ID kênh YouTube (UC...)")
    video_id: str = Field(..., description="ID video YouTube")
    video_title: Optional[str] = Field(default=None, description="Tiêu đề video")
    publish_date: Optional[str] = Field(default=None, description="Ngày xuất bản video (YYYY-MM-DD)")
    duration_seconds: Optional[float] = Field(default=None, description="Thời lượng video tính bằng giây")
    period_start: str = Field(..., description="Ngày bắt đầu khoảng thời gian phân tích (YYYY-MM-DD)")
    period_end: str = Field(..., description="Ngày kết thúc khoảng thời gian phân tích (YYYY-MM-DD)")
    period_kind: str = Field(default="fixed_calendar_range", description="Loại khoảng thời gian (ví dụ 28_days)")
    views: Optional[int] = Field(default=None, description="Số lượt xem")
    watch_time_hours: Optional[float] = Field(default=None, description="Thời gian xem (giờ)")
    average_view_duration_seconds: Optional[float] = Field(default=None, description="Thời lượng xem trung bình (giây)")
    impressions: Optional[int] = Field(default=None, description="Số lượt hiển thị hình thu nhỏ")
    ctr_percent: Optional[float] = Field(default=None, description="Tỷ lệ nhấp (%)")
    subscribers: Optional[int] = Field(default=None, description="Số người đăng ký")
    estimated_revenue: Optional[float] = Field(default=None, description="Doanh thu ước tính (nếu có)")
    status: str = Field(default="ok", description="Trạng thái số liệu: ok, zero, not_available, failed")
    status_reason: Optional[str] = Field(default=None, description="Lý do chi tiết khi trạng thái khác ok")
    source_file: str = Field(..., description="Đường dẫn file nguồn gốc")


class NormalizedTrafficSourceRecord(BaseModel):
    """Bản ghi nguồn lưu lượng truy cập đã chuẩn hóa."""
    channel_id: str = Field(..., description="ID kênh YouTube")
    video_id: Optional[str] = Field(default=None, description="ID video cụ thể (nếu có)")
    traffic_source: str = Field(..., description="Tên nguồn lưu lượng truy cập")
    views: Optional[int] = Field(default=None, description="Số lượt xem từ nguồn")
    watch_time_hours: Optional[float] = Field(default=None, description="Thời gian xem từ nguồn (giờ)")
    average_view_duration_seconds: Optional[float] = Field(default=None, description="Thời lượng xem trung bình (giây)")
    impressions: Optional[int] = Field(default=None, description="Lượt hiển thị từ nguồn")
    ctr_percent: Optional[float] = Field(default=None, description="Tỷ lệ nhấp từ nguồn (%)")
    period_start: str = Field(..., description="Ngày bắt đầu")
    period_end: str = Field(..., description="Ngày kết thúc")
    status: str = Field(default="ok", description="Trạng thái số liệu")
    source_file: str = Field(..., description="Đường dẫn file nguồn")


class NormalizedChannelOverview(BaseModel):
    """Tổng quan số liệu kênh cho file data/channel.json."""
    channel_id: str = Field(..., description="ID kênh YouTube")
    channel_name: Optional[str] = Field(default=None, description="Tên kênh YouTube")
    period_start: str = Field(..., description="Ngày bắt đầu")
    period_end: str = Field(..., description="Ngày kết thúc")
    period_kind: str = Field(default="28_days", description="Loại khoảng thời gian")
    total_views: Optional[int] = Field(default=None, description="Tổng lượt xem kênh")
    total_watch_time_hours: Optional[float] = Field(default=None, description="Tổng thời gian xem (giờ)")
    total_impressions: Optional[int] = Field(default=None, description="Tổng lượt hiển thị")
    average_ctr_percent: Optional[float] = Field(default=None, description="Tỷ lệ nhấp trung bình toàn kênh (%)")
    total_subscribers: Optional[int] = Field(default=None, description="Tổng người đăng ký")
    video_count: int = Field(default=0, description="Số lượng video đã trích xuất")
    source_file: str = Field(..., description="File nguồn")
    normalized_at: str = Field(..., description="Thời điểm chuẩn hóa ISO")


class NormalizationResult(BaseModel):
    """Kết quả hoàn tất chuẩn hóa dữ liệu cho một đợt chạy."""
    success: bool
    run_id: str
    channel_id: str
    period_start: str
    period_end: str
    videos_count: int = 0
    daily_metrics_count: int = 0
    traffic_sources_count: int = 0
    generated_files: List[str] = Field(default_factory=list, description="Danh sách các file sinh ra trong data/")
    message: Optional[str] = None


class QualityIssue(BaseModel):
    """Một vấn đề hoặc cảnh báo về chất lượng dữ liệu."""
    code: str = Field(..., description="Mã lỗi/cảnh báo (ví dụ MISSING_CTR, ZERO_VIEWS, DISCREPANCY)")
    level: str = Field(default="warning", description="Mức độ nghiêm trọng: info, warning, error")
    video_id: Optional[str] = Field(default=None, description="ID video liên quan (nếu có)")
    video_title: Optional[str] = Field(default=None, description="Tiêu đề video (nếu có)")
    field: Optional[str] = Field(default=None, description="Trường dữ liệu liên quan")
    message: str = Field(..., description="Mô tả chi tiết vấn đề")
    source_file: Optional[str] = Field(default=None, description="File nguồn chứa vấn đề")


class QualityReportSummary(BaseModel):
    """Tổng hợp số liệu kiểm tra chất lượng."""
    total_videos_checked: int = Field(default=0, description="Tổng số video được kiểm tra")
    valid_videos_count: int = Field(default=0, description="Số video hợp lệ đầy đủ")
    warning_videos_count: int = Field(default=0, description="Số video có cảnh báo")
    failed_videos_count: int = Field(default=0, description="Số video bị lỗi dữ liệu")
    total_warnings: int = Field(default=0, description="Tổng số lượng cảnh báo phát hiện")
    total_errors: int = Field(default=0, description="Tổng số lượng lỗi phát hiện")
    completeness_score_percent: float = Field(default=100.0, description="Tỷ lệ trường dữ liệu đầy đủ (%)")


class QualityReconciliation(BaseModel):
    """Đối chiếu số liệu tổng dòng so với tổng kênh."""
    reconciled: bool = Field(default=True, description="Trạng thái đối chiếu có khớp hoặc hợp lý")
    total_video_views: int = Field(default=0, description="Tổng lượt xem của tất cả các video chi tiết")
    channel_summary_views: Optional[int] = Field(default=None, description="Tổng lượt xem toàn kênh từ dòng Tổng")
    views_difference: Optional[int] = Field(default=None, description="Chênh lệch lượt xem (Kênh - Chi tiết)")
    difference_percent: Optional[float] = Field(default=None, description="Tỷ lệ chênh lệch (%)")
    notes: Optional[str] = Field(default=None, description="Ghi chú đối chiếu")


class QualityChecks(BaseModel):
    """Chi tiết kết quả các bài kiểm tra chất lượng."""
    channel_id_verified: bool = Field(default=True, description="Channel ID đã được xác thực")
    period_consistency: bool = Field(default=True, description="Khoảng ngày nhất quán")
    summary_reconciliation: Optional[QualityReconciliation] = Field(default=None, description="Kết quả đối chiếu tổng")
    raw_files_intact: bool = Field(default=True, description="Các file raw không bị rỗng hoặc hỏng")
    evidence_images_present: bool = Field(default=False, description="Có ảnh chụp bằng chứng đối chiếu")


class QualityReport(BaseModel):
    """Báo cáo chất lượng dữ liệu chi tiết cho đợt chạy (quality_report.json)."""
    run_id: str = Field(..., description="Mã đợt chạy")
    generated_at: str = Field(..., description="Thời điểm sinh báo cáo ISO")
    status: str = Field(default="passed", description="Trạng thái tổng quát: passed, warnings, failed")
    channel_id: str = Field(..., description="ID kênh YouTube")
    period_start: str = Field(..., description="Ngày bắt đầu")
    period_end: str = Field(..., description="Ngày kết thúc")
    summary: QualityReportSummary = Field(default_factory=QualityReportSummary)
    status_breakdown: Dict[str, int] = Field(default_factory=dict, description="Thống kê số lượng theo status: ok, zero, not_available...")
    checks: QualityChecks = Field(default_factory=QualityChecks)
    issues: List[QualityIssue] = Field(default_factory=list, description="Danh sách các cảnh báo và lỗi")
    suggestions: List[str] = Field(default_factory=list, description="Các khuyến nghị xử lý cho AI và người dùng")
    coverage: Dict[str, Any] = Field(default_factory=dict, description="Độ phủ dữ liệu theo video, ngày và nguồn truy cập")


class ManifestFileInfo(BaseModel):
    """Thông tin tệp tin trong gói kết quả."""
    path: str = Field(..., description="Đường dẫn tương đối của file trong run_dir")
    size_bytes: int = Field(default=0, description="Kích thước tệp tin (bytes)")
    sha256: str = Field(default="", description="Mã băm SHA-256")
    category: str = Field(default="data", description="Phân loại: data, raw, evidence, report, other")


class RunManifest(BaseModel):
    """Bản kê thông tin toàn bộ gói dữ liệu đợt chạy (manifest.json)."""
    schema_version: str = Field(default="1.0", description="Phiên bản schema")
    run_id: str = Field(..., description="Mã đợt chạy")
    channel_id: str = Field(..., description="ID kênh YouTube")
    channel_name: Optional[str] = Field(default=None, description="Tên kênh YouTube")
    profile_id: Optional[str] = Field(default=None, description="ID profile GPM")
    profile_name: Optional[str] = Field(default=None, description="Tên profile GPM")
    period: str = Field(default="28_days", description="Khoảng thời gian (ví dụ 28_days)")
    period_start: str = Field(..., description="Ngày bắt đầu (YYYY-MM-DD)")
    period_end: str = Field(..., description="Ngày kết thúc (YYYY-MM-DD)")
    period_kind: str = Field(default="fixed_calendar_range", description="Loại khoảng thời gian")
    collection_depth: str = Field(default="standard", description="Mức thu thập đã chọn")
    extra_exports: Dict[str, Any] = Field(default_factory=dict, description="Kết quả các báo cáo xuất bổ sung")
    created_at: str = Field(..., description="Thời điểm khởi tạo ISO")
    finished_at: Optional[str] = Field(default=None, description="Thời điểm hoàn thành ISO")
    status: str = Field(default="initialized", description="Trạng thái: initialized, running, success, partial, failed")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Tóm tắt số lượng video, daily metrics, raw, evidence...")
    files: List[ManifestFileInfo] = Field(default_factory=list, description="Danh mục tệp tin và mã băm SHA-256")
    quality_summary: Optional[Dict[str, Any]] = Field(default=None, description="Tóm tắt chất lượng dữ liệu từ quality_report")




