"""Logs Page view (Tab 3: Nhật ký hoạt động).

Triển khai hoàn chỉnh Task 4.4:
- Khung hiển thị Live Logs màu sắc trực quan (INFO, SUCCESS, WARNING, ERROR).
- Nền tối dịu mắt (#0F172A) với font chữ Monospace Consolas thẳng hàng, chuẩn WCAG AA.
- Tự động nhận diện mức log và gắn màu sắc:
  + [INFO]: Xanh dương dịu (#38BDF8 / #60A5FA)
  + [SUCCESS]: Xanh ngọc lục bảo Emerald (#34D399)
  + [WARNING]: Vàng cam Amber (#FBBF24)
  + [ERROR]: Đỏ Crimson (#F87171)
  + [TIMESTAMP] & Thẻ luồng: Xám nhạt (#94A3B8) và Tím (#C084FC)
- Thanh công cụ đầy đủ:
  + Nút "📋 Sao chép toàn bộ" (Copy all vào Clipboard)
  + Nút "🗑️ Xóa nhật ký" (Clear logs)
  + Checkbox "Tự động cuộn theo dòng mới" (Auto-scroll)
  + Bộ lọc cấp độ log (Tất cả, INFO, SUCCESS, WARNING, ERROR)
  + Ô tìm kiếm từ khóa real-time
  + Nút "💾 Lưu file log..." (Export file text)
- Tích hợp chuẩn QtLogHandler kết nối logging hệ thống Python vào UI thread an toàn.
"""

import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Union

from PySide6.QtCore import Qt, Signal, Slot, QObject
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QListView,
    QTextEdit,
    QFileDialog,
    QApplication,
    QMessageBox,
)

from ytb_gpm_collector.interfaces.desktop.theme import (
    COLOR_BG_DARK_LOG,
    COLOR_BORDER_LIGHT,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_MONO,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. BẢNG MÀU LOG TERMINAL (HIGH CONTRAST & SOFT BLUE THEME)
# ==============================================================================

LOG_COLOR_TIMESTAMP = "#94A3B8"  # Slate Muted
LOG_COLOR_INFO = "#38BDF8"       # Sky Blue sáng
LOG_COLOR_SUCCESS = "#34D399"    # Emerald Green sáng
LOG_COLOR_WARNING = "#FBBF24"    # Amber Yellow sáng
LOG_COLOR_ERROR = "#F87171"      # Crimson Red sáng
LOG_COLOR_WORKER = "#C084FC"     # Purple luồng
LOG_COLOR_SYSTEM = "#818CF8"     # Indigo hệ thống
LOG_COLOR_BODY = "#F8FAFC"       # Light Slate Text


# ==============================================================================
# 2. CẤU TRÚC BẢN GHI LOG (LOG RECORD DATA)
# ==============================================================================

@dataclass
class LogItem:
    """Một dòng nhật ký lưu trữ."""
    raw_message: str
    level: str  # INFO, SUCCESS, WARNING, ERROR
    timestamp: str  # HH:MM:SS
    formatted_html: str
    plain_text: str


def detect_log_level(message: str, default_level: str = "INFO") -> str:
    """Tự động phân tích và xác định mức độ log từ nội dung tin nhắn."""
    msg_upper = message.upper()

    if "[ERROR]" in msg_upper or "[LỖI]" in msg_upper or "CRITICAL" in msg_upper or "EXCEPTION" in msg_upper:
        return "ERROR"
    elif "[WARN]" in msg_upper or "[WARNING]" in msg_upper or "[CẢNH BÁO]" in msg_upper:
        return "WARNING"
    elif "[SUCCESS]" in msg_upper or "[THÀNH CÔNG]" in msg_upper or "HOÀN TẤT 100%" in msg_upper:
        return "SUCCESS"
    elif "[INFO]" in msg_upper or "[THÔNG TIN]" in msg_upper:
        return "INFO"

    # Nhận diện theo từ khóa ngữ nghĩa
    lower = message.lower()
    if any(k in lower for k in ["lỗi", "error", "failed", "crash", "bị từ chối"]):
        return "ERROR"
    elif any(k in lower for k in ["cảnh báo", "warning", "thiếu", "chưa thể kết nối", "offline"]):
        return "WARNING"
    elif any(k in lower for k in ["thành công", "success", "sẵn sàng", "hoàn tất", "đã lưu", "chuẩn hóa thành công"]):
        return "SUCCESS"

    return default_level.upper()


def format_log_to_html(timestamp: str, level: str, message: str) -> str:
    """Tạo chuỗi HTML có màu sắc nổi bật cho từng thành phần của dòng log."""
    # Chọn màu cho badge level
    if level == "SUCCESS":
        lvl_color = LOG_COLOR_SUCCESS
        lvl_tag = "SUCCESS"
    elif level == "WARNING":
        lvl_color = LOG_COLOR_WARNING
        lvl_tag = "WARN"
    elif level == "ERROR":
        lvl_color = LOG_COLOR_ERROR
        lvl_tag = "ERROR"
    else:
        lvl_color = LOG_COLOR_INFO
        lvl_tag = "INFO"

    # Lọc bỏ các tag cấp độ thừa đã có trong chuỗi gốc để tránh lặp [INFO] [INFO]
    clean_msg = message
    clean_msg = re.sub(r"^\[(INFO|SUCCESS|WARN|WARNING|ERROR|THÀNH CÔNG|LỖI|CẢNH BÁO)\]\s*", "", clean_msg, flags=re.IGNORECASE)

    # Escape HTML để an toàn
    escaped_msg = html.escape(clean_msg)

    # Tô màu thẻ luồng [Luồng X] hoặc [Worker X] nếu có
    escaped_msg = re.sub(
        r"(\[(Luồng \d+|Worker \d+|Profile [^\]]+)\])",
        rf'<span style="color:{LOG_COLOR_WORKER}; font-weight:600;">\1</span>',
        escaped_msg,
    )

    # Tô màu thẻ hệ thống [HỆ THỐNG] hoặc [SẴN SÀNG]
    escaped_msg = re.sub(
        r"(\[(HỆ THỐNG|SẴN SÀNG|GPM|CDP)\])",
        rf'<span style="color:{LOG_COLOR_SYSTEM}; font-weight:600;">\1</span>',
        escaped_msg,
    )

    html_line = (
        f'<span style="color:{LOG_COLOR_TIMESTAMP};">[{timestamp}]</span> '
        f'<span style="color:{lvl_color}; font-weight:bold;">[{lvl_tag}]</span> '
        f'<span style="color:{LOG_COLOR_BODY};">{escaped_msg}</span>'
    )
    return html_line


# ==============================================================================
# 3. TERMINAL WIDGET TÙY BIẾN CHO PHÉP TƯƠNG THÍCH APPENDPLAINTEXT
# ==============================================================================

class LiveLogTerminal(QTextEdit):
    """QTextEdit tùy biến với Dark Theme (#0F172A) và hỗ trợ appendPlainText."""

    def __init__(self, logs_page: "LogsPage", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logs_page = logs_page
        self.setObjectName("liveLogsTerminal")
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit#liveLogsTerminal {{
                background-color: {COLOR_BG_DARK_LOG};
                color: {LOG_COLOR_BODY};
                border: 1px solid #1E293B;
                border-radius: 8px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 12px;
                line-height: 1.45;
                padding: 12px;
                selection-background-color: #334155;
            }}
        """)

    def appendPlainText(self, text: str) -> None:
        """Hàm tương thích ngược với QPlainTextEdit."""
        self.logs_page.append_log(text)


# ==============================================================================
# 4. GIAO DIỆN CHÍNH TAB 3: NHẬT KÝ HOẠT ĐỘNG (LOGS PAGE)
# ==============================================================================

class LogsPage(QWidget):
    """Màn hình Nhật ký hoạt động (Live Logs) - Tab 3."""

    # Signal phát ra khi có dòng log mới được thêm vào
    log_added = Signal(str, str)  # (level, text)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "page-container")

        self._all_logs: List[LogItem] = []
        self._counts = {"INFO": 0, "SUCCESS": 0, "WARNING": 0, "ERROR": 0}

        self._init_ui()
        self._wire_signals()

        # Thông báo khởi tạo mặc định
        self.append_log("[HỆ THỐNG] Khởi tạo giao diện Desktop YTB GPM Collector thành công.", level="INFO")
        self.append_log("[SẴN SÀNG] Đang chờ cấu hình và lệnh thu thập từ người dùng...", level="SUCCESS")

    # =========================================================================
    # 4.1. KHỞI TẠO BỐ CỤC GIAO DIỆN
    # =========================================================================

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(12)

        # 1. Thanh Header & Subtitle
        header_row = QHBoxLayout()
        header_layout = QVBoxLayout()
        header_layout.setSpacing(3)

        title = QLabel("Nhật ký hoạt động (Live Logs)")
        title.setProperty("class", "page-title")
        header_layout.addWidget(title)

        subtitle = QLabel("Ghi nhận chi tiết từng bước điều hướng, tải trang, xuất file và chuẩn hóa dữ liệu")
        subtitle.setProperty("class", "page-subtitle")
        header_layout.addWidget(subtitle)
        header_row.addLayout(header_layout)

        header_row.addStretch()

        # Checkbox Auto-scroll
        self.cb_autoscroll = QCheckBox("Tự động cuộn")
        self.cb_autoscroll.setChecked(True)
        self.cb_autoscroll.setToolTip("Tự động cuộn xuống cuối màn hình khi có dòng log mới")
        header_row.addWidget(self.cb_autoscroll)

        # Nút Sao chép
        self.btn_copy = QPushButton("📋 Sao chép")
        self.btn_copy.setToolTip("Sao chép toàn bộ nhật ký đang hiển thị vào Clipboard")
        header_row.addWidget(self.btn_copy)

        # Nút Lưu file log
        self.btn_save = QPushButton("💾 Lưu log...")
        self.btn_save.setToolTip("Lưu toàn bộ nhật ký thành tệp tin văn bản (.log / .txt)")
        header_row.addWidget(self.btn_save)

        # Nút Xóa log
        self.btn_clear = QPushButton("🗑️ Xóa log")
        self.btn_clear.setToolTip("Xóa sạch toàn bộ nội dung nhật ký hiện tại")
        header_row.addWidget(self.btn_clear)

        main_layout.addLayout(header_row)

        # 2. Thanh lọc và thống kê (Filter Toolbar)
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        # Bộ lọc cấp độ ComboBox
        self.combo_level = QComboBox()
        self.combo_level.setView(QListView())
        self.combo_level.addItem("Tất cả mức độ", "")
        self.combo_level.addItem("ℹ️ INFO (Thông tin)", "INFO")
        self.combo_level.addItem("✅ SUCCESS (Thành công)", "SUCCESS")
        self.combo_level.addItem("⚠️ WARNING (Cảnh báo)", "WARNING")
        self.combo_level.addItem("❌ ERROR (Lỗi)", "ERROR")
        self.combo_level.setMaximumWidth(190)
        filter_bar.addWidget(self.combo_level)

        # Ô tìm kiếm từ khóa
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Lọc từ khóa trong log...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMaximumWidth(280)
        filter_bar.addWidget(self.search_input)

        filter_bar.addStretch()

        # Nhãn thống kê số lượng dòng log theo cấp độ
        self.lbl_stats = QLabel("0 dòng log")
        self.lbl_stats.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        filter_bar.addWidget(self.lbl_stats)

        main_layout.addLayout(filter_bar)

        # 3. Khung hiển thị Dark Terminal
        self.log_terminal = LiveLogTerminal(logs_page=self, parent=self)
        main_layout.addWidget(self.log_terminal)

    # =========================================================================
    # 4.2. KẾT NỐI SỰ KIỆN (SIGNALS)
    # =========================================================================

    def _wire_signals(self) -> None:
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        self.btn_save.clicked.connect(self._on_save_logs_dialog)
        self.btn_clear.clicked.connect(self.clear_logs)
        self.combo_level.currentIndexChanged.connect(self._apply_filters)
        self.search_input.textChanged.connect(self._apply_filters)

    # =========================================================================
    # 4.3. THÊM VÀ HIỂN THỊ LOG (LOGGING ENGINE)
    # =========================================================================

    def append_log(
        self,
        message: str,
        level: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """
        Thêm một dòng log mới vào hệ thống.
        Tự động phân loại màu sắc, lưu trữ và cuộn trang nếu bật auto-scroll.
        """
        if not message:
            return

        ts = timestamp or datetime.now().strftime("%H:%M:%S")
        lvl = (level or detect_log_level(message)).upper()
        if lvl not in ["INFO", "SUCCESS", "WARNING", "ERROR"]:
            lvl = "INFO"

        html_formatted = format_log_to_html(timestamp=ts, level=lvl, message=message)
        plain_formatted = f"[{ts}] [{lvl}] {message}"

        log_item = LogItem(
            raw_message=message,
            level=lvl,
            timestamp=ts,
            formatted_html=html_formatted,
            plain_text=plain_formatted,
        )

        self._all_logs.append(log_item)
        self._counts[lvl] = self._counts.get(lvl, 0) + 1

        self._update_stats_label()

        # Kiểm tra xem dòng mới có thỏa mãn bộ lọc hiện tại hay không
        if self._matches_filter(log_item):
            self.log_terminal.append(html_formatted)
            if self.cb_autoscroll.isChecked():
                self._scroll_to_bottom()

        self.log_added.emit(lvl, message)

    def append_plain_text(self, text: str) -> None:
        """Hàm dự phòng tương thích với code cũ."""
        self.append_log(text)

    def info(self, message: str) -> None:
        """Ghi nhận log INFO."""
        self.append_log(message, level="INFO")

    def success(self, message: str) -> None:
        """Ghi nhận log SUCCESS."""
        self.append_log(message, level="SUCCESS")

    def warning(self, message: str) -> None:
        """Ghi nhận log WARNING."""
        self.append_log(message, level="WARNING")

    def error(self, message: str) -> None:
        """Ghi nhận log ERROR."""
        self.append_log(message, level="ERROR")

    # =========================================================================
    # 4.4. BỘ LỌC TÌM KIẾM & PHÂN LOẠI
    # =========================================================================

    def _matches_filter(self, item: LogItem) -> bool:
        """Kiểm tra một LogItem có phù hợp với bộ lọc level và từ khóa hiện tại không."""
        filter_level = self.combo_level.currentData()
        if filter_level and item.level != filter_level:
            return False

        search_query = self.search_input.text().strip().lower()
        if search_query:
            if search_query not in item.raw_message.lower():
                return False

        return True

    def _apply_filters(self) -> None:
        """Áp dụng lại bộ lọc cho toàn bộ danh sách log trong bộ nhớ."""
        self.log_terminal.clear()

        matched_items = [item for item in self._all_logs if self._matches_filter(item)]
        if matched_items:
            # Gộp nhiều dòng HTML để append một lần giúp tối ưu hiệu năng
            combined_html = "<br>".join(item.formatted_html for item in matched_items)
            self.log_terminal.setHtml(combined_html)
            if self.cb_autoscroll.isChecked():
                self._scroll_to_bottom()

        self._update_stats_label(filtered_count=len(matched_items))

    def _scroll_to_bottom(self) -> None:
        """Cuộn thanh cuộn xuống cuối cùng."""
        scrollbar = self.log_terminal.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _update_stats_label(self, filtered_count: Optional[int] = None) -> None:
        """Cập nhật nhãn thống kê tổng số dòng và từng loại."""
        total = len(self._all_logs)
        c = self._counts
        if filtered_count is not None and filtered_count < total:
            self.lbl_stats.setText(
                f"Hiển thị {filtered_count}/{total} dòng | {c['INFO']} INFO • {c['SUCCESS']} SUCCESS • {c['WARNING']} WARN • {c['ERROR']} ERROR"
            )
        else:
            self.lbl_stats.setText(
                f"Tổng: {total} dòng | {c['INFO']} INFO • {c['SUCCESS']} SUCCESS • {c['WARNING']} WARN • {c['ERROR']} ERROR"
            )

    # =========================================================================
    # 4.5. CÁC THAO TÁC CÔNG CỤ (CLEAR, COPY, EXPORT)
    # =========================================================================

    def clear_logs(self) -> None:
        """Xóa trắng toàn bộ nhật ký."""
        self._all_logs.clear()
        self._counts = {"INFO": 0, "SUCCESS": 0, "WARNING": 0, "ERROR": 0}
        self.log_terminal.clear()
        self._update_stats_label()

    def get_all_logs_text(self) -> str:
        """Lấy toàn bộ nội dung log hiện đang lọc dưới dạng plain text."""
        matched = [item.plain_text for item in self._all_logs if self._matches_filter(item)]
        return "\n".join(matched)

    def copy_to_clipboard(self) -> None:
        """Sao chép toàn bộ log đang hiển thị vào Clipboard."""
        text = self.get_all_logs_text()
        if not text:
            text = self.log_terminal.toPlainText()

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.lbl_stats.setText(f"✓ Đã sao chép {len(text.splitlines())} dòng vào bộ nhớ tạm!")

    def _on_save_logs_dialog(self) -> None:
        """Mở dialog lưu file log ra ổ đĩa."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"ytb_collector_logs_{timestamp}.txt"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu tệp tin nhật ký (Export Logs)",
            default_filename,
            "Text files (*.txt);;Log files (*.log);;All files (*.*)",
        )
        if filepath:
            success = self.save_to_file(filepath)
            if success:
                QMessageBox.information(
                    self,
                    "Lưu Log Thành Công",
                    f"Đã lưu tệp nhật ký thành công tại:\n{filepath}",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Lỗi Lưu Tệp",
                    f"Không thể ghi tệp tin tại:\n{filepath}",
                )

    def save_to_file(self, filepath: Union[Path, str]) -> bool:
        """Lưu toàn bộ log vào đường dẫn file chỉ định."""
        try:
            target = Path(filepath).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            text = self.get_all_logs_text()
            target.write_text(text, encoding="utf-8")
            logger.info("Đã lưu log ra file: %s", target)
            return True
        except Exception as ex:
            logger.error("Lỗi khi ghi file log %s: %s", filepath, ex)
            return False


# ==============================================================================
# 5. BỘ ĐIỀU PHỐI LOGGING CHUẨN PYTHON SANG QT (QT LOG HANDLER)
# ==============================================================================

class LogSignalEmitter(QObject):
    """QObject riêng biệt để phát tín hiệu an toàn luồng."""
    log_signal = Signal(str, str, str)  # (timestamp, level, message)


class QtLogHandler(logging.Handler):
    """
    Logging Handler chuẩn Python định tuyến mọi thông báo logger
    từ các luồng nền (Worker Threads / Playwright) về giao diện LogsPage an toàn.
    """

    def __init__(self, logs_page: LogsPage):
        super().__init__()
        self.emitter = LogSignalEmitter()
        self.emitter.log_signal.connect(logs_page.append_log)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

            # Xác định cấp độ
            if record.levelno >= logging.ERROR:
                lvl = "ERROR"
            elif record.levelno >= logging.WARNING:
                lvl = "WARNING"
            elif "thành công" in msg.lower() or "hoàn tất" in msg.lower() or "success" in msg.lower():
                lvl = "SUCCESS"
            else:
                lvl = "INFO"

            self.emitter.log_signal.emit(msg, lvl, ts)
        except Exception:
            self.handleError(record)


def setup_qt_logging(logs_page: LogsPage, logger_name: Optional[str] = "ytb_gpm_collector") -> QtLogHandler:
    """Gắn QtLogHandler vào logger hệ thống để tự động bắt log vào LogsPage."""
    handler = QtLogHandler(logs_page)
    handler.setFormatter(logging.Formatter("%(message)s"))
    target_logger = logging.getLogger(logger_name)
    target_logger.addHandler(handler)
    return handler
