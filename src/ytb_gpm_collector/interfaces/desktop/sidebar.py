"""Sidebar navigation widget for YTB GPM Collector.

Implements the Navy Slate (#1E293B) vertical navigation bar with:
- Brand header (title, subtitle, badge)
- 4 Navigation buttons (Thu thập, Lịch sử, Nhật ký, Cài đặt)
- Bottom GPM connection status card with live indicator LED
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QButtonGroup,
    QSpacerItem,
    QSizePolicy,
    QFrame,
)

from ytb_gpm_collector.interfaces.desktop.theme import (
    COLOR_BG_SIDEBAR,
    COLOR_SUCCESS,
    COLOR_DANGER,
    COLOR_WARNING,
    COLOR_TEXT_SIDEBAR_MUTED,
)


class SidebarWidget(QWidget):
    """Thanh điều hướng Sidebar bên trái (Navy Slate #1E293B)."""

    tab_changed = Signal(int)
    refresh_connection_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("sidebarWidget")
        self.setFixedWidth(230)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(6)

        # 1. Header (Brand & App Title)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        top_brand_row = QHBoxLayout()
        top_brand_row.setSpacing(8)

        # Brand Icon Badge
        brand_icon = QLabel("▶")
        brand_icon.setAlignment(Qt.AlignCenter)
        brand_icon.setFixedSize(28, 28)
        brand_icon.setStyleSheet(
            "background-color: #DC2626; color: #FFFFFF; font-size: 13px; font-weight: bold; border-radius: 6px;"
        )
        top_brand_row.addWidget(brand_icon)

        # Brand Title
        title_label = QLabel("YTB COLLECT")
        title_label.setObjectName("sidebarBrandTitle")
        top_brand_row.addWidget(title_label)
        top_brand_row.addStretch()

        # Version Badge
        v_badge = QLabel("v1.0")
        v_badge.setObjectName("sidebarBrandBadge")
        top_brand_row.addWidget(v_badge)

        header_layout.addLayout(top_brand_row)

        # Subtitle
        sub_label = QLabel("GPM AUTOMATION EDITION")
        sub_label.setObjectName("sidebarBrandSubtitle")
        header_layout.addWidget(sub_label)

        layout.addLayout(header_layout)
        layout.addSpacing(16)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #334155; max-height: 1px; border: none;")
        layout.addWidget(sep)
        layout.addSpacing(12)

        # 2. Navigation Button Group
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        nav_items = [
            (0, "📥  Thu thập dữ liệu", "btn_nav_collector"),
            (1, "📊  Lịch sử && Kết quả", "btn_nav_history"),
            (2, "📝  Nhật ký Logs", "btn_nav_logs"),
            (3, "⚙️  Cài đặt", "btn_nav_settings"),
        ]

        self.nav_buttons = []
        for idx, text, obj_name in nav_items:
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.setProperty("class", "nav-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            if idx == 0:
                btn.setChecked(True)
            self.button_group.addButton(btn, idx)
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.button_group.idClicked.connect(self._on_button_clicked)

        # Spacer to push status card to bottom
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 3. GPM Connection Status Card (at the bottom)
        self.status_card = QFrame()
        self.status_card.setObjectName("sidebarStatusCard")
        status_card_layout = QVBoxLayout(self.status_card)
        status_card_layout.setContentsMargins(10, 10, 10, 10)
        status_card_layout.setSpacing(6)

        status_header_row = QHBoxLayout()
        status_header_row.setSpacing(6)

        # LED Indicator Dot
        self.led_dot = QLabel("●")
        self.led_dot.setFixedSize(14, 14)
        self.led_dot.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 13px;")
        status_header_row.addWidget(self.led_dot)

        # Port Info Label
        self.port_label = QLabel("GPM API: Đang kiểm tra")
        self.port_label.setObjectName("sidebarStatusPort")
        status_header_row.addWidget(self.port_label)
        status_header_row.addStretch()

        status_card_layout.addLayout(status_header_row)

        # Status text + Refresh Button Row
        status_bottom_row = QHBoxLayout()
        status_bottom_row.setSpacing(4)

        self.status_text = QLabel("Đang kết nối...")
        self.status_text.setObjectName("sidebarStatusText")
        status_bottom_row.addWidget(self.status_text)
        status_bottom_row.addStretch()

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setToolTip("Kiểm tra lại kết nối GPM API")
        self.btn_refresh.setFixedSize(22, 22)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(
            "background-color: #1E293B; color: #94A3B8; border: 1px solid #334155; "
            "border-radius: 4px; font-weight: bold; font-size: 12px; padding: 0px;"
        )
        self.btn_refresh.clicked.connect(self.refresh_connection_requested.emit)
        status_bottom_row.addWidget(self.btn_refresh)

        status_card_layout.addLayout(status_bottom_row)

        layout.addWidget(self.status_card)

    def _on_button_clicked(self, tab_id: int) -> None:
        self.tab_changed.emit(tab_id)

    def set_current_tab(self, tab_id: int) -> None:
        """Đổi tab điều hướng theo mã index (0-3)."""
        btn = self.button_group.button(tab_id)
        if btn:
            btn.setChecked(True)

    def set_gpm_status(self, port: int, connected: bool, message: str = "") -> None:
        """Cập nhật đèn trạng thái và thông tin kết nối GPM."""
        self.port_label.setText(f"GPM API: {port}")
        if connected:
            self.led_dot.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: 13px;")
            self.status_text.setText(message or "Sẵn sàng (Online)")
            self.status_text.setStyleSheet(f"color: #86EFAC; font-size: 11px;")
        else:
            self.led_dot.setStyleSheet(f"color: {COLOR_DANGER}; font-size: 13px;")
            self.status_text.setText(message or "Chưa kết nối (Offline)")
            self.status_text.setStyleSheet(f"color: #FCA5A5; font-size: 11px;")
