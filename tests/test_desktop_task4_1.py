"""Tests for Task 4.1: UI Architecture and Soft Blue Stylesheet."""

import os
import sys
import unittest
from pathlib import Path

# Ensure src in sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Use offscreen platform for Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from ytb_gpm_collector.interfaces.desktop.theme import (
    COLOR_BG_MAIN,
    COLOR_BG_SIDEBAR,
    COLOR_PRIMARY,
    get_application_stylesheet,
)
from ytb_gpm_collector.interfaces.desktop.sidebar import SidebarWidget
from ytb_gpm_collector.interfaces.desktop.main_window import MainWindow
from ytb_gpm_collector.interfaces.desktop.pages.collector_page import CollectorPage
from ytb_gpm_collector.interfaces.desktop.pages.history_page import HistoryPage
from ytb_gpm_collector.interfaces.desktop.pages.logs_page import LogsPage
from ytb_gpm_collector.interfaces.desktop.pages.settings_page import SettingsPage
from ytb_gpm_collector.interfaces.desktop.app import create_application


class TestDesktopTask41(unittest.TestCase):
    """Test suite for UI Architecture and Soft Blue Theme (Task 4.1)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def test_theme_stylesheet_contains_core_tokens(self):
        """Kiểm tra bộ QSS có đầy đủ các mã màu chuẩn Soft Blue và Navy Slate."""
        qss = get_application_stylesheet()
        self.assertIsInstance(qss, str)
        self.assertGreater(len(qss), 1000)

        # Kiểm tra màu nền chính và sidebar
        self.assertIn(COLOR_BG_MAIN, qss)  # #F1F5F9
        self.assertIn(COLOR_BG_SIDEBAR, qss)  # #1E293B
        self.assertIn(COLOR_PRIMARY, qss)  # #2563EB

        # Kiểm tra các selector quan trọng
        self.assertIn("QMainWindow", qss)
        self.assertIn("sidebarWidget", qss)
        self.assertIn("nav-btn", qss)
        self.assertIn("card", qss)
        self.assertIn("liveLogsTerminal", qss)
        self.assertIn("QProgressBar", qss)
        self.assertIn("QTableWidget", qss)

    def test_sidebar_widget(self):
        """Kiểm tra cấu trúc và tính năng của SidebarWidget."""
        sidebar = SidebarWidget()
        self.assertEqual(sidebar.width(), 230)
        self.assertEqual(len(sidebar.nav_buttons), 4)

        # Mặc định tab 0 (Thu thập) được chọn
        self.assertEqual(sidebar.button_group.checkedId(), 0)

        # Kiểm tra phát tín hiệu khi chuyển tab
        received_tabs = []
        sidebar.tab_changed.connect(lambda idx: received_tabs.append(idx))

        sidebar.set_current_tab(2)
        self.assertEqual(sidebar.button_group.checkedId(), 2)

        # Click nút tab 1
        sidebar.nav_buttons[1].click()
        self.assertIn(1, received_tabs)

        # Kiểm tra cập nhật trạng thái GPM
        sidebar.set_gpm_status(19996, True, "Sẵn sàng")
        self.assertIn("19996", sidebar.port_label.text())
        self.assertIn("Sẵn sàng", sidebar.status_text.text())

        sidebar.set_gpm_status(9495, False, "Chưa kết nối")
        self.assertIn("9495", sidebar.port_label.text())
        self.assertIn("Chưa kết nối", sidebar.status_text.text())

    def test_main_window_architecture(self):
        """Kiểm tra kiến trúc MainWindow gồm Sidebar bên trái và QStackedWidget bên phải."""
        window = MainWindow()

        # Kiểm tra tiêu đề cửa sổ
        self.assertIn("YTB Studio Data Collector", window.windowTitle())
        self.assertIn("GPM Automation", window.windowTitle())

        # Kiểm tra kích thước tối thiểu
        self.assertGreaterEqual(window.minimumWidth(), 1024)
        self.assertGreaterEqual(window.minimumHeight(), 680)

        # Kiểm tra QStackedWidget có đủ 4 trang
        stack = window.content_stack
        self.assertEqual(stack.count(), 4)
        self.assertIsInstance(stack.widget(0), CollectorPage)
        self.assertIsInstance(stack.widget(1), HistoryPage)
        self.assertIsInstance(stack.widget(2), LogsPage)
        self.assertIsInstance(stack.widget(3), SettingsPage)

        # Chuyển tab qua sidebar
        window.sidebar.tab_changed.emit(1)
        self.assertEqual(stack.currentIndex(), 1)

        window.sidebar.tab_changed.emit(3)
        self.assertEqual(stack.currentIndex(), 3)

        # Chuyển tab qua hàm switch_to_tab
        window.switch_to_tab(0)
        self.assertEqual(stack.currentIndex(), 0)
        self.assertEqual(window.sidebar.button_group.checkedId(), 0)

        window.switch_to_tab(2)
        self.assertEqual(stack.currentIndex(), 2)
        self.assertEqual(window.sidebar.button_group.checkedId(), 2)

    def test_check_gpm_status(self):
        """Kiểm tra hàm check_gpm_status không gây crash ứng dụng."""
        window = MainWindow()
        res = window.check_gpm_status()
        self.assertIsInstance(res, bool)

    def test_create_application(self):
        """Kiểm tra khởi tạo QApplication với stylesheet và thông tin metadata."""
        app = create_application()
        self.assertEqual(app.applicationName(), "YTB Studio Data Collector")
        self.assertGreater(len(app.styleSheet()), 500)


if __name__ == "__main__":
    unittest.main()
