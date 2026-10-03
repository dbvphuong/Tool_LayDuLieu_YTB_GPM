"""Main application window for YTB GPM Collector.

Implements the single-window architecture:
- Left: Navy Slate Sidebar (SidebarWidget)
- Right: Content Stack (QStackedWidget) with 4 tabs
- Smooth coordination and GPM connection detection
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QStackedWidget,
)

from ytb_gpm_collector.application.coordinator import CollectionCoordinator
from ytb_gpm_collector.domain.models import GpmProfile
from ytb_gpm_collector.config import AppConfig, read_gpm_api_port_from_setting
from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.interfaces.desktop.sidebar import SidebarWidget
from ytb_gpm_collector.interfaces.desktop.pages.collector_page import CollectorPage
from ytb_gpm_collector.interfaces.desktop.pages.history_page import HistoryPage
from ytb_gpm_collector.interfaces.desktop.pages.logs_page import LogsPage, setup_qt_logging
from ytb_gpm_collector.interfaces.desktop.pages.settings_page import SettingsPage

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Cửa sổ chính của công cụ Thu thập dữ liệu YouTube Studio GPM."""

    def __init__(self, config: Optional[AppConfig] = None, parent: QWidget = None):
        super().__init__(parent)
        self.config = config or AppConfig()
        self.gpm_client = GpmClient(port=self.config.api_port)

        self._init_window()
        self._init_ui()
        self._wire_signals()

        # Kiểm tra kết nối GPM ngay sau khi UI khởi tạo xong
        QTimer.singleShot(200, self.check_gpm_status)

    def _init_window(self) -> None:
        self.setWindowTitle("YTB Studio Data Collector v1.0 | GPM Automation")
        self.resize(1200, 800)
        self.setMinimumSize(1024, 680)

    def _init_ui(self) -> None:
        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)

        # Main horizontal layout: Sidebar (Left) + Content (Right)
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar bên trái
        self.sidebar = SidebarWidget(self)
        main_layout.addWidget(self.sidebar)

        # 2. Content Stack bên phải
        self.content_stack = QStackedWidget(self)
        self.content_stack.setObjectName("contentStack")

        # 4 Trang tương ứng 4 Tab
        self.page_collector = CollectorPage(self, gpm_client=self.gpm_client)
        self.page_history = HistoryPage(
            self,
            history_storage=self.page_collector.history_storage,
            runs_dir=self.config.runs_dir,
        )
        self.page_logs = LogsPage(self)
        self.log_handler = setup_qt_logging(self.page_logs)
        self.page_settings = SettingsPage(
            self,
            config=self.config,
            history_storage=self.page_collector.history_storage,
        )

        self.content_stack.addWidget(self.page_collector)  # index 0
        self.content_stack.addWidget(self.page_history)    # index 1
        self.content_stack.addWidget(self.page_logs)       # index 2
        self.content_stack.addWidget(self.page_settings)   # index 3

        main_layout.addWidget(self.content_stack)

        # 3. Bộ điều phối đa luồng (Worker Thread Pool Coordinator - Task 4.6)
        self.coordinator = CollectionCoordinator(
            gpm_client=self.gpm_client,
            history_storage=self.page_collector.history_storage,
            runs_dir=self.config.runs_dir,
            timeout_seconds=self.config.timeout_seconds,
            parent=self,
        )

    def _wire_signals(self) -> None:
        # Sidebar điều hướng trang
        self.sidebar.tab_changed.connect(self._on_tab_changed)
        # Nút refresh kết nối ở sidebar
        self.sidebar.refresh_connection_requested.connect(self.check_gpm_status)

        # Kết nối sự kiện từ CollectorPage
        self.page_collector.start_requested.connect(self._on_collector_start_requested)
        self.page_collector.stop_requested.connect(self._on_collector_stop_requested)

        # Kết nối sự kiện từ Coordinator tới UI
        self.coordinator.worker_status.connect(self.page_collector.update_worker_status)
        self.coordinator.overall_progress.connect(self.page_collector.set_overall_progress)
        self.coordinator.log_message.connect(self._on_coordinator_log)
        self.coordinator.campaign_finished.connect(self._on_coordinator_campaign_finished)

        # Cài đặt lưu thành công -> cập nhật hệ thống
        self.page_settings.settings_saved.connect(self._on_settings_saved)

    def _on_collector_start_requested(self, config: dict) -> None:
        """Kích hoạt chạy đa luồng qua CollectionCoordinator."""
        selected_ids = config.get("selected_profile_ids", [])
        # Lấy danh sách đối tượng GpmProfile đã chọn
        selected_profiles = [p for p in self.page_collector._profiles if p.id in selected_ids]
        if not selected_profiles:
            selected_profiles = [GpmProfile(id=pid, name=f"Profile {pid}") for pid in selected_ids]

        self.coordinator.runs_dir = self.config.runs_dir
        self.coordinator.timeout_seconds = self.config.timeout_seconds
        self.coordinator.start(config, selected_profiles)

    def _on_collector_stop_requested(self) -> None:
        """Dừng chiến dịch thu thập an toàn."""
        self.coordinator.stop()

    def _on_coordinator_log(self, level: str, message: str) -> None:
        """Ghi log từ Coordinator lên LogsPage."""
        self.page_logs.append_log(message, level=level)

    def _on_coordinator_campaign_finished(self, total: int, success: int, failed: int) -> None:
        """Xử lý khi chiến dịch thu thập kết thúc."""
        self.page_collector.set_running_state(False)
        self.page_history.reload_runs()

    def _on_settings_saved(self, new_config_dict: dict) -> None:
        """Cập nhật các thành phần hệ thống khi người dùng lưu cài đặt mới."""
        self.config = AppConfig.from_dict(new_config_dict)
        self.gpm_client.port = self.config.api_port
        self.coordinator.runs_dir = self.config.runs_dir
        self.coordinator.timeout_seconds = self.config.timeout_seconds
        self.page_history.runs_dir = self.config.runs_dir
        self.page_collector.concurrency_spin.setValue(self.config.default_concurrency)
        self.check_gpm_status()
        self.page_logs.success(
            f"Đã áp dụng cấu hình mới: Port {self.config.api_port}, {self.config.default_concurrency} luồng mặc định, thư mục {self.config.runs_dir.name}."
        )

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= index < self.content_stack.count():
            self.content_stack.setCurrentIndex(index)
            if index == 1:
                self.page_history.reload_runs()

    def switch_to_tab(self, index: int) -> None:
        """Chuyển tab lập trình qua index."""
        self.sidebar.set_current_tab(index)
        self.content_stack.setCurrentIndex(index)
        if index == 1:
            self.page_history.reload_runs()

    def check_gpm_status(self) -> bool:
        """Kiểm tra và cập nhật trạng thái kết nối tới GPM Local API."""
        port = self.gpm_client.port
        try:
            connected = self.gpm_client.check_connection()
            # Cập nhật cổng nếu client tự động phát hiện cổng khác
            current_port = self.gpm_client.port
            if connected:
                self.sidebar.set_gpm_status(current_port, True, "Sẵn sàng (Online)")
                self.page_logs.success(
                    f"Kết nối thành công tới GPM Local API tại cổng {current_port}."
                )
            else:
                self.sidebar.set_gpm_status(current_port, False, "Chưa kết nối (Offline)")
                self.page_logs.warning(
                    f"Chưa thể kết nối tới GPM Local API tại cổng {current_port}. Vui lòng mở GPMLogin."
                )

            return connected
        except Exception as ex:
            logger.warning("Lỗi kiểm tra GPM API: %s", ex)
            self.sidebar.set_gpm_status(port, False, "Lỗi kết nối")
            return False

    def closeEvent(self, event) -> None:
        if hasattr(self, "coordinator") and self.coordinator:
            self.coordinator.stop()
        if hasattr(self, "log_handler") and self.log_handler:
            logging.getLogger("ytb_gpm_collector").removeHandler(self.log_handler)
        if hasattr(self, "page_collector") and self.page_collector:
            self.page_collector.cleanup()
        super().closeEvent(event)
