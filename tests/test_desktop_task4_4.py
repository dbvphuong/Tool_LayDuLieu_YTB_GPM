"""Unit tests for Task 4.4: Tab 3 - Nhật ký hoạt động (LogsPage)."""

import logging
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure src in sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Headless Qt platform for offscreen testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from ytb_gpm_collector.interfaces.desktop.pages.logs_page import (
    LogsPage,
    detect_log_level,
    format_log_to_html,
    setup_qt_logging,
    LOG_COLOR_INFO,
    LOG_COLOR_SUCCESS,
    LOG_COLOR_WARNING,
    LOG_COLOR_ERROR,
)


class TestLogsPageTask44(unittest.TestCase):
    """Bộ kiểm thử toàn diện cho Tab 3: Nhật ký hoạt động (Task 4.4)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.page = LogsPage(parent=None)
        # Xóa các log mặc định để test từ trạng thái trống
        self.page.clear_logs()

    def test_01_ui_structure_and_components(self):
        """Kiểm tra cấu trúc giao diện và thanh công cụ của LogsPage."""
        # Kiểm tra các nút công cụ
        self.assertIsNotNone(self.page.btn_copy)
        self.assertIsNotNone(self.page.btn_save)
        self.assertIsNotNone(self.page.btn_clear)
        self.assertIsNotNone(self.page.cb_autoscroll)
        self.assertTrue(self.page.cb_autoscroll.isChecked())

        # Kiểm tra bộ lọc
        self.assertIsNotNone(self.page.combo_level)
        self.assertIsNotNone(self.page.search_input)
        self.assertIsNotNone(self.page.lbl_stats)

        # Kiểm tra khung terminal
        self.assertIsNotNone(self.page.log_terminal)
        self.assertEqual(self.page.log_terminal.objectName(), "liveLogsTerminal")
        self.assertTrue(self.page.log_terminal.isReadOnly())

    def test_02_detect_log_level(self):
        """Kiểm tra hàm nhận diện cấp độ log từ tin nhắn."""
        self.assertEqual(detect_log_level("[INFO] Khởi động trình duyệt"), "INFO")
        self.assertEqual(detect_log_level("[SUCCESS] Đã xuất file thành công"), "SUCCESS")
        self.assertEqual(detect_log_level("[WARN] Timeout tải trang"), "WARNING")
        self.assertEqual(detect_log_level("[ERROR] Mất kết nối CDP"), "ERROR")

        # Nhận diện ngữ nghĩa tiếng Việt
        self.assertEqual(detect_log_level("Chuẩn hóa thành công 10 video"), "SUCCESS")
        self.assertEqual(detect_log_level("Cảnh báo thiếu dữ liệu CTR"), "WARNING")
        self.assertEqual(detect_log_level("Gặp lỗi nghiêm trọng khi đọc file"), "ERROR")

    def test_03_format_log_to_html_colors(self):
        """Kiểm tra mã màu trong chuỗi HTML sinh ra."""
        html_info = format_log_to_html("12:00:00", "INFO", "Tin tức thông thường")
        self.assertIn(LOG_COLOR_INFO, html_info)
        self.assertIn("[INFO]", html_info)

        html_succ = format_log_to_html("12:00:01", "SUCCESS", "Đã xuất xong")
        self.assertIn(LOG_COLOR_SUCCESS, html_succ)
        self.assertIn("[SUCCESS]", html_succ)

        html_warn = format_log_to_html("12:00:02", "WARNING", "Tải trang chậm")
        self.assertIn(LOG_COLOR_WARNING, html_warn)
        self.assertIn("[WARN]", html_warn)

        html_err = format_log_to_html("12:00:03", "ERROR", "Lỗi mạng")
        self.assertIn(LOG_COLOR_ERROR, html_err)
        self.assertIn("[ERROR]", html_err)

    def test_04_append_log_and_stats_update(self):
        """Kiểm tra hàm append_log cập nhật bộ nhớ và nhãn thống kê."""
        self.page.append_log("Khởi động", level="INFO")
        self.page.append_log("Đã kết nối CDP", level="SUCCESS")
        self.page.append_log("Tải chậm", level="WARNING")
        self.page.append_log("Lỗi tải trang", level="ERROR")

        self.assertEqual(len(self.page._all_logs), 4)
        self.assertEqual(self.page._counts["INFO"], 1)
        self.assertEqual(self.page._counts["SUCCESS"], 1)
        self.assertEqual(self.page._counts["WARNING"], 1)
        self.assertEqual(self.page._counts["ERROR"], 1)

        stats_text = self.page.lbl_stats.text()
        self.assertIn("4 dòng", stats_text)
        self.assertIn("1 INFO", stats_text)
        self.assertIn("1 SUCCESS", stats_text)
        self.assertIn("1 WARN", stats_text)
        self.assertIn("1 ERROR", stats_text)

    def test_05_convenience_methods(self):
        """Kiểm tra các hàm tiện ích info, success, warning, error và appendPlainText."""
        self.page.info("Thông tin A")
        self.page.success("Thành công B")
        self.page.warning("Cảnh báo C")
        self.page.error("Lỗi D")

        # Tương thích ngược với log_terminal.appendPlainText
        self.page.log_terminal.appendPlainText("[INFO] Tin nhắn từ terminal cũ")

        self.assertEqual(len(self.page._all_logs), 5)
        self.assertEqual(self.page._counts["INFO"], 2)
        self.assertEqual(self.page._counts["SUCCESS"], 1)
        self.assertEqual(self.page._counts["WARNING"], 1)
        self.assertEqual(self.page._counts["ERROR"], 1)

    def test_06_copy_to_clipboard(self):
        """Kiểm tra nút sao chép đưa toàn bộ plain text vào clipboard."""
        self.page.info("Dòng 1 để copy")
        self.page.success("Dòng 2 để copy")

        self.page.copy_to_clipboard()
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        self.assertIn("Dòng 1 để copy", text)
        self.assertIn("Dòng 2 để copy", text)
        self.assertIn("Đã sao chép", self.page.lbl_stats.text())

    def test_07_clear_logs(self):
        """Kiểm tra nút xóa log đưa về trạng thái sạch sẽ."""
        self.page.info("Tin nhắn cần xóa")
        self.assertEqual(len(self.page._all_logs), 1)

        self.page.clear_logs()
        self.assertEqual(len(self.page._all_logs), 0)
        self.assertEqual(self.page.log_terminal.toPlainText(), "")
        self.assertEqual(self.page._counts["INFO"], 0)
        self.assertIn("0 dòng", self.page.lbl_stats.text())

    def test_08_filtering_by_level(self):
        """Kiểm tra lọc log theo ComboBox cấp độ (INFO, SUCCESS, WARNING, ERROR)."""
        self.page.info("Chỉ là thông tin")
        self.page.success("Đã hoàn tất 100%")
        self.page.warning("Cảnh báo thiếu dữ liệu")
        self.page.error("Lỗi crash")

        # Lọc chỉ hiện ERROR
        idx_err = self.page.combo_level.findData("ERROR")
        self.page.combo_level.setCurrentIndex(idx_err)
        visible_text = self.page.log_terminal.toPlainText()
        self.assertIn("Lỗi crash", visible_text)
        self.assertNotIn("Chỉ là thông tin", visible_text)
        self.assertNotIn("Đã hoàn tất", visible_text)
        self.assertIn("1/4 dòng", self.page.lbl_stats.text())

        # Lọc chỉ hiện SUCCESS
        idx_succ = self.page.combo_level.findData("SUCCESS")
        self.page.combo_level.setCurrentIndex(idx_succ)
        visible_text = self.page.log_terminal.toPlainText()
        self.assertIn("Đã hoàn tất 100%", visible_text)
        self.assertNotIn("Lỗi crash", visible_text)

        # Lọc Tất cả
        self.page.combo_level.setCurrentIndex(0)
        visible_text = self.page.log_terminal.toPlainText()
        self.assertIn("Chỉ là thông tin", visible_text)
        self.assertIn("Lỗi crash", visible_text)

    def test_09_filtering_by_keyword_search(self):
        """Kiểm tra tìm kiếm từ khóa trong nhật ký."""
        self.page.info("Khởi động Profile 06")
        self.page.info("Khởi động Profile 01")
        self.page.success("Hoàn tất Profile 06")

        # Tìm "06" -> hiển thị 2 dòng của Profile 06
        self.page.search_input.setText("06")
        visible_text = self.page.log_terminal.toPlainText()
        self.assertIn("Profile 06", visible_text)
        self.assertNotIn("Profile 01", visible_text)
        self.assertIn("2/3 dòng", self.page.lbl_stats.text())

        # Xóa tìm kiếm -> hiển thị cả 3
        self.page.search_input.setText("")
        visible_text = self.page.log_terminal.toPlainText()
        self.assertIn("Profile 01", visible_text)
        self.assertIn("Profile 06", visible_text)

    def test_10_save_to_file(self):
        """Kiểm tra lưu nhật ký ra file text."""
        self.page.info("Log cần lưu vào đĩa")
        self.page.success("Thành công lưu đĩa")

        temp_dir = Path(tempfile.mkdtemp(prefix="test_save_log_"))
        try:
            target_file = temp_dir / "exported_logs.txt"
            success = self.page.save_to_file(target_file)
            self.assertTrue(success)
            self.assertTrue(target_file.exists())

            content = target_file.read_text(encoding="utf-8")
            self.assertIn("Log cần lưu vào đĩa", content)
            self.assertIn("Thành công lưu đĩa", content)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_11_qt_log_handler_integration(self):
        """Kiểm tra kết nối logging chuẩn Python với QtLogHandler."""
        test_logger = logging.getLogger("test_subsystem")
        test_logger.setLevel(logging.DEBUG)
        handler = setup_qt_logging(self.page, logger_name="test_subsystem")
        try:
            test_logger.info("Thông điệp từ Python standard logger")
            test_logger.warning("Cảnh báo từ worker thread")
            test_logger.error("Lỗi nghiêm trọng từ CDP session")

            # Kiểm tra logs đã được nạp vào LogsPage
            all_text = self.page.get_all_logs_text()
            self.assertIn("Thông điệp từ Python standard logger", all_text)
            self.assertIn("Cảnh báo từ worker thread", all_text)
            self.assertIn("Lỗi nghiêm trọng từ CDP session", all_text)
        finally:
            test_logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
