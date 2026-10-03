"""Unit tests for Task 4.5: Tab 4 - Cài đặt hệ thống (SettingsPage)."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure src in sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Headless Qt platform for offscreen testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from ytb_gpm_collector.config import AppConfig
from ytb_gpm_collector.integrations.storage.history import LocalStorage
from ytb_gpm_collector.interfaces.desktop.pages.settings_page import SettingsPage


class TestSettingsPageTask45(unittest.TestCase):
    """Bộ kiểm thử cho Tab 4: Cài đặt hệ thống (Task 4.5)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_ytb_task45_"))
        self.storage = LocalStorage(self.test_dir / "state" / "app_state.db")
        self.custom_config = AppConfig(
            api_port=19996,
            runs_dir=self.test_dir / "custom_runs",
            default_concurrency=3,
            timeout_seconds=45.0,
            keep_raw_files=True,
            auto_generate_reports=True,
        )
        self.page = SettingsPage(
            parent=None,
            config=self.custom_config,
            history_storage=self.storage,
        )

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_ui_structure_and_form_controls(self):
        """Kiểm tra đầy đủ các trường nhập liệu và nút bấm trên SettingsPage."""
        # Khối GPM
        self.assertIsNotNone(self.page.spin_port)
        self.assertIsNotNone(self.page.btn_detect_port)
        self.assertIsNotNone(self.page.btn_ping_api)
        self.assertIsNotNone(self.page.lbl_ping_status)
        self.assertIsNotNone(self.page.input_setting_dat)
        self.assertIsNotNone(self.page.input_db_path)

        # Khối Automation & Lưu trữ
        self.assertIsNotNone(self.page.input_runs_dir)
        self.assertIsNotNone(self.page.btn_browse_runs)
        self.assertIsNotNone(self.page.spin_concurrency)
        self.assertIsNotNone(self.page.spin_timeout)
        self.assertIsNotNone(self.page.cb_keep_raw)
        self.assertIsNotNone(self.page.cb_auto_reports)

        # Nút điều khiển lưu
        self.assertIsNotNone(self.page.btn_save)
        self.assertIsNotNone(self.page.btn_reset)
        self.assertIsNotNone(self.page.lbl_save_status)

    def test_02_load_settings(self):
        """Kiểm tra nạp thông số cấu hình ban đầu lên giao diện."""
        self.assertEqual(self.page.spin_port.value(), 19996)
        self.assertEqual(self.page.input_runs_dir.text(), str((self.test_dir / "custom_runs").resolve()))
        self.assertEqual(self.page.spin_concurrency.value(), 3)
        self.assertEqual(self.page.spin_timeout.value(), 45)
        self.assertTrue(self.page.cb_keep_raw.isChecked())
        self.assertTrue(self.page.cb_auto_reports.isChecked())

    def test_03_save_settings_and_emit_signal(self):
        """Kiểm tra thay đổi giá trị và nhấn Lưu Cài Đặt phát tín hiệu và ghi SQLite."""
        # Đổi giá trị trên form
        self.page.spin_port.setValue(9495)
        new_runs_dir = str((self.test_dir / "new_runs").resolve())
        self.page.input_runs_dir.setText(new_runs_dir)
        self.page.spin_concurrency.setValue(4)
        self.page.spin_timeout.setValue(60)
        self.page.cb_keep_raw.setChecked(False)

        saved_signals = []
        self.page.settings_saved.connect(lambda s: saved_signals.append(s))

        # Nhấn Lưu Cài Đặt
        self.page.btn_save.click()

        # Kiểm tra phát tín hiệu
        self.assertEqual(len(saved_signals), 1)
        emitted = saved_signals[0]
        self.assertEqual(emitted["api_port"], 9495)
        self.assertEqual(emitted["runs_dir"], new_runs_dir)
        self.assertEqual(emitted["default_concurrency"], 4)
        self.assertEqual(emitted["timeout_seconds"], 60.0)
        self.assertFalse(emitted["keep_raw_files"])
        self.assertIn("thành công", self.page.lbl_save_status.text())

        # Kiểm tra nạp lại từ SQLite khớp 100%
        reloaded_config = AppConfig.load_from_storage(self.storage)
        self.assertEqual(reloaded_config.api_port, 9495)
        self.assertEqual(reloaded_config.default_concurrency, 4)
        self.assertEqual(reloaded_config.timeout_seconds, 60.0)
        self.assertFalse(reloaded_config.keep_raw_files)

    @patch("ytb_gpm_collector.integrations.gpm.client.GpmClient.check_connection")
    def test_04_ping_gpm_api_success_and_failure(self, mock_check):
        """Kiểm tra nút Ping API cập nhật nhãn trạng thái kết nối."""
        # 1. Giả lập kết nối thành công
        mock_check.return_value = True
        connected = self.page.ping_gpm_api()
        self.assertTrue(connected)
        self.assertIn("Kết nối thành công", self.page.lbl_ping_status.text())
        self.assertIn("Online", self.page.lbl_ping_status.text())

        # 2. Giả lập kết nối thất bại
        mock_check.return_value = False
        connected = self.page.ping_gpm_api()
        self.assertFalse(connected)
        self.assertIn("Không thể kết nối", self.page.lbl_ping_status.text())
        self.assertIn("Offline", self.page.lbl_ping_status.text())

    @patch("ytb_gpm_collector.interfaces.desktop.pages.settings_page.read_gpm_api_port_from_setting")
    def test_05_auto_detect_port(self, mock_read_port):
        """Kiểm tra nút tự động dò tìm cổng gán giá trị cổng phát hiện được."""
        mock_read_port.return_value = 9495
        with patch.object(self.page, "ping_gpm_api") as mock_ping:
            self.page.auto_detect_port()
            self.assertEqual(self.page.spin_port.value(), 9495)
            mock_ping.assert_called_once()


if __name__ == "__main__":
    unittest.main()
