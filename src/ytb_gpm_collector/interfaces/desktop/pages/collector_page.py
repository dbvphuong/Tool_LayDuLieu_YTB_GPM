"""Collector Page view (Tab 1: Thu thập dữ liệu).

Triển khai hoàn chỉnh Task 4.2:
- Khối 1: Bảng chọn Profile GPM (checkbox từng cái / chọn tất cả, kèm proxy, tìm kiếm, số luồng 1-10, nút làm mới).
- Khối 2: Cấu hình dữ liệu cần lấy (chọn video theo số lượng gần nhất, khoảng ngày đăng, hoặc toàn bộ; khung thời gian phân tích số liệu 28 ngày, 90 ngày, lifetime, tùy chỉnh).
- Khối 3: Điều khiển & Tiến trình thu thập (Nút to [ BẮT ĐẦU THU THẬP ], nút Dừng lại, Mở thư mục kết quả, Thanh tiến trình tổng % và bảng trạng thái luồng trực tiếp).
- Tích hợp lưu/khôi phục trạng thái phiên qua HistoryStorage và nạp profile mượt mà từ GpmClient.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Any

from PySide6.QtCore import Qt, QDate, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QListView,
    QRadioButton,
    QButtonGroup,
    QDateEdit,
    QProgressBar,
    QMessageBox,
)

from ytb_gpm_collector.domain.models import GpmProfile, GpmGroup, AppSessionState, ChannelCache
from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.integrations.storage.history import LocalStorage, HistoryStorage
from ytb_gpm_collector.interfaces.desktop.theme import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    COLOR_BG_CARD_ALT,
    COLOR_BORDER_LIGHT,
)

logger = logging.getLogger(__name__)


class ProfileLoaderThread(QThread):
    """Worker Thread tải danh sách profile và nhóm từ GPM không gây đơ giao diện."""
    loaded = Signal(list, list)  # (profiles, groups)
    error = Signal(str)

    def __init__(self, gpm_client: GpmClient, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.gpm_client = gpm_client

    def run(self) -> None:
        try:
            groups = []
            if hasattr(self.gpm_client, "get_groups"):
                try:
                    res = self.gpm_client.get_groups()
                    if isinstance(res, list):
                        groups = res
                except Exception as g_ex:
                    logger.debug("Không thể nạp nhóm GPM: %s", g_ex)
            profiles = self.gpm_client.get_profiles()
            self.loaded.emit(profiles, groups)
        except Exception as ex:
            logger.warning("Lỗi nạp profile GPM: %s", ex)
            self.error.emit(str(ex))


class CollectorPage(QWidget):
    """Màn hình chính Thu thập dữ liệu (Tab 1)."""

    # Signals phát ra cho bộ điều phối Worker Thread Pool (Task 4.6)
    start_requested = Signal(dict)
    stop_requested = Signal()
    profiles_reloaded = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        gpm_client: Optional[GpmClient] = None,
        history_storage: Optional[HistoryStorage] = None,
        auto_load: bool = False,
    ):
        super().__init__(parent)
        self.setProperty("class", "page-container")

        self.gpm_client = gpm_client or GpmClient()
        self.history_storage = history_storage or HistoryStorage()

        # Dữ liệu nội bộ
        self._profiles: List[GpmProfile] = []
        self._groups: List[GpmGroup] = []
        self._groups_dict: Dict[str, str] = {}
        self._channel_caches: Dict[str, ChannelCache] = {}
        self._selected_ids: Set[str] = set()
        self._selected_group_id_saved: Optional[str] = None
        self._is_updating_table = False
        self._is_updating_combos = False
        self._is_running = False
        self._loader_thread: Optional[ProfileLoaderThread] = None

        self._init_ui()
        self._wire_internal_signals()

        # Tải cấu hình phiên trước và nạp danh sách profile nếu bật auto_load
        self.load_session_state()
        if auto_load:
            self.reload_profiles(async_mode=True)

    # =========================================================================
    # 1. KHỞI TẠO GIAO DIỆN CHÍNH (UI INITIALIZATION)
    # =========================================================================

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Title (gọn gàng, không subtitle để tiết kiệm chiều cao)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(0)

        title = QLabel("Thu thập dữ liệu YouTube Studio")
        title.setProperty("class", "page-title")
        header_layout.addWidget(title)

        main_layout.addLayout(header_layout)

        # Scroll area cho nội dung các khối chức năng
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

        # Khối 1: Điều khiển & Tiến trình Thu thập (ĐƯA LÊN ĐẦU TIÊN)
        self._build_block3_execution(content_layout)

        # Khối 2: Cấu hình Dữ liệu Cần Lấy (TINH GỌN 1-2 DÒNG)
        self._build_block2_data_config(content_layout)

        # Khối 3: Bảng chọn Profile GPM (TRỌNG TÂM - KÉO DÀI 400PX+)
        self._build_block1_profiles(content_layout)

        # Khối 4: Trạng thái chi tiết các luồng worker (Có thể thu gọn/mở rộng)
        self._build_block4_workers(content_layout)

        content_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # =========================================================================
    # 2. KHỐI 1 (MỚI): ĐIỀU KHIỂN & TIẾN TRÌNH THU THẬP (CARD_EXECUTION)
    # =========================================================================

    def _build_block3_execution(self, parent_layout: QVBoxLayout) -> None:
        self.card_execution = QFrame()
        self.card_execution.setProperty("class", "card")
        layout = QVBoxLayout(self.card_execution)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Tiêu đề khối & Trạng thái tổng
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        lbl_title = QLabel("1. ĐIỀU KHIỂN & TIẾN TRÌNH THU THẬP")
        lbl_title.setProperty("class", "card-title")
        header_row.addWidget(lbl_title)

        header_row.addStretch()

        self.lbl_overall_status = QLabel("Trạng thái: Sẵn sàng.")
        self.lbl_overall_status.setStyleSheet(
            "font-weight: 600; color: #1E293B; background-color: #F8FAFC; "
            "padding: 4px 12px; border-radius: 6px; border: 1px solid #E2E8F0;"
        )
        header_row.addWidget(self.lbl_overall_status)
        layout.addLayout(header_row)

        # Hàng nút điều khiển & Số luồng
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        # Nút BẮT ĐẦU: Solid Royal Blue nổi bật
        self.btn_start = QPushButton("▶  BẮT ĐẦU THU THẬP")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setProperty("btnType", "primary")
        self.btn_start.setProperty("btnSize", "large")
        self.btn_start.setMinimumHeight(42)
        self.btn_start.setStyleSheet(
            "QPushButton#btnStart {"
            "  background-color: #2563EB;"
            "  color: #FFFFFF;"
            "  font-weight: 700;"
            "  font-size: 13px;"
            "  border-radius: 6px;"
            "  padding: 8px 22px;"
            "  border: 1px solid #1D4ED8;"
            "}"
            "QPushButton#btnStart:hover {"
            "  background-color: #1D4ED8;"
            "  border-color: #1E40AF;"
            "}"
            "QPushButton#btnStart:pressed {"
            "  background-color: #1E40AF;"
            "}"
            "QPushButton#btnStart:disabled {"
            "  background-color: #93C5FD;"
            "  color: #EFF6FF;"
            "  border-color: #93C5FD;"
            "}"
        )
        self.btn_start.setToolTip("Khởi động tiến trình cào dữ liệu cho các profile đã chọn")
        action_row.addWidget(self.btn_start)

        # Nút DỪNG LẠI: Danger Red
        self.btn_stop = QPushButton("⏹  DỪNG LẠI")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setProperty("btnType", "danger")
        self.btn_stop.setMinimumHeight(42)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(
            "QPushButton#btnStop {"
            "  background-color: #DC2626;"
            "  color: #FFFFFF;"
            "  font-weight: 600;"
            "  font-size: 13px;"
            "  border-radius: 6px;"
            "  padding: 8px 18px;"
            "  border: 1px solid #B91C1C;"
            "}"
            "QPushButton#btnStop:hover {"
            "  background-color: #B91C1C;"
            "}"
            "QPushButton#btnStop:disabled {"
            "  background-color: #FCA5A5;"
            "  color: #FEF2F2;"
            "  border-color: #FCA5A5;"
            "}"
        )
        self.btn_stop.setToolTip("Dừng an toàn các luồng đang chạy")
        action_row.addWidget(self.btn_stop)

        # Nút MỞ THƯ MỤC KẾT QUẢ
        self.btn_open_runs = QPushButton("📁  Mở thư mục kết quả (runs/)")
        self.btn_open_runs.setObjectName("btnOpenRuns")
        self.btn_open_runs.setMinimumHeight(42)
        self.btn_open_runs.setStyleSheet(
            "QPushButton#btnOpenRuns {"
            "  background-color: #FFFFFF;"
            "  color: #1E293B;"
            "  font-weight: 500;"
            "  font-size: 13px;"
            "  border-radius: 6px;"
            "  padding: 8px 16px;"
            "  border: 1px solid #CBD5E1;"
            "}"
            "QPushButton#btnOpenRuns:hover {"
            "  background-color: #F8FAFC;"
            "  border-color: #94A3B8;"
            "}"
        )
        self.btn_open_runs.setToolTip("Mở thư mục chứa toàn bộ dữ liệu CSV, JSONL và báo cáo vừa cào")
        action_row.addWidget(self.btn_open_runs)

        # Vách ngăn đứng nhỏ
        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.VLine)
        v_sep.setStyleSheet("color: #E2E8F0; margin: 0 4px;")
        action_row.addWidget(v_sep)

        # Cấu hình số luồng song song
        concurrency_box = QHBoxLayout()
        concurrency_box.setSpacing(6)
        lbl_threads = QLabel("Số luồng:")
        lbl_threads.setStyleSheet("font-weight: 600; color: #334155;")
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 10)
        self.concurrency_spin.setValue(2)
        self.concurrency_spin.setFixedWidth(65)
        self.concurrency_spin.setToolTip("Số lượng Profile GPM chạy tự động đồng thời (1 - 10 luồng)")
        concurrency_box.addWidget(lbl_threads)
        concurrency_box.addWidget(self.concurrency_spin)
        action_row.addLayout(concurrency_box)

        action_row.addStretch()
        layout.addLayout(action_row)

        # Thanh tiến trình tổng
        progress_box = QVBoxLayout()
        progress_box.setSpacing(6)

        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setTextVisible(True)
        self.overall_progress_bar.setFormat("%p% (%v/%m)")
        self.overall_progress_bar.setFixedHeight(16)
        self.overall_progress_bar.setStyleSheet(
            "QProgressBar {"
            "  background-color: #E2E8F0;"
            "  border-radius: 8px;"
            "  text-align: center;"
            "  color: #0F172A;"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "}"
            "QProgressBar::chunk {"
            "  background-color: #2563EB;"
            "  border-radius: 8px;"
            "}"
        )
        progress_box.addWidget(self.overall_progress_bar)

        # Hàng badges thống kê trực quan & nhãn tiến độ
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)

        badge_style_base = "border-radius: 5px; padding: 3px 10px; font-weight: 600; font-size: 11px;"

        self.badge_completed = QLabel("✓ Hoàn thành: 0")
        self.badge_completed.setStyleSheet(
            f"{badge_style_base} background-color: #ECFDF5; color: #059669; border: 1px solid #A7F3D0;"
        )
        stats_row.addWidget(self.badge_completed)

        self.badge_running = QLabel("⚡ Đang chạy: 0")
        self.badge_running.setStyleSheet(
            f"{badge_style_base} background-color: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE;"
        )
        stats_row.addWidget(self.badge_running)

        self.badge_pending = QLabel("⏳ Chờ xử lý: 0")
        self.badge_pending.setStyleSheet(
            f"{badge_style_base} background-color: #F8FAFC; color: #64748B; border: 1px solid #CBD5E1;"
        )
        stats_row.addWidget(self.badge_pending)

        self.badge_failed = QLabel("❌ Lỗi: 0")
        self.badge_failed.setStyleSheet(
            f"{badge_style_base} background-color: #FEF2F2; color: #DC2626; border: 1px solid #FECACA;"
        )
        stats_row.addWidget(self.badge_failed)

        stats_row.addSpacing(10)

        # Nhãn text chi tiết (được test suite kiểm tra)
        self.lbl_progress_detail = QLabel("Tiến độ: 0/0 profile hoàn thành | Đang xử lý: 0 | Còn lại: 0")
        self.lbl_progress_detail.setProperty("class", "card-subtitle")
        self.lbl_progress_detail.setStyleSheet("color: #64748B; font-size: 12px;")
        stats_row.addWidget(self.lbl_progress_detail)

        stats_row.addStretch()
        progress_box.addLayout(stats_row)

        layout.addLayout(progress_box)
        parent_layout.addWidget(self.card_execution)

    # =========================================================================
    # 3. KHỐI 2 (MỚI): CẤU HÌNH DỮ LIỆU TINH GỌN (CARD_CONFIG)
    # =========================================================================

    def _build_block2_data_config(self, parent_layout: QVBoxLayout) -> None:
        self.card_config = QFrame()
        self.card_config.setProperty("class", "card")
        layout = QVBoxLayout(self.card_config)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        # Header gọn gàng
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        lbl_title = QLabel("2. CẤU HÌNH THU THẬP DỮ LIỆU")
        lbl_title.setProperty("class", "card-title")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #1E293B;")
        header_row.addWidget(lbl_title)

        lbl_desc = QLabel("(Phạm vi video, thời gian Analytics và mức độ chi tiết)")
        lbl_desc.setStyleSheet("color: #64748B; font-size: 12px;")
        header_row.addWidget(lbl_desc)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Dòng 1: Lọc video cần cào (nằm ngang)
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        lbl_vscope = QLabel("🎯 Video:")
        lbl_vscope.setStyleSheet("font-weight: 600; color: #334155; min-width: 60px;")
        row1.addWidget(lbl_vscope)

        self.video_scope_group = QButtonGroup(self)

        # Radio 1: Số lượng video mới nhất
        self.radio_recent = QRadioButton("Mới nhất:")
        self.radio_recent.setChecked(True)
        self.video_scope_group.addButton(self.radio_recent, 1)
        row1.addWidget(self.radio_recent)

        self.spin_video_limit = QSpinBox()
        self.spin_video_limit.setRange(1, 500)
        self.spin_video_limit.setValue(10)
        self.spin_video_limit.setFixedWidth(65)
        row1.addWidget(self.spin_video_limit)

        lbl_vunit = QLabel("video")
        lbl_vunit.setStyleSheet("color: #64748B; margin-right: 8px;")
        row1.addWidget(lbl_vunit)

        # Radio 2: Theo ngày đăng
        self.radio_date_range = QRadioButton("Theo ngày đăng:")
        self.video_scope_group.addButton(self.radio_date_range, 2)
        row1.addWidget(self.radio_date_range)

        self.combo_video_date = QComboBox()
        self.combo_video_date.setView(QListView())
        self.combo_video_date.addItem("7 ngày qua (7_days)", "7_days")
        self.combo_video_date.addItem("28 ngày qua (28_days)", "28_days")
        self.combo_video_date.addItem("90 ngày qua (90_days)", "90_days")
        self.combo_video_date.addItem("365 ngày qua (365_days)", "365_days")
        self.combo_video_date.addItem("Tùy chỉnh khoảng ngày...", "custom")
        self.combo_video_date.setCurrentIndex(1)
        self.combo_video_date.setEnabled(False)
        self.combo_video_date.setMinimumWidth(160)
        row1.addWidget(self.combo_video_date)

        # Radio 3: Toàn bộ video
        self.radio_all_videos = QRadioButton("Toàn bộ video")
        self.video_scope_group.addButton(self.radio_all_videos, 3)
        row1.addWidget(self.radio_all_videos)

        row1.addStretch()
        layout.addLayout(row1)

        # Dòng 2: Analytics & Mức độ thu thập (nằm ngang)
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        # Khung thời gian Analytics
        lbl_analytics = QLabel("📅 Analytics:")
        lbl_analytics.setStyleSheet("font-weight: 600; color: #334155; min-width: 60px;")
        row2.addWidget(lbl_analytics)

        self.combo_analytics_period = QComboBox()
        self.combo_analytics_period.setView(QListView())
        self.combo_analytics_period.addItem("28 ngày qua (28_days - Mặc định)", "28_days")
        self.combo_analytics_period.addItem("7 ngày qua (7_days)", "7_days")
        self.combo_analytics_period.addItem("90 ngày qua (90_days)", "90_days")
        self.combo_analytics_period.addItem("365 ngày qua (365_days)", "365_days")
        self.combo_analytics_period.addItem("Năm hiện tại (current_year)", "current_year")
        self.combo_analytics_period.addItem("Toàn thời gian (lifetime)", "lifetime")
        self.combo_analytics_period.addItem("Tùy chỉnh ngày phân tích...", "custom")
        self.combo_analytics_period.setMinimumWidth(210)
        row2.addWidget(self.combo_analytics_period)

        row2.addSpacing(12)

        # Mức độ thu thập
        lbl_depth = QLabel("⚙ Mức độ:")
        lbl_depth.setStyleSheet("font-weight: 600; color: #334155;")
        row2.addWidget(lbl_depth)

        self.depth_group = QButtonGroup(self)

        self.radio_depth_std = QRadioButton("Tiêu chuẩn (Video + Nguồn traffic)")
        self.radio_depth_std.setChecked(True)
        self.depth_group.addButton(self.radio_depth_std, 1)
        row2.addWidget(self.radio_depth_std)

        self.radio_depth_fast = QRadioButton("Nhanh")
        self.depth_group.addButton(self.radio_depth_fast, 2)
        row2.addWidget(self.radio_depth_fast)

        self.radio_depth_full = QRadioButton("Chuyên sâu (+ Evidence ảnh)")
        self.depth_group.addButton(self.radio_depth_full, 3)
        row2.addWidget(self.radio_depth_full)

        row2.addStretch()
        layout.addLayout(row2)

        # Dòng 3 (Ẩn theo mặc định, chỉ hiện khi chọn Custom date):
        # Widget chọn ngày tùy chỉnh cho video
        self.widget_custom_video_dates = QWidget()
        custom_vdate_layout = QHBoxLayout(self.widget_custom_video_dates)
        custom_vdate_layout.setContentsMargins(0, 4, 0, 0)
        custom_vdate_layout.setSpacing(6)
        lbl_vdate_note = QLabel("📅 Ngày đăng video:")
        lbl_vdate_note.setStyleSheet("font-weight: 600; color: #475569;")
        lbl_from = QLabel("Từ:")
        self.date_video_from = QDateEdit()
        self.date_video_from.setCalendarPopup(True)
        self.date_video_from.setDate(QDate.currentDate().addDays(-30))
        lbl_to = QLabel("Đến:")
        self.date_video_to = QDateEdit()
        self.date_video_to.setCalendarPopup(True)
        self.date_video_to.setDate(QDate.currentDate())
        custom_vdate_layout.addWidget(lbl_vdate_note)
        custom_vdate_layout.addWidget(lbl_from)
        custom_vdate_layout.addWidget(self.date_video_from)
        custom_vdate_layout.addWidget(lbl_to)
        custom_vdate_layout.addWidget(self.date_video_to)
        custom_vdate_layout.addStretch()
        self.widget_custom_video_dates.setVisible(False)
        layout.addWidget(self.widget_custom_video_dates)

        # Widget ngày tùy chỉnh cho Analytics
        self.widget_custom_analytics_dates = QWidget()
        custom_adate_layout = QHBoxLayout(self.widget_custom_analytics_dates)
        custom_adate_layout.setContentsMargins(0, 4, 0, 0)
        custom_adate_layout.setSpacing(6)
        lbl_adate_note = QLabel("📅 Khoảng ngày Analytics:")
        lbl_adate_note.setStyleSheet("font-weight: 600; color: #475569;")
        lbl_afrom = QLabel("Từ:")
        self.date_analytics_from = QDateEdit()
        self.date_analytics_from.setCalendarPopup(True)
        self.date_analytics_from.setDate(QDate.currentDate().addDays(-28))
        lbl_ato = QLabel("Đến:")
        self.date_analytics_to = QDateEdit()
        self.date_analytics_to.setCalendarPopup(True)
        self.date_analytics_to.setDate(QDate.currentDate())
        custom_adate_layout.addWidget(lbl_adate_note)
        custom_adate_layout.addWidget(lbl_afrom)
        custom_adate_layout.addWidget(self.date_analytics_from)
        custom_adate_layout.addWidget(lbl_ato)
        custom_adate_layout.addWidget(self.date_analytics_to)
        custom_adate_layout.addStretch()
        self.widget_custom_analytics_dates.setVisible(False)
        layout.addWidget(self.widget_custom_analytics_dates)

        parent_layout.addWidget(self.card_config)

    # =========================================================================
    # 4. KHỐI 3 (MỚI): CHỌN PROFILE GPM (KÉO DÀI BẢNG PROFILE)
    # =========================================================================

    def _build_block1_profiles(self, parent_layout: QVBoxLayout) -> None:
        self.card_profile = QFrame()
        self.card_profile.setProperty("class", "card")
        layout = QVBoxLayout(self.card_profile)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Tiêu đề khối
        header_row = QHBoxLayout()
        lbl_title = QLabel("3. DANH SÁCH PROFILE GPM")
        lbl_title.setProperty("class", "card-title")
        header_row.addWidget(lbl_title)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Thanh công cụ: Chọn nhóm GPM, Tìm kiếm, Chọn tất cả, Bỏ chọn, Làm mới, Thống kê
        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(8)

        # Dropdown Lọc theo Nhóm GPM (như trên giao diện GPM)
        lbl_group = QLabel("Nhóm:")
        lbl_group.setStyleSheet("font-weight: 600; color: #334155; margin-left: 2px;")
        toolbar_row.addWidget(lbl_group)

        self.combo_group_filter = QComboBox()
        self.combo_group_filter.setView(QListView())
        self.combo_group_filter.setMinimumWidth(180)
        self.combo_group_filter.setToolTip("Lọc profile theo Nhóm trên GPM (như giao diện GPMLogin)")
        self.combo_group_filter.addItem("📁 Tất cả nhóm", "")
        toolbar_row.addWidget(self.combo_group_filter)

        # Ô tìm kiếm profile
        self.search_profile_input = QLineEdit()
        self.search_profile_input.setPlaceholderText("🔍 Tìm theo tên profile, ID, proxy, ghi chú...")
        self.search_profile_input.setClearButtonEnabled(True)
        self.search_profile_input.setMinimumWidth(240)
        toolbar_row.addWidget(self.search_profile_input)

        # Nút chọn tất cả & bỏ chọn
        self.btn_select_all = QPushButton("✓ Chọn tất cả")
        self.btn_select_all.setToolTip("Chọn tất cả profile đang hiển thị (trong nhóm đã lọc)")
        toolbar_row.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("✗ Bỏ chọn")
        self.btn_deselect_all.setToolTip("Bỏ chọn các profile đang hiển thị")
        toolbar_row.addWidget(self.btn_deselect_all)

        # Nút làm mới danh sách
        self.btn_refresh_profiles = QPushButton("🔄 Làm mới")
        self.btn_refresh_profiles.setToolTip("Tải lại danh sách Profile và Nhóm từ GPMLogin API hoặc Database")
        toolbar_row.addWidget(self.btn_refresh_profiles)

        toolbar_row.addStretch()

        # Nhãn đếm số lượng profile đã chọn
        self.lbl_selected_count = QLabel("Đã chọn: 0 / 0 profile")
        self.lbl_selected_count.setStyleSheet(
            f"background-color: {COLOR_BG_CARD_ALT}; color: {COLOR_PRIMARY}; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px 12px; font-weight: 600;"
        )
        toolbar_row.addWidget(self.lbl_selected_count)

        layout.addLayout(toolbar_row)

        # Bảng danh sách Profile GPM (Mở rộng chiều cao tối thiểu lên 400px, cho phép co giãn)
        self.profile_table = QTableWidget()
        self.profile_table.setColumnCount(7)
        self.profile_table.setHorizontalHeaderLabels([
            "",  # Checkbox
            "Tên Profile",
            "Nhóm",
            "Ghi chú",
            "Proxy / IP",
            "Kênh YouTube đã lưu",
            "Trạng thái GPM",
        ])
        self.profile_table.setAlternatingRowColors(True)
        self.profile_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.profile_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.profile_table.verticalHeader().setVisible(False)
        self.profile_table.setMinimumHeight(400)
        self.profile_table.setTextElideMode(Qt.ElideRight)

        # Cấu hình độ rộng các cột
        header = self.profile_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_profile_header_clicked)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.profile_table.setColumnWidth(0, 42)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.profile_table.setColumnWidth(1, 180)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.profile_table.setColumnWidth(2, 140)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.profile_table.setColumnWidth(3, 220)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        self.profile_table.setColumnWidth(4, 160)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        self.profile_table.setColumnWidth(5, 170)
        header.setSectionResizeMode(6, QHeaderView.Interactive)
        self.profile_table.setColumnWidth(6, 110)

        layout.addWidget(self.profile_table, 1)

        # Trạng thái tải profile
        self.lbl_profile_status = QLabel("Chưa tải danh sách profile. Nhấn 'Làm mới danh sách' để nạp.")
        self.lbl_profile_status.setProperty("class", "card-subtitle")
        layout.addWidget(self.lbl_profile_status)

        parent_layout.addWidget(self.card_profile, 1)

    # =========================================================================
    # 5. KHỐI 4 (MỚI): THEO DÕI LIVE WORKER SLOTS (CÓ THỂ ĐÓNG/MỞ)
    # =========================================================================

    def _build_block4_workers(self, parent_layout: QVBoxLayout) -> None:
        self.card_workers = QFrame()
        self.card_workers.setProperty("class", "card")
        layout = QVBoxLayout(self.card_workers)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        # Header với nút Toggle thu gọn / mở rộng
        w_header_row = QHBoxLayout()
        lbl_worker_title = QLabel("4. THEO DÕI CÁC LUỒNG ĐANG CHẠY (LIVE WORKER SLOTS)")
        lbl_worker_title.setProperty("class", "card-title")
        lbl_worker_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #1E293B;")
        w_header_row.addWidget(lbl_worker_title)

        w_header_row.addStretch()

        self.btn_toggle_workers = QPushButton("▾ Thu gọn theo dõi")
        self.btn_toggle_workers.setStyleSheet(
            "QPushButton {"
            "  background-color: #F1F5F9;"
            "  color: #475569;"
            "  border: 1px solid #CBD5E1;"
            "  border-radius: 4px;"
            "  padding: 3px 10px;"
            "  font-size: 11px;"
            "  font-weight: 500;"
            "}"
            "QPushButton:hover {"
            "  background-color: #E2E8F0;"
            "}"
        )
        self.btn_toggle_workers.clicked.connect(self._toggle_worker_table)
        w_header_row.addWidget(self.btn_toggle_workers)

        layout.addLayout(w_header_row)

        self.worker_table = QTableWidget()
        self.worker_table.setColumnCount(6)
        self.worker_table.setHorizontalHeaderLabels([
            "Luồng #",
            "Profile GPM",
            "Kênh YouTube",
            "Bước thực hiện",
            "Trạng thái",
            "Thời gian",
        ])
        self.worker_table.setAlternatingRowColors(True)
        self.worker_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.worker_table.verticalHeader().setVisible(False)
        self.worker_table.setMinimumHeight(130)

        # Cấu hình độ rộng các cột bảng worker
        w_header = self.worker_table.horizontalHeader()
        w_header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.worker_table.setColumnWidth(0, 85)
        w_header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.worker_table.setColumnWidth(1, 160)
        w_header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.worker_table.setColumnWidth(2, 170)
        w_header.setSectionResizeMode(3, QHeaderView.Stretch)
        w_header.setSectionResizeMode(4, QHeaderView.Interactive)
        self.worker_table.setColumnWidth(4, 120)
        w_header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.worker_table.setColumnWidth(5, 90)

        layout.addWidget(self.worker_table)
        parent_layout.addWidget(self.card_workers)

        # Khởi tạo các hàng hiển thị luồng mặc định
        self.reset_worker_table()

    def _toggle_worker_table(self) -> None:
        """Đóng / mở hiển thị bảng Live Worker Slots."""
        is_vis = self.worker_table.isVisible()
        self.worker_table.setVisible(not is_vis)
        self.btn_toggle_workers.setText("▾ Thu gọn theo dõi" if not is_vis else "▸ Mở rộng theo dõi")

    def _on_profile_header_clicked(self, logical_index: int) -> None:
        """Nhấn vào tiêu đề Cột 0 (Checkbox) để Chọn tất cả / Bỏ chọn tất cả."""
        if logical_index == 0:
            visible_rows = [r for r in range(self.profile_table.rowCount()) if not self.profile_table.isRowHidden(r)]
            if not visible_rows:
                return
            all_selected = all(
                self.profile_table.item(r, 0) and self.profile_table.item(r, 0).checkState() == Qt.Checked
                for r in visible_rows
            )
            if all_selected:
                self.deselect_all_profiles()
            else:
                self.select_all_profiles()

    def _update_stat_badges(self, completed: int = 0, running: int = 0, pending: int = 0, failed: int = 0) -> None:
        """Cập nhật nội dung các thẻ mini badge trực quan."""
        if hasattr(self, "badge_completed"):
            self.badge_completed.setText(f"✓ Hoàn thành: {completed}")
        if hasattr(self, "badge_running"):
            self.badge_running.setText(f"⚡ Đang chạy: {running}")
        if hasattr(self, "badge_pending"):
            self.badge_pending.setText(f"⏳ Chờ xử lý: {pending}")
        if hasattr(self, "badge_failed"):
            self.badge_failed.setText(f"❌ Lỗi: {failed}")

    def _refresh_stat_badges_from_table(self) -> None:
        """Đếm trạng thái hiện tại từ bảng worker để cập nhật badges."""
        if not hasattr(self, "badge_completed"):
            return
        running = 0
        failed = 0
        completed = self.overall_progress_bar.value()
        total = self.overall_progress_bar.maximum()
        for r in range(self.worker_table.rowCount()):
            st_item = self.worker_table.item(r, 4)
            st = st_item.text().lower() if st_item else ""
            if "lỗi" in st or "fail" in st:
                failed += 1
            elif "đang" in st or "running" in st:
                running += 1
        pending = max(0, total - completed - running - failed)
        self._update_stat_badges(completed=completed, running=running, pending=pending, failed=failed)

    # =========================================================================
    # 5. KẾT NỐI TÍN HIỆU NỘI BỘ (WIRING SIGNALS)
    # =========================================================================

    def _wire_internal_signals(self) -> None:
        # Bảng profile: tìm kiếm, chọn nhóm, chọn tất cả, bỏ chọn, làm mới
        self.combo_group_filter.currentIndexChanged.connect(self._on_group_filter_changed)
        self.search_profile_input.textChanged.connect(self._filter_profile_rows)
        self.btn_select_all.clicked.connect(self.select_all_profiles)
        self.btn_deselect_all.clicked.connect(self.deselect_all_profiles)
        self.btn_refresh_profiles.clicked.connect(self.reload_profiles)
        self.profile_table.itemChanged.connect(self._on_table_item_changed)
        self.profile_table.cellClicked.connect(self._on_cell_clicked)

        # Thay đổi số luồng
        self.concurrency_spin.valueChanged.connect(self._on_concurrency_changed)

        # Radio chọn video
        self.video_scope_group.idToggled.connect(self._on_video_scope_toggled)
        self.combo_video_date.currentIndexChanged.connect(self._on_video_date_combo_changed)

        # Khung thời gian Analytics
        self.combo_analytics_period.currentIndexChanged.connect(self._on_analytics_period_changed)

        # Nút điều khiển
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        self.btn_open_runs.clicked.connect(self._on_open_runs_clicked)

    # =========================================================================
    # 6. LOGIC NẠP PROFILE VÀ BẢNG PROFILE GPM
    # =========================================================================

    def reload_profiles(self, async_mode: bool = True) -> None:
        """Tải lại danh sách profile và nhóm từ GPM.
        - async_mode=True: chạy qua Worker Thread không gây đơ giao diện.
        - async_mode=False: chạy đồng bộ (thích hợp cho unit tests).
        """
        self.lbl_profile_status.setText("⏳ Đang tải danh sách profile và nhóm từ GPM...")
        self.btn_refresh_profiles.setEnabled(False)

        # Tải cache kênh trước từ SQLite
        try:
            self._channel_caches = self.history_storage.get_all_channel_caches()
        except Exception as ex:
            logger.warning("Không thể đọc channel cache: %s", ex)
            self._channel_caches = {}

        if not async_mode:
            try:
                groups = []
                if hasattr(self.gpm_client, "get_groups"):
                    try:
                        res = self.gpm_client.get_groups()
                        if isinstance(res, list):
                            groups = res
                    except Exception as g_ex:
                        logger.debug("Không thể lấy nhóm GPM: %s", g_ex)
                profiles = self.gpm_client.get_profiles()
                self._on_profiles_loaded(profiles, groups)
            except Exception as ex:
                self._on_profiles_load_error(str(ex))
            return

        # Dọn dẹp thread cũ nếu đang chạy
        self.cleanup()

        # Chạy thread nạp
        self._loader_thread = ProfileLoaderThread(self.gpm_client, self)
        self._loader_thread.loaded.connect(self._on_profiles_loaded)
        self._loader_thread.error.connect(self._on_profiles_load_error)
        self._loader_thread.start()

    def cleanup(self) -> None:
        """Dọn dẹp an toàn các thread nền khi đóng widget."""
        if hasattr(self, "_loader_thread") and self._loader_thread is not None:
            if self._loader_thread.isRunning():
                self._loader_thread.quit()
                self._loader_thread.wait(1500)
            self._loader_thread = None

    def closeEvent(self, event) -> None:
        self.cleanup()
        super().closeEvent(event)

    @Slot(list, list)
    def _on_profiles_loaded(self, profiles: List[GpmProfile], groups: Optional[List[Any]] = None) -> None:
        self.btn_refresh_profiles.setEnabled(True)
        self._profiles = profiles or []

        # Xử lý danh sách nhóm
        raw_groups = groups or []
        parsed_groups: List[GpmGroup] = []
        for g in raw_groups:
            if isinstance(g, GpmGroup):
                parsed_groups.append(g)
            elif isinstance(g, dict):
                try:
                    parsed_groups.append(GpmGroup(**g))
                except Exception:
                    pass
        self._groups = parsed_groups
        self._groups_dict = {g.id: g.name for g in self._groups}

        # Gán group_name cho profile nếu chưa có
        for p in self._profiles:
            if not p.group_name and p.group_id and p.group_id in self._groups_dict:
                p.group_name = self._groups_dict[p.group_id]

        # Nạp các lựa chọn vào combobox nhóm
        self._populate_group_combobox()

        group_count = len(self._groups)
        if group_count > 0:
            self.lbl_profile_status.setText(f"✓ Đã tìm thấy {len(self._profiles)} Profile GPM trong {group_count} nhóm.")
        else:
            self.lbl_profile_status.setText(f"✓ Đã tìm thấy {len(self._profiles)} Profile GPM.")

        self._populate_profile_table()
        self.profiles_reloaded.emit(len(self._profiles))

    def _populate_group_combobox(self) -> None:
        """Cập nhật dropdown nhóm GPM kèm số lượng profile của từng nhóm."""
        self._is_updating_combos = True
        prev_group_id = self.combo_group_filter.currentData() or self._selected_group_id_saved or ""
        self.combo_group_filter.clear()

        total = len(self._profiles)
        self.combo_group_filter.addItem(f"📁 Tất cả nhóm ({total})", "")

        for g in self._groups:
            cnt = sum(1 for p in self._profiles if p.group_id == g.id)
            self.combo_group_filter.addItem(f"📁 {g.name} ({cnt})", g.id)

        # Nếu có profile chưa phân nhóm
        ungrouped_cnt = sum(1 for p in self._profiles if not p.group_id or p.group_id not in self._groups_dict)
        if ungrouped_cnt > 0 and len(self._groups) > 0:
            self.combo_group_filter.addItem(f"📁 Chưa phân nhóm ({ungrouped_cnt})", "UNGROUPED")

        # Khôi phục lựa chọn trước đó nếu hợp lệ
        if prev_group_id:
            idx = self.combo_group_filter.findData(prev_group_id)
            if idx >= 0:
                self.combo_group_filter.setCurrentIndex(idx)
            else:
                self.combo_group_filter.setCurrentIndex(0)
        else:
            self.combo_group_filter.setCurrentIndex(0)

        self._is_updating_combos = False

    def _on_group_filter_changed(self, index: int) -> None:
        """Khi người dùng chọn nhóm khác trong combobox."""
        if self._is_updating_combos:
            return
        self._filter_profile_rows()
        self.save_session_state()

    @Slot(str)
    def _on_profiles_load_error(self, err_msg: str) -> None:
        self.btn_refresh_profiles.setEnabled(True)
        self.lbl_profile_status.setText(f"⚠️ Chưa kết nối được GPM API/Database ({err_msg}). Vui lòng mở GPMLogin.")
        self._populate_profile_table()
        self.profiles_reloaded.emit(0)

    def _populate_profile_table(self) -> None:
        """Điền dữ liệu profile vào bảng QTableWidget (7 cột)."""
        self._is_updating_table = True
        self.profile_table.setRowCount(0)
        self.profile_table.setRowCount(len(self._profiles))

        for row_idx, profile in enumerate(self._profiles):
            # Cột 0: Checkbox
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            is_checked = profile.id in self._selected_ids
            check_item.setCheckState(Qt.Checked if is_checked else Qt.Unchecked)
            check_item.setData(Qt.UserRole, profile.id)
            self.profile_table.setItem(row_idx, 0, check_item)

            # Cột 1: Tên Profile
            raw_note = (profile.note or "").strip()
            formatted_tooltip_note = (
                raw_note.replace("<br>", "\n")
                .replace("<br/>", "\n")
                .replace("<br />", "\n")
            )
            name_item = QTableWidgetItem(profile.name or "Unnamed")
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_tooltip = f"Profile ID: {profile.id}"
            if formatted_tooltip_note:
                name_tooltip += f"\n\nGhi chú: {formatted_tooltip_note}"
            name_item.setToolTip(name_tooltip)
            self.profile_table.setItem(row_idx, 1, name_item)

            # Cột 2: Nhóm GPM
            g_name = profile.group_name or self._groups_dict.get(profile.group_id or "", "")
            if not g_name and profile.group_id:
                g_name = f"Nhóm {profile.group_id[:8]}"
            elif not g_name:
                g_name = "Chưa phân nhóm"

            group_item = QTableWidgetItem(f"📁 {g_name}")
            group_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if g_name == "Chưa phân nhóm":
                group_item.setForeground(QColor(COLOR_TEXT_MUTED))
            else:
                group_item.setForeground(QColor(COLOR_TEXT_MAIN))
            self.profile_table.setItem(row_idx, 2, group_item)

            # Cột 3: Ghi chú (lấy từ GPMLogin)
            clean_note = (
                raw_note.replace("<br>", " ")
                .replace("<br/>", " ")
                .replace("<br />", " ")
                .replace("\r\n", " ")
                .replace("\n", " ")
            )
            display_note = " ".join(clean_note.split()) if clean_note else "-"

            note_item = QTableWidgetItem(display_note)
            note_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if display_note == "-":
                note_item.setForeground(QColor(COLOR_TEXT_MUTED))
            else:
                note_item.setForeground(QColor(COLOR_TEXT_MAIN))

            if formatted_tooltip_note:
                note_item.setToolTip(formatted_tooltip_note)

            self.profile_table.setItem(row_idx, 3, note_item)

            # Cột 4: Proxy
            proxy_text = profile.raw_proxy or "Trực tiếp (Không proxy)"
            proxy_item = QTableWidgetItem(proxy_text)
            proxy_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if not profile.raw_proxy:
                proxy_item.setForeground(QColor(COLOR_TEXT_MUTED))
            self.profile_table.setItem(row_idx, 4, proxy_item)

            # Cột 5: Kênh YouTube đã lưu
            cache = self._channel_caches.get(profile.id)
            if cache and cache.channel_name:
                channel_str = f"🎥 {cache.channel_name}"
                if cache.channel_id:
                    channel_str += f" ({cache.channel_id[:10]}...)"
            elif profile.channel_name:
                channel_str = f"🎥 {profile.channel_name}"
            else:
                channel_str = "Chưa liên kết"

            channel_item = QTableWidgetItem(channel_str)
            channel_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if channel_str == "Chưa liên kết":
                channel_item.setForeground(QColor(COLOR_TEXT_MUTED))
            else:
                channel_item.setForeground(QColor(COLOR_PRIMARY))
            self.profile_table.setItem(row_idx, 5, channel_item)

            # Cột 6: Trạng thái GPM
            status_text = "Đang chạy" if profile.is_running else "Sẵn sàng"
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            status_item.setTextAlignment(Qt.AlignCenter)
            if profile.is_running:
                status_item.setForeground(QColor(COLOR_WARNING))
            else:
                status_item.setForeground(QColor(COLOR_SUCCESS))
            self.profile_table.setItem(row_idx, 6, status_item)

        self._is_updating_table = False
        self._filter_profile_rows()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        """Xử lý khi người dùng tích/bỏ tích checkbox ở Cột 0."""
        if self._is_updating_table:
            return
        if item.column() == 0:
            profile_id = item.data(Qt.UserRole)
            if profile_id:
                if item.checkState() == Qt.Checked:
                    self._selected_ids.add(profile_id)
                else:
                    self._selected_ids.discard(profile_id)
                self._update_selected_count_badge()
                self._sync_start_button_state()
                self.save_session_state()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Bấm vào dòng giúp đảo nhanh trạng thái checkbox ở Cột 0."""
        if col != 0 and 0 <= row < self.profile_table.rowCount():
            check_item = self.profile_table.item(row, 0)
            if check_item:
                new_state = Qt.Unchecked if check_item.checkState() == Qt.Checked else Qt.Checked
                check_item.setCheckState(new_state)

    def _filter_profile_rows(self, _arg: Optional[Any] = None) -> None:
        """Lọc các hàng trong bảng theo Nhóm GPM và Từ khóa tìm kiếm."""
        q = self.search_profile_input.text().strip().lower()
        selected_gid = self.combo_group_filter.currentData() or ""

        visible_count = 0
        total_rows = self.profile_table.rowCount()

        for row in range(total_rows):
            profile = self._profiles[row] if row < len(self._profiles) else None
            p_gid = profile.group_id if profile else None

            # 1. Kiểm tra khớp nhóm
            if not selected_gid or selected_gid == "ALL":
                group_match = True
            elif selected_gid == "UNGROUPED":
                group_match = (not p_gid) or (p_gid not in self._groups_dict)
            else:
                group_match = (p_gid == selected_gid)

            if not group_match:
                self.profile_table.setRowHidden(row, True)
                continue

            # 2. Kiểm tra từ khóa tìm kiếm
            if not q:
                self.profile_table.setRowHidden(row, False)
                visible_count += 1
                continue

            name = self.profile_table.item(row, 1).text().lower() if self.profile_table.item(row, 1) else ""
            group_txt = self.profile_table.item(row, 2).text().lower() if self.profile_table.item(row, 2) else ""
            note_txt = self.profile_table.item(row, 3).text().lower() if self.profile_table.item(row, 3) else ""
            proxy = self.profile_table.item(row, 4).text().lower() if self.profile_table.item(row, 4) else ""
            channel = self.profile_table.item(row, 5).text().lower() if self.profile_table.item(row, 5) else ""
            raw_pid = (profile.id or "").lower() if profile else ""

            match = (
                (q in name)
                or (q in group_txt)
                or (q in note_txt)
                or (q in raw_pid)
                or (q in proxy)
                or (q in channel)
            )
            self.profile_table.setRowHidden(row, not match)
            if match:
                visible_count += 1

        self._update_selected_count_badge(visible_count)

    def select_all_profiles(self) -> None:
        """Chọn tất cả profile đang hiển thị (phù hợp cả khi đang lọc theo nhóm)."""
        self._is_updating_table = True
        for row in range(self.profile_table.rowCount()):
            if not self.profile_table.isRowHidden(row):
                item = self.profile_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Checked)
                    pid = item.data(Qt.UserRole)
                    if pid:
                        self._selected_ids.add(pid)
        self._is_updating_table = False
        self._update_selected_count_badge()
        self._sync_start_button_state()
        self.save_session_state()

    def deselect_all_profiles(self) -> None:
        """Bỏ chọn các profile đang hiển thị (nếu đang lọc theo nhóm) hoặc toàn bộ (nếu không lọc)."""
        self._is_updating_table = True
        is_filtered = bool(self.combo_group_filter.currentData() or self.search_profile_input.text().strip())

        for row in range(self.profile_table.rowCount()):
            if not self.profile_table.isRowHidden(row):
                item = self.profile_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)
                    pid = item.data(Qt.UserRole)
                    if pid:
                        self._selected_ids.discard(pid)
            elif not is_filtered:
                item = self.profile_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)

        if not is_filtered:
            self._selected_ids.clear()

        self._is_updating_table = False
        self._update_selected_count_badge()
        self._sync_start_button_state()
        self.save_session_state()

    def _update_selected_count_badge(self, visible_count: Optional[int] = None) -> None:
        """Cập nhật nhãn đếm số lượng profile được chọn và hiển thị."""
        total = len(self._profiles)
        selected = len(self._selected_ids)

        if visible_count is None:
            visible_count = sum(1 for r in range(self.profile_table.rowCount()) if not self.profile_table.isRowHidden(r))

        selected_gid = self.combo_group_filter.currentData() or ""
        q = self.search_profile_input.text().strip()

        if selected_gid or q:
            self.lbl_selected_count.setText(f"Hiển thị: {visible_count}/{total} | Đã chọn: {selected} profile")
        else:
            self.lbl_selected_count.setText(f"Đã chọn: {selected} / {total} profile")

        self._sync_start_button_state()

    def _sync_start_button_state(self) -> None:
        """Đồng bộ trạng thái nút Bắt đầu (không cho bấm nếu chưa chọn profile)."""
        if self._is_running:
            self.btn_start.setEnabled(False)
            return

        has_selection = len(self._selected_ids) > 0
        self.btn_start.setEnabled(has_selection)
        if not has_selection:
            self.btn_start.setToolTip("Vui lòng tích chọn ít nhất 1 Profile GPM để bắt đầu thu thập")
        else:
            self.btn_start.setToolTip(f"Bắt đầu thu thập cho {len(self._selected_ids)} Profile đã chọn")

    # =========================================================================
    # 7. LOGIC CẤU HÌNH DỮ LIỆU & GIAO DIỆN CONTEXTUAL
    # =========================================================================

    def _on_concurrency_changed(self, value: int) -> None:
        """Khi thay đổi số luồng, cập nhật bảng Live Worker Slots và lưu phiên."""
        self.reset_worker_table()
        self.save_session_state()

    def _on_video_scope_toggled(self, button_id: int, checked: bool) -> None:
        """Bật/tắt các ô nhập tương ứng với chế độ chọn video."""
        if not checked:
            return

        # 1: Số lượng gần nhất
        self.spin_video_limit.setEnabled(button_id == 1)

        # 2: Theo thời gian đăng
        self.combo_video_date.setEnabled(button_id == 2)
        is_custom_vdate = (button_id == 2) and (self.combo_video_date.currentData() == "custom")
        self.widget_custom_video_dates.setVisible(is_custom_vdate)

        self.save_session_state()

    def _on_video_date_combo_changed(self, index: int) -> None:
        """Hiển thị DateEdit tùy chỉnh nếu chọn 'Tùy chỉnh khoảng ngày...'."""
        is_custom = self.combo_video_date.currentData() == "custom"
        self.widget_custom_video_dates.setVisible(is_custom and self.radio_date_range.isChecked())
        self.save_session_state()

    def _on_analytics_period_changed(self, index: int) -> None:
        """Hiển thị DateEdit tùy chỉnh nếu chọn khoảng thời gian Analytics tùy chỉnh."""
        is_custom = self.combo_analytics_period.currentData() == "custom"
        self.widget_custom_analytics_dates.setVisible(is_custom)
        self.save_session_state()

    # =========================================================================
    # 8. ĐIỀU KHIỂN TIẾN TRÌNH & BẢNG WORKER SLOTS
    # =========================================================================

    def reset_worker_table(self) -> None:
        """Khởi tạo lại bảng worker slots theo số luồng hiện tại."""
        concurrency = self.concurrency_spin.value()
        self.worker_table.setRowCount(0)
        self.worker_table.setRowCount(concurrency)

        for i in range(concurrency):
            # Cột 0: Tên Luồng
            w_item = QTableWidgetItem(f"Luồng #{i + 1}")
            w_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            w_item.setTextAlignment(Qt.AlignCenter)
            self.worker_table.setItem(i, 0, w_item)

            # Cột 1: Profile
            p_item = QTableWidgetItem("---")
            p_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            p_item.setForeground(QColor(COLOR_TEXT_MUTED))
            self.worker_table.setItem(i, 1, p_item)

            # Cột 2: Kênh
            c_item = QTableWidgetItem("---")
            c_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            c_item.setForeground(QColor(COLOR_TEXT_MUTED))
            self.worker_table.setItem(i, 2, c_item)

            # Cột 3: Bước thực hiện
            step_item = QTableWidgetItem("Chờ việc trong hàng đợi...")
            step_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            step_item.setForeground(QColor(COLOR_TEXT_MUTED))
            self.worker_table.setItem(i, 3, step_item)

            # Cột 4: Trạng thái
            st_item = QTableWidgetItem("Sẵn sàng")
            st_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            st_item.setTextAlignment(Qt.AlignCenter)
            st_item.setForeground(QColor(COLOR_TEXT_MUTED))
            self.worker_table.setItem(i, 4, st_item)

            # Cột 5: Thời gian
            time_item = QTableWidgetItem("00:00")
            time_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            time_item.setTextAlignment(Qt.AlignCenter)
            time_item.setForeground(QColor(COLOR_TEXT_MUTED))
            self.worker_table.setItem(i, 5, time_item)

    def update_worker_status(
        self,
        worker_idx: int,
        profile_name: str,
        channel_name: str,
        step: str,
        status: str,
        elapsed: str = "00:00",
    ) -> None:
        """Cập nhật dòng thông tin của một worker slot cụ thể."""
        if 0 <= worker_idx < self.worker_table.rowCount():
            self.worker_table.item(worker_idx, 1).setText(profile_name)
            self.worker_table.item(worker_idx, 1).setForeground(QColor(COLOR_TEXT_MAIN))

            self.worker_table.item(worker_idx, 2).setText(channel_name or "Đang nhận diện...")
            self.worker_table.item(worker_idx, 2).setForeground(QColor(COLOR_PRIMARY))

            self.worker_table.item(worker_idx, 3).setText(step)
            self.worker_table.item(worker_idx, 3).setForeground(QColor(COLOR_TEXT_MAIN))

            status_item = self.worker_table.item(worker_idx, 4)
            status_item.setText(status)
            if "lỗi" in status.lower() or "fail" in status.lower():
                status_item.setForeground(QColor(COLOR_DANGER))
            elif "thành công" in status.lower() or "xong" in status.lower() or "success" in status.lower():
                status_item.setForeground(QColor(COLOR_SUCCESS))
            else:
                status_item.setForeground(QColor(COLOR_WARNING))

            self.worker_table.item(worker_idx, 5).setText(elapsed)

        # Cập nhật số liệu trên các mini badge
        self._refresh_stat_badges_from_table()

    def set_overall_progress(self, current: int, total: int, status_text: str = "") -> None:
        """Cập nhật giá trị thanh tiến trình tổng và nhãn chi tiết."""
        if total <= 0:
            self.overall_progress_bar.setRange(0, 100)
            self.overall_progress_bar.setValue(0)
            self.lbl_progress_detail.setText("Tiến độ: 0/0 profile hoàn thành | Đang xử lý: 0 | Còn lại: 0")
            self._update_stat_badges(completed=0, running=0, pending=0, failed=0)
            return

        self.overall_progress_bar.setRange(0, total)
        self.overall_progress_bar.setValue(current)
        remaining = max(0, total - current)
        self.lbl_progress_detail.setText(
            f"Tiến độ: {current}/{total} profile hoàn thành | Còn lại: {remaining} profile"
        )
        if status_text:
            self.lbl_overall_status.setText(f"Trạng thái: {status_text}")
        self._refresh_stat_badges_from_table()

    def set_running_state(self, is_running: bool) -> None:
        """Chuyển đổi giao diện giữa chế độ Đang chạy và Chế độ Chờ."""
        self._is_running = is_running

        # Nút điều khiển
        self.btn_start.setEnabled(not is_running and len(self._selected_ids) > 0)
        self.btn_stop.setEnabled(is_running)
        self.btn_refresh_profiles.setEnabled(not is_running)
        self.btn_select_all.setEnabled(not is_running)
        self.btn_deselect_all.setEnabled(not is_running)

        # Bộ lọc nhóm và tìm kiếm
        self.combo_group_filter.setEnabled(not is_running)
        self.search_profile_input.setEnabled(not is_running)

        # Cấu hình đa luồng và dữ liệu
        self.concurrency_spin.setEnabled(not is_running)
        self.radio_recent.setEnabled(not is_running)
        self.radio_date_range.setEnabled(not is_running)
        self.radio_all_videos.setEnabled(not is_running)
        self.spin_video_limit.setEnabled(not is_running and self.radio_recent.isChecked())
        self.combo_video_date.setEnabled(not is_running and self.radio_date_range.isChecked())
        self.combo_analytics_period.setEnabled(not is_running)
        self.radio_depth_std.setEnabled(not is_running)
        self.radio_depth_fast.setEnabled(not is_running)
        self.radio_depth_full.setEnabled(not is_running)

        if is_running:
            self.lbl_overall_status.setText("Trạng thái: 🚀 Đang tiến hành thu thập dữ liệu...")
        else:
            self.lbl_overall_status.setText("Trạng thái: Sẵn sàng.")

    def _on_start_clicked(self) -> None:
        """Xử lý khi người dùng nhấn [ BẮT ĐẦU THU THẬP ]."""
        if not self._selected_ids:
            QMessageBox.warning(
                self,
                "Chưa chọn Profile",
                "Vui lòng tích chọn ít nhất 1 Profile GPM từ danh sách trước khi bắt đầu!",
            )
            return

        # Tự động mở bảng Worker table nếu đang thu gọn
        if hasattr(self, "worker_table") and not self.worker_table.isVisible():
            self.worker_table.setVisible(True)
            if hasattr(self, "btn_toggle_workers"):
                self.btn_toggle_workers.setText("▾ Thu gọn theo dõi")

        config = self.get_configuration()
        self.save_session_state()
        self.set_running_state(True)
        self.set_overall_progress(0, len(self._selected_ids), "Bắt đầu khởi chạy...")
        self.reset_worker_table()

        # Phát tín hiệu cho MainWindow / Coordinator
        self.start_requested.emit(config)

    def _on_stop_clicked(self) -> None:
        """Xử lý khi người dùng nhấn [ DỪNG LẠI ]."""
        self.lbl_overall_status.setText("Trạng thái: Đang gửi yêu cầu dừng các luồng an toàn...")
        self.btn_stop.setEnabled(False)
        self.stop_requested.emit()

    def _on_open_runs_clicked(self) -> None:
        """Mở thư mục runs/ trong File Explorer của Windows."""
        runs_dir = Path("runs").resolve()
        runs_dir.mkdir(parents=True, exist_ok=True)
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(runs_dir)))
        except Exception as ex:
            logger.warning("Không thể mở thư mục runs: %s", ex)

    # =========================================================================
    # 9. LẤY & KHÔI PHỤC CẤU HÌNH PHIÊN (SESSION STATE PERSISTENCE)
    # =========================================================================

    def get_configuration(self) -> Dict[str, Any]:
        """Tổng hợp toàn bộ tham số cấu hình hiện tại của Tab 1."""
        # Chế độ video
        if self.radio_recent.isChecked():
            v_mode = "recent_count"
        elif self.radio_date_range.isChecked():
            v_mode = "date_range"
        else:
            v_mode = "all"

        # Mức độ thu thập
        if self.radio_depth_fast.isChecked():
            depth = "fast"
        elif self.radio_depth_full.isChecked():
            depth = "full"
        else:
            depth = "standard"

        return {
            "selected_profile_ids": sorted(list(self._selected_ids)),
            "selected_group_id": self.combo_group_filter.currentData() or "",
            "concurrency": self.concurrency_spin.value(),
            "video_selection_mode": v_mode,
            "video_limit": self.spin_video_limit.value(),
            "video_date_preset": self.combo_video_date.currentData() or "28_days",
            "video_date_from": self.date_video_from.date().toString("yyyy-MM-dd"),
            "video_date_to": self.date_video_to.date().toString("yyyy-MM-dd"),
            "analytics_period": self.combo_analytics_period.currentData() or "28_days",
            "analytics_date_from": self.date_analytics_from.date().toString("yyyy-MM-dd"),
            "analytics_date_to": self.date_analytics_to.date().toString("yyyy-MM-dd"),
            "collection_depth": depth,
        }

    def save_session_state(self) -> None:
        """Lưu trạng thái lựa chọn hiện tại vào SQLite."""
        try:
            cfg = self.get_configuration()
            session = AppSessionState(
                selected_profile_ids=cfg["selected_profile_ids"],
                video_selection_mode=cfg["video_selection_mode"],
                video_limit=cfg["video_limit"],
                date_range_preset=cfg["analytics_period"],
                custom_date_from=cfg["analytics_date_from"],
                custom_date_to=cfg["analytics_date_to"],
                concurrency=cfg["concurrency"],
                api_port=self.gpm_client.port,
                selected_group_id=self.combo_group_filter.currentData() or None,
            )
            self.history_storage.save_session_state(session)
        except Exception as ex:
            logger.debug("Lỗi lưu session state: %s", ex)

    def load_session_state(self) -> None:
        """Khôi phục các lựa chọn từ phiên trước."""
        try:
            session = self.history_storage.load_session_state()
            self._selected_ids = set(session.selected_profile_ids or [])
            self._selected_group_id_saved = getattr(session, "selected_group_id", None)
            if self._selected_group_id_saved:
                idx = self.combo_group_filter.findData(self._selected_group_id_saved)
                if idx >= 0:
                    self.combo_group_filter.setCurrentIndex(idx)

            self.concurrency_spin.setValue(max(1, min(10, session.concurrency or 2)))

            # Khôi phục chế độ video
            if session.video_selection_mode == "recent_count":
                self.radio_recent.setChecked(True)
                self.spin_video_limit.setValue(session.video_limit or 10)
            elif session.video_selection_mode == "date_range":
                self.radio_date_range.setChecked(True)
            elif session.video_selection_mode == "all":
                self.radio_all_videos.setChecked(True)

            # Khôi phục Analytics Period
            idx = self.combo_analytics_period.findData(session.date_range_preset)
            if idx >= 0:
                self.combo_analytics_period.setCurrentIndex(idx)

            if session.custom_date_from:
                qdate_from = QDate.fromString(session.custom_date_from, "yyyy-MM-dd")
                if qdate_from.isValid():
                    self.date_analytics_from.setDate(qdate_from)
            if session.custom_date_to:
                qdate_to = QDate.fromString(session.custom_date_to, "yyyy-MM-dd")
                if qdate_to.isValid():
                    self.date_analytics_to.setDate(qdate_to)

            self._update_selected_count_badge()
        except Exception as ex:
            logger.debug("Lỗi tải session state: %s", ex)
