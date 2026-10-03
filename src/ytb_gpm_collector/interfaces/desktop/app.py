"""Desktop Application entrypoint and Qt lifecycle management."""

import sys
import logging
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ytb_gpm_collector.config import AppConfig
from ytb_gpm_collector.interfaces.desktop.theme import get_application_stylesheet
from ytb_gpm_collector.interfaces.desktop.main_window import MainWindow

logger = logging.getLogger(__name__)


def create_application(argv: Optional[List[str]] = None) -> QApplication:
    """Khởi tạo QApplication với cấu hình Soft Blue stylesheet và font chữ chuẩn."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv or sys.argv)

    app.setApplicationName("YTB Studio Data Collector")
    app.setApplicationDisplayName("")
    app.setOrganizationName("YTB Tools")

    # Set font hệ thống dịu mắt
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    # Nạp bộ Qt Style Sheet Soft Blue
    app.setStyleSheet(get_application_stylesheet())

    return app


def run_desktop_app(config: Optional[AppConfig] = None) -> int:
    """Chạy vòng lặp ứng dụng Desktop PySide6."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = create_application()
    window = MainWindow(config=config)
    window.show()

    # Tự động tải danh sách Profile GPM sau khi giao diện đã hiển thị
    window.page_collector.reload_profiles(async_mode=True)

    return app.exec()


def main() -> None:
    """Hàm main gọi từ CLI."""
    sys.exit(run_desktop_app())


if __name__ == "__main__":
    main()
