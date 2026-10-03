"""Settings Page view (Tab 4: Cài đặt hệ thống).

Triển khai hoàn chỉnh Task 4.5:
- Form cấu hình cổng GPM Local API (19996 / 9495 hoặc tùy chỉnh).
- Nút kiểm tra kết nối ngay (Ping GPM API) và tự động dò tìm cổng đang mở.
- Cấu hình thư mục lưu trữ kết quả (runs/) kèm nút duyệt thư mục trực quan.
- Cấu hình số luồng chạy song song mặc định (1 - 10 luồng).
- Cấu hình thời gian chờ tải trang (Page Timeout 10s - 180s).
- Tùy chọn giữ file thô (raw) và tự động sinh gói báo cáo cho AI (README.md, JSONL).
- Lưu trữ bền vững vào SQLite (LocalStorage / app_settings) và phát tín hiệu settings_saved.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QMessageBox,
)

from ytb_gpm_collector.config import (
    AppConfig,
    read_gpm_api_port_from_setting,
    get_default_setting_dat_path,
    get_gpm_database_path,
)
from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.integrations.storage.history import LocalStorage, HistoryStorage
from ytb_gpm_collector.interfaces.desktop.theme import (
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
)

logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    """Màn hình Cài đặt cấu hình hệ thống (Tab 4)."""

    # Signal phát ra khi người dùng lưu cấu hình mới
    settings_saved = Signal(dict)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config: Optional[AppConfig] = None,
        history_storage: Optional[HistoryStorage] = None,
    ):
        super().__init__(parent)
        self.setProperty("class", "page-container")

        self.history_storage = history_storage or HistoryStorage()
        self.config = config or AppConfig.load_from_storage(self.history_storage)

        self._init_ui()
        self._wire_signals()
        self.load_settings()

    # =========================================================================
    # 1. KHỞI TẠO BỐ CỤC GIAO DIỆN
    # =========================================================================

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header Title & Subtitle
        header_layout = QVBoxLayout()
        header_layout.setSpacing(3)

        title = QLabel("Cài đặt hệ thống")
        title.setProperty("class", "page-title")
        header_layout.addWidget(title)

        subtitle = QLabel("Cấu hình cổng GPM Local API, số luồng song song, thời gian chờ và thư mục lưu trữ")
        subtitle.setProperty("class", "page-subtitle")
        header_layout.addWidget(subtitle)

        main_layout.addLayout(header_layout)

        # Scroll Area chứa các thẻ Form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(16)

        # ---------------------------------------------------------------------
        # Khối 1: Cấu hình kết nối GPM-Login Local API
        # ---------------------------------------------------------------------
        card_gpm = QFrame()
        card_gpm.setProperty("class", "card")
        card_gpm_layout = QVBoxLayout(card_gpm)
        card_gpm_layout.setContentsMargins(20, 18, 20, 18)
        card_gpm_layout.setSpacing(14)

        lbl_gpm_title = QLabel("1. KẾT NỐI GPM-LOGIN LOCAL API")
        lbl_gpm_title.setProperty("class", "card-title")
        card_gpm_layout.addWidget(lbl_gpm_title)

        lbl_gpm_desc = QLabel("Cấu hình cổng giao tiếp cục bộ và các đường dẫn dữ liệu của GPMLoginGlobal.")
        lbl_gpm_desc.setProperty("class", "card-subtitle")
        card_gpm_layout.addWidget(lbl_gpm_desc)

        grid_gpm = QGridLayout()
        grid_gpm.setHorizontalSpacing(16)
        grid_gpm.setVerticalSpacing(12)

        # Hàng 0: Cổng API
        lbl_port = QLabel("Cổng GPM API:")
        lbl_port.setStyleSheet("font-weight: 600; color: #1E293B;")
        grid_gpm.addWidget(lbl_port, 0, 0)

        port_row = QHBoxLayout()
        port_row.setSpacing(8)

        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(self.config.api_port)
        self.spin_port.setFixedWidth(130)
        port_row.addWidget(self.spin_port)

        self.btn_detect_port = QPushButton("🔍 Tự động dò tìm cổng")
        self.btn_detect_port.setToolTip("Quét cổng 9495, 19996 và đọc từ setting.dat của GPMLogin")
        port_row.addWidget(self.btn_detect_port)

        self.btn_ping_api = QPushButton("📡 Kiểm tra kết nối ngay (Ping)")
        self.btn_ping_api.setToolTip("Gửi yêu cầu tới GPM API để xác nhận kết nối")
        port_row.addWidget(self.btn_ping_api)

        port_row.addStretch()
        grid_gpm.addLayout(port_row, 0, 1)

        # Hàng 1: Trạng thái Ping LED
        grid_gpm.addWidget(QLabel("Trạng thái kết nối:"), 1, 0)
        self.lbl_ping_status = QLabel("⚪ Chưa kiểm tra kết nối")
        self.lbl_ping_status.setStyleSheet("font-weight: 600; font-size: 12px; color: #64748B;")
        grid_gpm.addWidget(self.lbl_ping_status, 1, 1)

        # Hàng 2: File setting.dat của GPM
        lbl_setting = QLabel("File cấu hình setting.dat:")
        lbl_setting.setStyleSheet("font-weight: 600; color: #1E293B;")
        grid_gpm.addWidget(lbl_setting, 2, 0)

        setting_row = QHBoxLayout()
        setting_row.setSpacing(8)
        self.input_setting_dat = QLineEdit()
        self.input_setting_dat.setPlaceholderText("Đường dẫn tới file setting.dat của GPM...")
        setting_row.addWidget(self.input_setting_dat)

        self.btn_browse_setting = QPushButton("📂 Chọn file...")
        setting_row.addWidget(self.btn_browse_setting)
        grid_gpm.addLayout(setting_row, 2, 1)

        # Hàng 3: File database.db của GPM
        lbl_db = QLabel("File database.db GPM:")
        lbl_db.setStyleSheet("font-weight: 600; color: #1E293B;")
        grid_gpm.addWidget(lbl_db, 3, 0)

        db_row = QHBoxLayout()
        db_row.setSpacing(8)
        self.input_db_path = QLineEdit()
        self.input_db_path.setPlaceholderText("Đường dẫn tới database.db (chứa danh sách profile)...")
        db_row.addWidget(self.input_db_path)

        self.btn_browse_db = QPushButton("📂 Chọn file...")
        db_row.addWidget(self.btn_browse_db)
        grid_gpm.addLayout(db_row, 3, 1)

        card_gpm_layout.addLayout(grid_gpm)
        content_layout.addWidget(card_gpm)

        # ---------------------------------------------------------------------
        # Khối 2: Cấu hình Lưu trữ & Tự động hóa
        # ---------------------------------------------------------------------
        card_automation = QFrame()
        card_automation.setProperty("class", "card")
        card_automation_layout = QVBoxLayout(card_automation)
        card_automation_layout.setContentsMargins(20, 18, 20, 18)
        card_automation_layout.setSpacing(14)

        lbl_auto_title = QLabel("2. LƯU TRỮ VÀ THÔNG SỐ TỰ ĐỘNG HÓA")
        lbl_auto_title.setProperty("class", "card-title")
        card_automation_layout.addWidget(lbl_auto_title)

        lbl_auto_desc = QLabel("Thiết lập thư mục xuất dữ liệu runs/, số luồng xử lý và thời gian chờ tải trang.")
        lbl_auto_desc.setProperty("class", "card-subtitle")
        card_automation_layout.addWidget(lbl_auto_desc)

        grid_auto = QGridLayout()
        grid_auto.setHorizontalSpacing(16)
        grid_auto.setVerticalSpacing(12)

        # Hàng 0: Thư mục runs_dir
        lbl_runs = QLabel("Thư mục lưu kết quả:")
        lbl_runs.setStyleSheet("font-weight: 600; color: #1E293B;")
        grid_auto.addWidget(lbl_runs, 0, 0)

        runs_row = QHBoxLayout()
        runs_row.setSpacing(8)
        self.input_runs_dir = QLineEdit()
        self.input_runs_dir.setText(str(self.config.runs_dir))
        runs_row.addWidget(self.input_runs_dir)

        self.btn_browse_runs = QPushButton("📁 Chọn thư mục...")
        runs_row.addWidget(self.btn_browse_runs)
        grid_auto.addLayout(runs_row, 0, 1)

        # Hàng 1: Số luồng mặc định
        lbl_conc = QLabel("Số luồng song song mặc định:")
        lbl_conc.setStyleSheet("font-weight: 600; color: #1E293B;")
        grid_auto.addWidget(lbl_conc, 1, 0)

        conc_row = QHBoxLayout()
        conc_row.setSpacing(8)
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 10)
        self.spin_concurrency.setValue(self.config.default_concurrency)
        self.spin_concurrency.setFixedWidth(130)
        conc_row.addWidget(self.spin_concurrency)

        lbl_conc_hint = QLabel("(Khuyên dùng 2-4 luồng tùy theo RAM/CPU và Proxy)")
        lbl_conc_hint.setStyleSheet("font-size: 11px; color: #64748B;")
        conc_row.addWidget(lbl_conc_hint)
        conc_row.addStretch()
        grid_auto.addLayout(conc_row, 1, 1)

        # Hàng 2: Timeout
        lbl_timeout = QLabel("Thời gian chờ Playwright (Timeout):")
        lbl_timeout.setStyleSheet("font-weight: 600; color: #1E293B;")
        grid_auto.addWidget(lbl_timeout, 2, 0)

        timeout_row = QHBoxLayout()
        timeout_row.setSpacing(8)
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(10, 300)
        self.spin_timeout.setSuffix(" giây")
        self.spin_timeout.setValue(int(self.config.timeout_seconds))
        self.spin_timeout.setFixedWidth(130)
        timeout_row.addWidget(self.spin_timeout)

        lbl_timeout_hint = QLabel("(Mặc định 60 giây. Tăng lên 90s - 180s nếu mạng lag hoặc proxy chậm)")
        lbl_timeout_hint.setStyleSheet("font-size: 11px; color: #64748B;")
        timeout_row.addWidget(lbl_timeout_hint)
        timeout_row.addStretch()
        grid_auto.addLayout(timeout_row, 2, 1)

        # Hàng 3: Tùy chọn Checkbox lưu trữ
        grid_auto.addWidget(QLabel("Tùy chọn nâng cao:"), 3, 0)
        opts_box = QVBoxLayout()
        opts_box.setSpacing(8)

        self.cb_keep_raw = QCheckBox("Giữ lại toàn bộ tệp tin gốc (raw XLSX/CSV/ZIP) từ YouTube Studio")
        self.cb_keep_raw.setChecked(self.config.keep_raw_files)
        opts_box.addWidget(self.cb_keep_raw)

        self.cb_auto_reports = QCheckBox("Tự động xuất file README.md, manifest.json và quality_report.json cho AI")
        self.cb_auto_reports.setChecked(self.config.auto_generate_reports)
        opts_box.addWidget(self.cb_auto_reports)

        grid_auto.addLayout(opts_box, 3, 1)

        card_automation_layout.addLayout(grid_auto)
        content_layout.addWidget(card_automation)

        content_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # ---------------------------------------------------------------------
        # 3. Thanh nút hành động cuối trang (Footer Action Bar)
        # ---------------------------------------------------------------------
        footer_frame = QFrame()
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(0, 8, 0, 0)
        footer_layout.setSpacing(12)

        self.btn_save = QPushButton("💾 Lưu Cài Đặt")
        self.btn_save.setProperty("btnType", "primary")
        self.btn_save.setProperty("btnSize", "large")
        footer_layout.addWidget(self.btn_save)

        self.btn_reset = QPushButton("↺ Khôi phục mặc định")
        footer_layout.addWidget(self.btn_reset)

        self.lbl_save_status = QLabel("")
        self.lbl_save_status.setStyleSheet("font-weight: 600; font-size: 13px; color: #059669;")
        footer_layout.addWidget(self.lbl_save_status)

        footer_layout.addStretch()
        main_layout.addWidget(footer_frame)

    # =========================================================================
    # 2. KẾT NỐI TÍN HIỆU (SIGNALS WIRING)
    # =========================================================================

    def _wire_signals(self) -> None:
        self.btn_detect_port.clicked.connect(self.auto_detect_port)
        self.btn_ping_api.clicked.connect(self.ping_gpm_api)
        self.btn_browse_setting.clicked.connect(self._browse_setting_dat)
        self.btn_browse_db.clicked.connect(self._browse_db_path)
        self.btn_browse_runs.clicked.connect(self._browse_runs_dir)

        self.btn_save.clicked.connect(self.save_settings)
        self.btn_reset.clicked.connect(self.reset_to_defaults)

    # =========================================================================
    # 3. CÁC HÀM XỬ LÝ NGHIỆP VỤ & LƯU TRỮ
    # =========================================================================

    def load_settings(self) -> None:
        """Nạp các giá trị cài đặt lên giao diện."""
        # 1. Cổng API
        self.spin_port.setValue(self.config.api_port)

        # 2. Đường dẫn files
        setting_dat = get_default_setting_dat_path()
        self.input_setting_dat.setText(str(setting_dat) if setting_dat.exists() else "")

        db_path = self.config.db_path or get_gpm_database_path()
        self.input_db_path.setText(str(db_path) if db_path and db_path.exists() else "")

        # 3. Lưu trữ & Automation
        self.input_runs_dir.setText(str(self.config.runs_dir))
        self.spin_concurrency.setValue(self.config.default_concurrency)
        self.spin_timeout.setValue(int(self.config.timeout_seconds))
        self.cb_keep_raw.setChecked(self.config.keep_raw_files)
        self.cb_auto_reports.setChecked(self.config.auto_generate_reports)

    def save_settings(self) -> None:
        """Lưu toàn bộ cài đặt vào LocalStorage và cập nhật AppConfig."""
        # Cập nhật AppConfig
        self.config.api_port = self.spin_port.value()
        self.config.api_base_url = f"http://127.0.0.1:{self.config.api_port}"
        self.config.runs_dir = Path(self.input_runs_dir.text().strip() or "runs").resolve()
        self.config.default_concurrency = self.spin_concurrency.value()
        self.config.timeout_seconds = float(self.spin_timeout.value())
        self.config.keep_raw_files = self.cb_keep_raw.isChecked()
        self.config.auto_generate_reports = self.cb_auto_reports.isChecked()

        # Lưu vào SQLite
        self.config.save_to_storage(self.history_storage)

        # Báo thành công
        self.lbl_save_status.setText("✓ Đã lưu cài đặt hệ thống thành công!")
        logger.info("Đã lưu cấu hình cài đặt mới: %s", self.config.to_dict())

        # Phát tín hiệu ra ngoài
        self.settings_saved.emit(self.config.to_dict())

    def reset_to_defaults(self) -> None:
        """Khôi phục các giá trị cấu hình về mặc định."""
        reply = QMessageBox.question(
            self,
            "Xác nhận khôi phục",
            "Bạn có chắc chắn muốn khôi phục tất cả cài đặt về giá trị mặc định?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            default_config = AppConfig()
            self.config = default_config
            self.load_settings()
            self.save_settings()
            self.lbl_save_status.setText("↺ Đã khôi phục cài đặt về mặc định.")

    def auto_detect_port(self) -> None:
        """Tự động phát hiện cổng GPM đang mở."""
        port = read_gpm_api_port_from_setting()
        self.spin_port.setValue(port)
        self.ping_gpm_api()

    def ping_gpm_api(self) -> bool:
        """Kiểm tra kết nối trực tiếp tới cổng GPM API."""
        port = self.spin_port.value()
        client = GpmClient(port=port)
        connected = client.check_connection()

        if connected:
            self.lbl_ping_status.setText(f"🟢 Kết nối thành công tới GPM API tại cổng {client.port} (Online)")
            self.lbl_ping_status.setStyleSheet("font-weight: 600; font-size: 12px; color: #059669;")
        else:
            self.lbl_ping_status.setText(f"🔴 Không thể kết nối tới GPM API tại cổng {port} (Offline)")
            self.lbl_ping_status.setStyleSheet("font-weight: 600; font-size: 12px; color: #DC2626;")

        return connected

    def _browse_runs_dir(self) -> None:
        """Mở hộp thoại chọn thư mục lưu kết quả."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục lưu trữ kết quả (runs/)",
            self.input_runs_dir.text(),
        )
        if folder:
            self.input_runs_dir.setText(folder)

    def _browse_setting_dat(self) -> None:
        """Mở hộp thoại chọn file setting.dat."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file cấu hình setting.dat của GPM",
            self.input_setting_dat.text(),
            "Data files (*.dat);;All files (*.*)",
        )
        if filepath:
            self.input_setting_dat.setText(filepath)

    def _browse_db_path(self) -> None:
        """Mở hộp thoại chọn file database.db."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file database.db của GPM",
            self.input_db_path.text(),
            "Database files (*.db *.sqlite);;All files (*.*)",
        )
        if filepath:
            self.input_db_path.setText(filepath)
