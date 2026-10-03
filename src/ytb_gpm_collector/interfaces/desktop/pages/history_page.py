"""History Page view (Tab 2: Lịch sử & Kết quả).

Triển khai hoàn chỉnh Task 4.3:
- Quét và hiển thị bảng danh sách các đợt chạy trong thư mục runs/ và SQLite DB.
- Bộ lọc tìm kiếm theo tên kênh, Run ID và trạng thái (Hoàn tất, Cảnh báo, Thất bại).
- Khung xem chi tiết đợt chạy (Detail Card) với đầy đủ thông số chất lượng, tệp tin sinh ra.
- Nút mở thư mục đợt chạy trong Explorer, mở bảng Excel videos.csv, mở folder evidence/.
- Dialog xem nhanh báo cáo tóm tắt README.md trực tiếp trên giao diện không cần mở app ngoài.
- Nút tạo lại báo cáo (Rebuild reports) cập nhật tức thì manifest.json và quality_report.json.
"""

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QLineEdit,
    QComboBox,
    QListView,
    QDialog,
    QTextEdit,
    QMessageBox,
    QSplitter,
    QScrollArea,
)

from ytb_gpm_collector.domain.models import RunHistoryRecord
from ytb_gpm_collector.integrations.storage.history import LocalStorage, HistoryStorage
from ytb_gpm_collector.integrations.storage.runs import (
    build_run_reports,
    format_number,
)
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
    COLOR_BORDER,
    COLOR_INFO_BG,
    COLOR_BG_DARK_LOG,
    FONT_FAMILY_MONO,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. HÀM TIỆN ÍCH HỆ THỐNG & ĐỊNH DẠNG
# ==============================================================================

def open_path_in_system(path: Union[Path, str]) -> bool:
    """Mở tệp tin hoặc thư mục bằng ứng dụng mặc định của hệ điều hành."""
    target = Path(path).resolve()
    if not target.exists():
        logger.warning("Đường dẫn không tồn tại: %s", target)
        return False

    try:
        if sys.platform == "win32":
            os.startfile(str(target))
            return True
        else:
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
    except Exception as ex:
        logger.warning("Lỗi khi mở đường dẫn %s: %s", target, ex)
        return False


def format_iso_to_display(iso_str: Optional[str]) -> str:
    """Định dạng chuỗi thời gian ISO thành dd/MM/yyyy HH:mm:ss dễ đọc."""
    if not iso_str:
        return "-"
    try:
        # Chuẩn hóa nếu có dấu Z hoặc microseconds
        cleaned = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        # Nếu chuỗi dạng YYYY-MM-DD_HHMMSS từ tên thư mục
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})(\d{2})", iso_str)
        if match:
            y, m, d, hh, mm, ss = match.groups()
            return f"{d}/{m}/{y} {hh}:{mm}"
        return iso_str[:16] if len(iso_str) >= 16 else iso_str


def format_bytes_to_human(size_bytes: int) -> str:
    """Chuyển đổi kích thước bytes thành định dạng KB, MB dễ đọc."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


# ==============================================================================
# 2. CẤU TRÚC DỮ LIỆU ĐỢT CHẠY (RUN ENTRY)
# ==============================================================================

@dataclass
class RunEntry:
    """Thông tin tổng hợp của một đợt chạy trong thư mục runs/."""
    run_id: str
    run_dir: Path
    channel_name: str = "Chưa rõ"
    channel_id: str = "N/A"
    profile_name: Optional[str] = None
    profile_id: Optional[str] = None
    period: str = "28_days"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    created_at: str = ""
    finished_at: Optional[str] = None
    status: str = "success"  # success, partial, failed, running
    video_count: int = 0
    daily_metrics_count: int = 0
    traffic_sources_count: int = 0
    raw_files_count: int = 0
    evidence_files_count: int = 0
    total_size_bytes: int = 0
    completeness_score_percent: float = 100.0
    total_warnings: int = 0
    total_errors: int = 0
    reconciled: bool = True
    reconciliation_notes: Optional[str] = None
    has_readme: bool = False
    has_manifest: bool = False
    has_quality_report: bool = False
    has_videos_csv: bool = False
    has_videos_jsonl: bool = False
    has_evidence: bool = False
    has_raw: bool = False

    @property
    def display_period(self) -> str:
        """Chuỗi hiển thị thân thiện của kỳ phân tích."""
        p = self.period.replace("_days", " ngày qua").replace("days", " ngày qua").replace("28d", "28 ngày qua")
        if self.period_start and self.period_end:
            return f"{p} ({self.period_start} → {self.period_end})"
        return p

    @property
    def status_label(self) -> str:
        """Huy hiệu trạng thái có icon."""
        st = self.status.lower()
        if st in ["success", "passed"]:
            return "✅ Hoàn tất 100%"
        elif st in ["partial", "warnings", "warning"]:
            return "⚠️ Có cảnh báo"
        elif st in ["failed", "error"]:
            return "❌ Thất bại"
        elif st in ["running", "initialized"]:
            return "⏳ Đang chạy"
        return f"⚪ {self.status.capitalize()}"


def scan_single_run_dir(run_path: Path) -> Optional[RunEntry]:
    """Quét và trích xuất dữ liệu từ một thư mục run."""
    if not run_path.is_dir() or run_path.name.startswith("."):
        return None

    run_id = run_path.name
    # Bỏ qua các thư mục tạm không phải cấu trúc run
    if run_id in ["test_evidence", "test_export"] and not (run_path / "manifest.json").exists():
        return None

    manifest_file = run_path / "manifest.json"
    quality_file = run_path / "quality_report.json"
    readme_file = run_path / "README.md"
    videos_csv = run_path / "data" / "videos.csv"
    videos_jsonl = run_path / "data" / "videos.jsonl"
    evidence_dir = run_path / "evidence"
    raw_dir = run_path / "raw"

    has_manifest = manifest_file.exists()
    has_quality = quality_file.exists()
    has_readme = readme_file.exists()
    has_videos_csv = videos_csv.exists()
    has_videos_jsonl = videos_jsonl.exists()

    evidence_files = [p for p in evidence_dir.iterdir() if p.is_file()] if evidence_dir.exists() else []
    raw_files = [p for p in raw_dir.iterdir() if p.is_file()] if raw_dir.exists() else []

    channel_name = "Chưa rõ"
    channel_id = "N/A"
    period = "28_days"
    period_start = None
    period_end = None
    created_at = ""
    finished_at = None
    status = "success"
    video_count = 0
    daily_count = 0
    traffic_count = 0
    raw_count = len(raw_files)
    evidence_count = len(evidence_files)
    total_size = 0
    completeness = 100.0
    total_warnings = 0
    total_errors = 0
    reconciled = True
    recon_notes = None

    # 1. Đọc manifest.json nếu có
    if has_manifest:
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                m_data = json.load(f)
                channel_name = m_data.get("channel_name") or channel_name
                channel_id = m_data.get("channel_id") or channel_id
                period = m_data.get("period") or period
                period_start = m_data.get("period_start")
                period_end = m_data.get("period_end")
                created_at = m_data.get("created_at") or ""
                finished_at = m_data.get("finished_at")
                status = m_data.get("status") or status

                summary = m_data.get("summary") or {}
                video_count = summary.get("video_count", 0)
                daily_count = summary.get("daily_metrics_count", 0)
                traffic_count = summary.get("traffic_sources_count", 0)
                raw_count = summary.get("raw_files_count", raw_count)
                evidence_count = summary.get("evidence_files_count", evidence_count)
                total_size = summary.get("total_size_bytes", 0)

                q_summary = m_data.get("quality_summary") or {}
                if q_summary:
                    completeness = q_summary.get("completeness_score_percent", 100.0)
                    total_warnings = q_summary.get("total_warnings", 0)
                    total_errors = q_summary.get("total_errors", 0)
                    reconciled = q_summary.get("reconciled", True)
        except Exception as ex:
            logger.warning("Lỗi đọc manifest %s: %s", manifest_file, ex)

    # 2. Đọc quality_report.json nếu có để bổ sung chi tiết
    if has_quality:
        try:
            with open(quality_file, "r", encoding="utf-8") as f:
                q_data = json.load(f)
                q_sum = q_data.get("summary") or {}
                completeness = q_sum.get("completeness_score_percent", completeness)
                total_warnings = q_sum.get("total_warnings", total_warnings)
                total_errors = q_sum.get("total_errors", total_errors)
                q_checks = q_data.get("checks") or {}
                recon_obj = q_checks.get("summary_reconciliation") or {}
                reconciled = recon_obj.get("reconciled", reconciled)
                recon_notes = recon_obj.get("notes")
        except Exception as ex:
            logger.warning("Lỗi đọc quality_report %s: %s", quality_file, ex)

    # 3. Nếu thiếu ngày giờ, lấy từ thời gian sửa đổi thư mục hoặc tên
    if not created_at:
        try:
            created_at = datetime.fromtimestamp(run_path.stat().st_mtime).isoformat()
        except Exception:
            created_at = datetime.now().isoformat()

    # 4. Dự phòng nếu chưa có video_count mà có file videos.csv
    if video_count == 0 and has_videos_csv:
        try:
            with open(videos_csv, "r", encoding="utf-8-sig") as f:
                video_count = max(0, sum(1 for _ in f) - 1)
        except Exception:
            pass

    # 5. Nếu chưa có total_size, tính tổng dung lượng file trong thư mục
    if total_size == 0:
        try:
            total_size = sum(f.stat().st_size for f in run_path.rglob("*") if f.is_file())
        except Exception:
            pass

    return RunEntry(
        run_id=run_id,
        run_dir=run_path,
        channel_name=channel_name,
        channel_id=channel_id,
        period=period,
        period_start=period_start,
        period_end=period_end,
        created_at=created_at,
        finished_at=finished_at,
        status=status,
        video_count=video_count,
        daily_metrics_count=daily_count,
        traffic_sources_count=traffic_count,
        raw_files_count=raw_count,
        evidence_files_count=evidence_count,
        total_size_bytes=total_size,
        completeness_score_percent=completeness,
        total_warnings=total_warnings,
        total_errors=total_errors,
        reconciled=reconciled,
        reconciliation_notes=recon_notes,
        has_readme=has_readme,
        has_manifest=has_manifest,
        has_quality_report=has_quality,
        has_videos_csv=has_videos_csv,
        has_videos_jsonl=has_videos_jsonl,
        has_evidence=len(evidence_files) > 0,
        has_raw=len(raw_files) > 0,
    )


# ==============================================================================
# 3. DIALOG XEM NHANH BÁO CÁO README.md (README VIEWER)
# ==============================================================================

class ReadmeViewerDialog(QDialog):
    """Cửa sổ Popup hiển thị nội dung báo cáo tóm tắt README.md."""

    def __init__(self, run_entry: RunEntry, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.run_entry = run_entry
        self.setWindowTitle(f"Báo Cáo Tóm Tắt: {run_entry.channel_name} - {run_entry.run_id}")
        self.resize(850, 650)
        self.setMinimumSize(600, 450)
        self._init_ui()
        self._load_content()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Info
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        lbl_title = QLabel(f"📄 Báo cáo YouTube Studio: {self.run_entry.channel_name}")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #0F172A;")
        lbl_sub = QLabel(f"Run ID: {self.run_entry.run_id} | Thư mục: {self.run_entry.run_dir}")
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_sub)
        header_layout.addLayout(title_layout)

        header_layout.addStretch()

        self.btn_copy = QPushButton("📋 Sao chép")
        self.btn_copy.clicked.connect(self._copy_content)
        header_layout.addWidget(self.btn_copy)

        self.btn_open_folder = QPushButton("📁 Mở thư mục")
        self.btn_open_folder.clicked.connect(lambda: open_path_in_system(self.run_entry.run_dir))
        header_layout.addWidget(self.btn_open_folder)

        layout.addWidget(header_frame)

        # Content Text Area
        self.text_viewer = QTextEdit()
        self.text_viewer.setReadOnly(True)
        self.text_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 14px;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.text_viewer)

        # Footer Buttons
        footer_row = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #059669; font-weight: 600;")
        footer_row.addWidget(self.lbl_status)
        footer_row.addStretch()

        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        btn_close.setProperty("btnType", "primary")
        footer_row.addWidget(btn_close)

        layout.addLayout(footer_row)

    def _load_content(self) -> None:
        readme_path = self.run_entry.run_dir / "README.md"
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8")
                self.text_viewer.setMarkdown(content)
                return
            except Exception as ex:
                logger.warning("Không thể đọc README.md: %s", ex)

        # Dự phòng nếu chưa có README.md
        fallback = (
            f"# Thông tin đợt chạy: {self.run_entry.run_id}\n\n"
            f"- **Kênh YouTube:** {self.run_entry.channel_name}\n"
            f"- **Channel ID:** `{self.run_entry.channel_id}`\n"
            f"- **Thời gian cào:** {self.run_entry.created_at}\n"
            f"- **Phạm vi số liệu:** {self.run_entry.display_period}\n"
            f"- **Số lượng video:** {self.run_entry.video_count}\n"
            f"- **Trạng thái:** {self.run_entry.status_label}\n\n"
            f"*(Chưa có tệp tin README.md trong thư mục này. Bấm nút 'Tạo lại báo cáo' để sinh tự động)*"
        )
        self.text_viewer.setMarkdown(fallback)

    def _copy_content(self) -> None:
        from PySide6.QtWidgets import QApplication
        text = self.text_viewer.toPlainText()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.lbl_status.setText("✓ Đã sao chép nội dung báo cáo!")


# ==============================================================================
# 4. GIAO DIỆN CHÍNH TAB 2: LỊCH SỬ & KẾT QUẢ (HISTORY PAGE)
# ==============================================================================

class HistoryPage(QWidget):
    """Màn hình Lịch sử & Kết quả thu thập (Tab 2)."""

    # Signal phát ra khi cần chuyển sang Tab xem Logs hoặc chạy lại
    run_selected = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        history_storage: Optional[HistoryStorage] = None,
        runs_dir: Optional[Union[Path, str]] = None,
        auto_load: bool = True,
    ):
        super().__init__(parent)
        self.setProperty("class", "page-container")

        self.history_storage = history_storage or HistoryStorage()
        self.runs_dir = Path(runs_dir or "runs").resolve()
        self._runs: List[RunEntry] = []
        self._selected_entry: Optional[RunEntry] = None
        self._is_updating = False

        self._init_ui()
        self._wire_signals()

        if auto_load:
            self.reload_runs()

    # =========================================================================
    # 4.1. KHỞI TẠO BỐ CỤC GIAO DIỆN
    # =========================================================================

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Thanh tiêu đề & Công cụ trên cùng
        header_row = QHBoxLayout()
        header_layout = QVBoxLayout()
        header_layout.setSpacing(3)

        title = QLabel("Lịch sử & Kết quả thu thập")
        title.setProperty("class", "page-title")
        header_layout.addWidget(title)

        subtitle = QLabel("Danh sách các phiên thu thập trong thư mục runs/, xem báo cáo và truy xuất dữ liệu")
        subtitle.setProperty("class", "page-subtitle")
        header_layout.addWidget(subtitle)
        header_row.addLayout(header_layout)

        header_row.addStretch()

        self.btn_open_runs = QPushButton("📁 Mở thư mục runs/")
        self.btn_open_runs.setToolTip("Mở thư mục gốc chứa toàn bộ các đợt chạy trong Explorer")
        header_row.addWidget(self.btn_open_runs)

        self.btn_refresh = QPushButton("⟳ Làm mới")
        self.btn_refresh.setToolTip("Quét lại toàn bộ thư mục runs/ và cập nhật bảng")
        header_row.addWidget(self.btn_refresh)

        main_layout.addLayout(header_row)

        # 2. Card chính: Bảng danh sách các đợt chạy
        self.card_table = QFrame()
        self.card_table.setProperty("class", "card")
        card_table_layout = QVBoxLayout(self.card_table)
        card_table_layout.setContentsMargins(16, 14, 16, 14)
        card_table_layout.setSpacing(10)

        # Thanh tìm kiếm và lọc
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Tìm theo tên kênh hoặc Run ID...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMaximumWidth(320)
        filter_row.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.setView(QListView())
        self.status_filter.addItem("Tất cả trạng thái", "")
        self.status_filter.addItem("✅ Hoàn tất 100%", "success")
        self.status_filter.addItem("⚠️ Có cảnh báo", "partial")
        self.status_filter.addItem("❌ Thất bại", "failed")
        self.status_filter.setMaximumWidth(170)
        filter_row.addWidget(self.status_filter)

        filter_row.addStretch()

        self.lbl_runs_count = QLabel("Tổng cộng: 0 đợt chạy")
        self.lbl_runs_count.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        filter_row.addWidget(self.lbl_runs_count)

        card_table_layout.addLayout(filter_row)

        # Bảng danh sách đợt chạy
        self.runs_table = QTableWidget()
        self.runs_table.setColumnCount(6)
        self.runs_table.setHorizontalHeaderLabels([
            "Thời gian",
            "Tên Kênh YouTube",
            "Phạm vi số liệu",
            "Số video",
            "Trạng thái",
            "Thao tác nhanh",
        ])

        # Cấu hình hiển thị bảng
        self.runs_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.runs_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.runs_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.runs_table.setAlternatingRowColors(True)
        self.runs_table.verticalHeader().setVisible(False)
        self.runs_table.setShowGrid(True)
        self.runs_table.setMinimumHeight(240)

        # Tỷ lệ cột
        header = self.runs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        card_table_layout.addWidget(self.runs_table)
        main_layout.addWidget(self.card_table, stretch=3)

        # 3. Card chi tiết lần chạy đang chọn (Detail Card)
        self.card_detail = QFrame()
        self.card_detail.setProperty("class", "card")
        self.card_detail.setStyleSheet("background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px;")
        card_detail_layout = QVBoxLayout(self.card_detail)
        card_detail_layout.setContentsMargins(18, 14, 18, 14)
        card_detail_layout.setSpacing(10)

        # Tiêu đề card chi tiết
        detail_header_row = QHBoxLayout()
        self.lbl_detail_title = QLabel("CHI TIẾT LẦN CHẠY: (Chưa chọn)")
        self.lbl_detail_title.setProperty("class", "card-title")
        self.lbl_detail_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        detail_header_row.addWidget(self.lbl_detail_title)

        detail_header_row.addStretch()

        self.lbl_detail_dir = QLabel("")
        self.lbl_detail_dir.setStyleSheet("font-size: 11px; color: #64748B;")
        detail_header_row.addWidget(self.lbl_detail_dir)
        card_detail_layout.addLayout(detail_header_row)

        # Khối thông tin lưới 2 cột
        self.info_grid = QGridLayout()
        self.info_grid.setHorizontalSpacing(24)
        self.info_grid.setVerticalSpacing(6)

        # Cột 1: Thông tin kênh & thời gian
        self.lbl_info_channel = QLabel("Kênh: -")
        self.lbl_info_period = QLabel("Phạm vi: -")
        self.lbl_info_created = QLabel("Thời điểm: -")
        self.info_grid.addWidget(self.lbl_info_channel, 0, 0)
        self.info_grid.addWidget(self.lbl_info_period, 1, 0)
        self.info_grid.addWidget(self.lbl_info_created, 2, 0)

        # Cột 2: Số liệu & Tệp tin
        self.lbl_info_metrics = QLabel("Số liệu: -")
        self.lbl_info_quality = QLabel("Kiểm định: -")
        self.lbl_info_files = QLabel("Tệp tin: -")
        self.info_grid.addWidget(self.lbl_info_metrics, 0, 1)
        self.info_grid.addWidget(self.lbl_info_quality, 1, 1)
        self.info_grid.addWidget(self.lbl_info_files, 2, 1)

        card_detail_layout.addLayout(self.info_grid)

        # Thanh nút hành động nhanh cho lần chạy đang chọn
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.btn_detail_readme = QPushButton("📄 Xem Báo Cáo README.md")
        self.btn_detail_readme.setProperty("btnType", "primary")
        self.btn_detail_readme.setEnabled(False)
        action_bar.addWidget(self.btn_detail_readme)

        self.btn_detail_open_folder = QPushButton("📁 Mở Thư Mục Chứa File")
        self.btn_detail_open_folder.setEnabled(False)
        action_bar.addWidget(self.btn_detail_open_folder)

        self.btn_detail_open_csv = QPushButton("📊 Mở File Excel (videos.csv)")
        self.btn_detail_open_csv.setEnabled(False)
        action_bar.addWidget(self.btn_detail_open_csv)

        self.btn_detail_open_evidence = QPushButton("🖼️ Xem Bằng Chứng (evidence/)")
        self.btn_detail_open_evidence.setEnabled(False)
        action_bar.addWidget(self.btn_detail_open_evidence)

        action_bar.addStretch()

        self.btn_detail_rebuild = QPushButton("🔄 Tạo Lại Báo Cáo")
        self.btn_detail_rebuild.setToolTip("Sinh lại README.md, manifest.json và quality_report.json từ dữ liệu hiện có")
        self.btn_detail_rebuild.setEnabled(False)
        action_bar.addWidget(self.btn_detail_rebuild)

        card_detail_layout.addLayout(action_bar)
        main_layout.addWidget(self.card_detail, stretch=1)

    # =========================================================================
    # 4.2. KẾT NỐI TÍN HIỆU (WIRE SIGNALS)
    # =========================================================================

    def _wire_signals(self) -> None:
        self.btn_open_runs.clicked.connect(self._on_open_runs_folder)
        self.btn_refresh.clicked.connect(self.reload_runs)
        self.search_input.textChanged.connect(self._apply_filters)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)

        self.runs_table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.runs_table.cellDoubleClicked.connect(self._on_table_double_clicked)

        self.btn_detail_readme.clicked.connect(self._on_view_selected_readme)
        self.btn_detail_open_folder.clicked.connect(self._on_open_selected_folder)
        self.btn_detail_open_csv.clicked.connect(self._on_open_selected_csv)
        self.btn_detail_open_evidence.clicked.connect(self._on_open_selected_evidence)
        self.btn_detail_rebuild.clicked.connect(self._on_rebuild_selected_reports)

    # =========================================================================
    # 4.3. QUÉT VÀ NẠP DỮ LIỆU ĐỢT CHẠY (RELOAD & SCAN)
    # =========================================================================

    def reload_runs(self) -> None:
        """Quét thư mục runs/ và cập nhật toàn bộ bảng."""
        self._is_updating = True
        try:
            self.runs_dir.mkdir(parents=True, exist_ok=True)
            entries: List[RunEntry] = []

            # Quét tất cả thư mục con trong runs_dir
            for item in self.runs_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    entry = scan_single_run_dir(item)
                    if entry:
                        entries.append(entry)

            # Sắp xếp mới nhất lên đầu theo created_at
            entries.sort(key=lambda x: x.created_at, reverse=True)
            self._runs = entries

            # Cập nhật bảng
            self._populate_table()
            self._apply_filters()

            # Tự động chọn hàng đầu tiên nếu có
            if self.runs_table.rowCount() > 0:
                self.runs_table.selectRow(0)
            else:
                self._clear_detail_card()

        finally:
            self._is_updating = False

    def _populate_table(self) -> None:
        """Hiển thị danh sách RunEntry vào QTableWidget."""
        self.runs_table.setRowCount(0)
        self.runs_table.setRowCount(len(self._runs))

        for row, entry in enumerate(self._runs):
            # 0. Thời gian
            item_time = QTableWidgetItem(format_iso_to_display(entry.created_at))
            item_time.setTextAlignment(Qt.AlignCenter)
            self.runs_table.setItem(row, 0, item_time)

            # 1. Tên kênh
            item_channel = QTableWidgetItem(f"📹 {entry.channel_name}")
            item_channel.setToolTip(f"Channel ID: {entry.channel_id}\nRun ID: {entry.run_id}")
            font = item_channel.font()
            font.setBold(True)
            item_channel.setFont(font)
            self.runs_table.setItem(row, 1, item_channel)

            # 2. Phạm vi số liệu
            item_period = QTableWidgetItem(entry.display_period)
            self.runs_table.setItem(row, 2, item_period)

            # 3. Số video
            item_videos = QTableWidgetItem(f"{entry.video_count} video")
            item_videos.setTextAlignment(Qt.AlignCenter)
            self.runs_table.setItem(row, 3, item_videos)

            # 4. Trạng thái
            item_status = QTableWidgetItem(entry.status_label)
            item_status.setTextAlignment(Qt.AlignCenter)
            if entry.status in ["success", "passed"]:
                item_status.setForeground(QColor(COLOR_SUCCESS))
            elif entry.status in ["partial", "warnings", "warning"]:
                item_status.setForeground(QColor(COLOR_WARNING))
            elif entry.status in ["failed", "error"]:
                item_status.setForeground(QColor(COLOR_DANGER))
            self.runs_table.setItem(row, 4, item_status)

            # 5. Cột Thao tác nhanh (Cell Widget với 2 nút)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)

            btn_open = QPushButton("📁 Mở")
            btn_open.setToolTip("Mở thư mục trong Explorer")
            btn_open.clicked.connect(lambda _, e=entry: open_path_in_system(e.run_dir))
            action_layout.addWidget(btn_open)

            btn_readme = QPushButton("📄 README")
            btn_readme.setToolTip("Xem tóm tắt báo cáo README.md")
            btn_readme.clicked.connect(lambda _, e=entry: self._view_readme(e))
            action_layout.addWidget(btn_readme)

            self.runs_table.setCellWidget(row, 5, action_widget)

        self.lbl_runs_count.setText(f"Tổng cộng: {len(self._runs)} đợt chạy")

    # =========================================================================
    # 4.4. BỘ LỌC TÌM KIẾM & TRẠNG THÁI
    # =========================================================================

    def _apply_filters(self) -> None:
        """Lọc các dòng trong bảng theo từ khóa tìm kiếm và trạng thái."""
        search_query = self.search_input.text().strip().lower()
        selected_status = self.status_filter.currentData()

        visible_count = 0
        for row in range(self.runs_table.rowCount()):
            if row >= len(self._runs):
                break
            entry = self._runs[row]

            # Kiểm tra từ khóa tìm kiếm (kênh, ID, run_id)
            match_search = True
            if search_query:
                combined_text = f"{entry.channel_name} {entry.channel_id} {entry.run_id}".lower()
                match_search = search_query in combined_text

            # Kiểm tra trạng thái
            match_status = True
            if selected_status:
                if selected_status == "success":
                    match_status = entry.status in ["success", "passed"]
                elif selected_status == "partial":
                    match_status = entry.status in ["partial", "warnings", "warning"]
                elif selected_status == "failed":
                    match_status = entry.status in ["failed", "error"]

            should_show = match_search and match_status
            self.runs_table.setRowHidden(row, not should_show)
            if should_show:
                visible_count += 1

        self.lbl_runs_count.setText(f"Hiển thị: {visible_count} / {len(self._runs)} đợt chạy")

    # =========================================================================
    # 4.5. XỬ LÝ SỰ KIỆN CHỌN HÀNG VÀ CẬP NHẬT CHI TIẾT
    # =========================================================================

    def _on_table_selection_changed(self) -> None:
        """Kích hoạt khi người dùng chọn một dòng trong bảng."""
        selected_rows = self.runs_table.selectionModel().selectedRows()
        if not selected_rows:
            self._clear_detail_card()
            return

        row = selected_rows[0].row()
        if 0 <= row < len(self._runs):
            entry = self._runs[row]
            self._update_detail_card(entry)

    def _on_table_double_clicked(self, row: int, col: int) -> None:
        """Nhấp đúp chuột vào dòng sẽ mở xem README."""
        if 0 <= row < len(self._runs):
            entry = self._runs[row]
            self._view_readme(entry)

    def _update_detail_card(self, entry: RunEntry) -> None:
        """Hiển thị chi tiết của đợt chạy đang chọn lên khung Detail Card."""
        self._selected_entry = entry

        # Tiêu đề
        self.lbl_detail_title.setText(f"CHI TIẾT ĐỢT CHẠY: {entry.run_id}")
        self.lbl_detail_dir.setText(f"📂 {entry.run_dir}")

        # Cột 1
        self.lbl_info_channel.setText(f"<b>Kênh:</b> {entry.channel_name} (<code>{entry.channel_id}</code>)")
        self.lbl_info_period.setText(f"<b>Phạm vi:</b> {entry.display_period}")
        self.lbl_info_created.setText(f"<b>Thời điểm cào:</b> {format_iso_to_display(entry.created_at)}")

        # Cột 2
        recon_icon = "✓ Khớp" if entry.reconciled else "⚠️ Lệch"
        self.lbl_info_metrics.setText(
            f"<b>Số liệu:</b> {entry.video_count} video | {entry.daily_metrics_count} chuỗi ngày | {format_bytes_to_human(entry.total_size_bytes)}"
        )
        self.lbl_info_quality.setText(
            f"<b>Kiểm định:</b> Điểm hoàn thiện {entry.completeness_score_percent}% | {entry.total_warnings} cảnh báo, {entry.total_errors} lỗi ({recon_icon})"
        )
        self.lbl_info_files.setText(
            f"<b>Tệp tin:</b> {entry.raw_files_count} file gốc raw/ | {entry.evidence_files_count} ảnh evidence/ | CSV & JSONL"
        )

        # Bật/tắt các nút hành động tương ứng
        self.btn_detail_readme.setEnabled(True)
        self.btn_detail_open_folder.setEnabled(True)
        self.btn_detail_open_csv.setEnabled(entry.has_videos_csv)
        self.btn_detail_open_evidence.setEnabled(entry.has_evidence)
        self.btn_detail_rebuild.setEnabled(True)

    def _clear_detail_card(self) -> None:
        """Xóa trắng nội dung card chi tiết khi không có lựa chọn."""
        self._selected_entry = None
        self.lbl_detail_title.setText("CHI TIẾT LẦN CHẠY: (Chưa có đợt chạy nào được chọn)")
        self.lbl_detail_dir.setText("")
        self.lbl_info_channel.setText("Kênh: -")
        self.lbl_info_period.setText("Phạm vi: -")
        self.lbl_info_created.setText("Thời điểm: -")
        self.lbl_info_metrics.setText("Số liệu: -")
        self.lbl_info_quality.setText("Kiểm định: -")
        self.lbl_info_files.setText("Tệp tin: -")

        self.btn_detail_readme.setEnabled(False)
        self.btn_detail_open_folder.setEnabled(False)
        self.btn_detail_open_csv.setEnabled(False)
        self.btn_detail_open_evidence.setEnabled(False)
        self.btn_detail_rebuild.setEnabled(False)

    # =========================================================================
    # 4.6. CÁC HÀNH ĐỘNG TƯƠNG TÁC (ACTIONS)
    # =========================================================================

    def _on_open_runs_folder(self) -> None:
        """Mở thư mục runs/ gốc trong File Explorer."""
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        open_path_in_system(self.runs_dir)

    def _view_readme(self, entry: RunEntry) -> None:
        """Mở dialog xem README của một đợt chạy."""
        dialog = ReadmeViewerDialog(run_entry=entry, parent=self)
        dialog.exec()

    def _on_view_selected_readme(self) -> None:
        if self._selected_entry:
            self._view_readme(self._selected_entry)

    def _on_open_selected_folder(self) -> None:
        if self._selected_entry:
            open_path_in_system(self._selected_entry.run_dir)

    def _on_open_selected_csv(self) -> None:
        if self._selected_entry and self._selected_entry.has_videos_csv:
            csv_path = self._selected_entry.run_dir / "data" / "videos.csv"
            open_path_in_system(csv_path)

    def _on_open_selected_evidence(self) -> None:
        if self._selected_entry:
            evidence_dir = self._selected_entry.run_dir / "evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            open_path_in_system(evidence_dir)

    def _on_rebuild_selected_reports(self) -> None:
        """Tạo lại toàn bộ báo cáo (quality_report.json, manifest.json, README.md)."""
        if not self._selected_entry:
            return

        run_path = self._selected_entry.run_dir
        try:
            build_run_reports(run_path)
            QMessageBox.information(
                self,
                "Tạo Lại Báo Cáo Thành Công",
                f"Đã cập nhật lại đầy đủ README.md, manifest.json và quality_report.json cho đợt chạy:\n{run_path.name}",
            )
            # Tải lại danh sách để cập nhật các số liệu mới nhất
            self.reload_runs()
        except Exception as ex:
            logger.error("Lỗi khi tạo lại báo cáo cho %s: %s", run_path, ex)
            QMessageBox.critical(
                self,
                "Lỗi Tạo Báo Cáo",
                f"Không thể tạo lại báo cáo: {ex}",
            )

    def get_selected_run(self) -> Optional[RunEntry]:
        """Lấy RunEntry đang được chọn (phục vụ test và automation)."""
        return self._selected_entry
