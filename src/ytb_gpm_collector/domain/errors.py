"""Exceptions and error definitions for the collector."""

class CollectorError(Exception):
    """Lỗi cơ sở của tool thu thập."""
    pass


class GpmConnectionError(CollectorError):
    """Không thể kết nối tới GPM Local API."""
    pass


class GpmProfileNotFoundError(CollectorError):
    """Không tìm thấy profile được yêu cầu."""
    pass


class GpmStartProfileError(CollectorError):
    """Lỗi khi gọi API khởi động profile."""
    pass


class StudioNavigationError(CollectorError):
    """Lỗi khi điều hướng trong YouTube Studio."""
    pass


class StudioAuthenticationError(CollectorError):
    """Profile chưa đăng nhập YouTube Studio."""
    pass


class ReportExportError(CollectorError):
    """Lỗi khi xuất hoặc tải báo cáo từ YouTube Studio."""
    pass
