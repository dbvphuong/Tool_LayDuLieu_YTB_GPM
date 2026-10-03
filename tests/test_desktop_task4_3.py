"""Unit tests for Task 4.3: Tab 2 - Lịch sử & Kết quả (HistoryPage)."""

import json
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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ytb_gpm_collector.integrations.storage.history import LocalStorage
from ytb_gpm_collector.interfaces.desktop.pages.history_page import (
    HistoryPage,
    ReadmeViewerDialog,
    RunEntry,
    scan_single_run_dir,
    format_iso_to_display,
    format_bytes_to_human,
)


class TestHistoryPageTask43(unittest.TestCase):
    """Bộ kiểm thử toàn diện cho Tab 2: Lịch sử & Kết quả (Task 4.3)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        # Tạo thư mục runs giả lập tạm thời
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_ytb_task43_"))
        self.runs_dir = self.test_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        # Tạo đợt chạy 1: Hoàn tất 100%
        self.run1_dir = self.runs_dir / "2026-10-03_102000_kenh-huong-dan_28d"
        self.run1_dir.mkdir(parents=True)
        (self.run1_dir / "data").mkdir()
        (self.run1_dir / "raw").mkdir()
        (self.run1_dir / "evidence").mkdir()

        # Tạo file data và manifest cho run 1
        (self.run1_dir / "data" / "videos.csv").write_text("video_id,views\nVID1,1000\nVID2,2000\n", encoding="utf-8-sig")
        (self.run1_dir / "data" / "channel.json").write_text('{"channel_name": "Kênh Hướng Dẫn", "channel_id": "UC_GUIDE_1"}', encoding="utf-8")
        (self.run1_dir / "raw" / "source.xlsx").write_text("raw excel", encoding="utf-8")
        (self.run1_dir / "evidence" / "overview.png").write_text("fake image", encoding="utf-8")
        (self.run1_dir / "README.md").write_text("# Báo Cáo Kênh Hướng Dẫn\n\nNội dung chi tiết đợt chạy...", encoding="utf-8")

        manifest1 = {
            "schema_version": "1.0",
            "run_id": self.run1_dir.name,
            "channel_id": "UC_GUIDE_1",
            "channel_name": "Kênh Hướng Dẫn",
            "period": "28_days",
            "period_start": "2026-09-04",
            "period_end": "2026-10-02",
            "period_kind": "fixed_calendar_range",
            "created_at": "2026-10-03T10:20:00",
            "finished_at": "2026-10-03T10:25:00",
            "status": "success",
            "summary": {
                "video_count": 10,
                "daily_metrics_count": 140,
                "traffic_sources_count": 5,
                "raw_files_count": 1,
                "evidence_files_count": 1,
                "total_size_bytes": 102400,
            },
            "quality_summary": {
                "status": "passed",
                "completeness_score_percent": 100.0,
                "total_warnings": 0,
                "total_errors": 0,
                "reconciled": True,
            },
        }
        (self.run1_dir / "manifest.json").write_text(json.dumps(manifest1), encoding="utf-8")

        # Tạo đợt chạy 2: Có cảnh báo
        self.run2_dir = self.runs_dir / "2026-10-02_151000_kenh-tin-tuc_90d"
        self.run2_dir.mkdir(parents=True)
        (self.run2_dir / "data").mkdir()
        (self.run2_dir / "data" / "videos.csv").write_text("video_id\nV1\nV2\nV3\n", encoding="utf-8-sig")
        manifest2 = {
            "run_id": self.run2_dir.name,
            "channel_id": "UC_NEWS_2",
            "channel_name": "Kênh Tin Tức",
            "period": "90_days",
            "period_start": "2026-07-04",
            "period_end": "2026-10-02",
            "created_at": "2026-10-02T15:10:00",
            "status": "partial",
            "summary": {
                "video_count": 5,
                "daily_metrics_count": 0,
                "raw_files_count": 1,
                "evidence_files_count": 0,
                "total_size_bytes": 20480,
            },
            "quality_summary": {
                "completeness_score_percent": 88.5,
                "total_warnings": 2,
                "total_errors": 0,
                "reconciled": False,
            },
        }
        (self.run2_dir / "manifest.json").write_text(json.dumps(manifest2), encoding="utf-8")

        # Khởi tạo Page với thư mục test
        self.page = HistoryPage(
            parent=None,
            history_storage=LocalStorage(self.test_dir / "state" / "test.db"),
            runs_dir=self.runs_dir,
            auto_load=True,
        )

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_ui_structure_and_components(self):
        """Kiểm tra cấu trúc giao diện Tab 2 theo đúng đặc tả kiến trúc."""
        # Kiểm tra nút đầu trang
        self.assertIsNotNone(self.page.btn_open_runs)
        self.assertIsNotNone(self.page.btn_refresh)
        self.assertIsNotNone(self.page.search_input)
        self.assertIsNotNone(self.page.status_filter)

        # Kiểm tra bảng danh sách đợt chạy
        table = self.page.runs_table
        self.assertEqual(table.columnCount(), 6)
        headers = [table.horizontalHeaderItem(i).text() for i in range(6)]
        self.assertIn("Thời gian", headers[0])
        self.assertIn("Tên Kênh", headers[1])
        self.assertIn("Phạm vi", headers[2])
        self.assertIn("Số video", headers[3])
        self.assertIn("Trạng thái", headers[4])
        self.assertIn("Thao tác", headers[5])

        # Kiểm tra khung Detail Card
        self.assertIsNotNone(self.page.card_detail)
        self.assertIsNotNone(self.page.btn_detail_readme)
        self.assertIsNotNone(self.page.btn_detail_open_folder)
        self.assertIsNotNone(self.page.btn_detail_open_csv)
        self.assertIsNotNone(self.page.btn_detail_rebuild)

    def test_02_scan_single_run_dir(self):
        """Kiểm tra hàm scan_single_run_dir trích xuất đúng thông số từ manifest."""
        entry = scan_single_run_dir(self.run1_dir)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.run_id, self.run1_dir.name)
        self.assertEqual(entry.channel_name, "Kênh Hướng Dẫn")
        self.assertEqual(entry.channel_id, "UC_GUIDE_1")
        self.assertEqual(entry.video_count, 10)
        self.assertEqual(entry.status, "success")
        self.assertTrue(entry.has_readme)
        self.assertTrue(entry.has_videos_csv)
        self.assertTrue(entry.has_evidence)
        self.assertTrue(entry.has_raw)
        self.assertEqual(entry.completeness_score_percent, 100.0)

    def test_03_table_populated_with_scanned_runs(self):
        """Kiểm tra bảng hiển thị đầy đủ 2 đợt chạy đã quét và sắp xếp mới nhất lên đầu."""
        table = self.page.runs_table
        self.assertEqual(table.rowCount(), 2)

        # Đợt chạy 1 (created_at 2026-10-03) mới hơn đợt 2 (2026-10-02) nên nằm ở hàng 0
        self.assertIn("Kênh Hướng Dẫn", table.item(0, 1).text())
        self.assertIn("10 video", table.item(0, 3).text())
        self.assertIn("Hoàn tất", table.item(0, 4).text())

        # Đợt chạy 2 ở hàng 1
        self.assertIn("Kênh Tin Tức", table.item(1, 1).text())
        self.assertIn("5 video", table.item(1, 3).text())
        self.assertIn("cảnh báo", table.item(1, 4).text().lower())

    def test_04_selection_updates_detail_card(self):
        """Kiểm tra chọn hàng cập nhật chi tiết đợt chạy lên Detail Card."""
        table = self.page.runs_table
        # Chọn hàng 0
        table.selectRow(0)

        selected = self.page.get_selected_run()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.channel_name, "Kênh Hướng Dẫn")

        # Kiểm tra nội dung text trong detail card
        self.assertIn(self.run1_dir.name, self.page.lbl_detail_title.text())
        self.assertIn("Kênh Hướng Dẫn", self.page.lbl_info_channel.text())
        self.assertIn("UC_GUIDE_1", self.page.lbl_info_channel.text())
        self.assertIn("10 video", self.page.lbl_info_metrics.text())
        self.assertIn("100.0%", self.page.lbl_info_quality.text())

        # Các nút thao tác phải được bật
        self.assertTrue(self.page.btn_detail_readme.isEnabled())
        self.assertTrue(self.page.btn_detail_open_folder.isEnabled())
        self.assertTrue(self.page.btn_detail_open_csv.isEnabled())
        self.assertTrue(self.page.btn_detail_open_evidence.isEnabled())

    def test_05_search_filter(self):
        """Kiểm tra tìm kiếm theo tên kênh lọc đúng số dòng."""
        table = self.page.runs_table
        self.assertEqual(table.rowCount(), 2)

        # Tìm kiếm "Tin Tức" -> chỉ hiện dòng 1
        self.page.search_input.setText("Tin Tức")
        self.assertTrue(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))
        self.assertIn("1 / 2 đợt chạy", self.page.lbl_runs_count.text())

        # Tìm kiếm từ khóa không có -> ẩn hết
        self.page.search_input.setText("Âm Nhạc")
        self.assertTrue(table.isRowHidden(0))
        self.assertTrue(table.isRowHidden(1))

        # Xóa tìm kiếm -> hiện lại cả 2
        self.page.search_input.setText("")
        self.assertFalse(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))

    def test_06_status_filter(self):
        """Kiểm tra lọc theo trạng thái (success, partial)."""
        table = self.page.runs_table

        # Chọn "Thành công"
        idx_success = self.page.status_filter.findData("success")
        self.page.status_filter.setCurrentIndex(idx_success)
        self.assertFalse(table.isRowHidden(0))
        self.assertTrue(table.isRowHidden(1))

        # Chọn "Có cảnh báo"
        idx_partial = self.page.status_filter.findData("partial")
        self.page.status_filter.setCurrentIndex(idx_partial)
        self.assertTrue(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))

        # Chọn "Tất cả"
        self.page.status_filter.setCurrentIndex(0)
        self.assertFalse(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))

    def test_07_readme_viewer_dialog(self):
        """Kiểm tra cửa sổ ReadmeViewerDialog nạp đúng nội dung markdown và sao chép."""
        entry = scan_single_run_dir(self.run1_dir)
        dialog = ReadmeViewerDialog(run_entry=entry, parent=None)

        content = dialog.text_viewer.toPlainText()
        self.assertIn("Báo Cáo Kênh Hướng Dẫn", content)
        self.assertIn("Nội dung chi tiết đợt chạy", content)

        # Test sao chép nội dung
        dialog._copy_content()
        clipboard = QApplication.clipboard()
        self.assertIn("Báo Cáo Kênh Hướng Dẫn", clipboard.text())
        self.assertIn("Đã sao chép", dialog.lbl_status.text())

    def test_08_empty_directory_handling(self):
        """Kiểm tra trường hợp thư mục runs rỗng không gây crash."""
        empty_dir = self.test_dir / "empty_runs"
        empty_dir.mkdir()
        empty_page = HistoryPage(
            parent=None,
            runs_dir=empty_dir,
            auto_load=True,
        )
        self.assertEqual(empty_page.runs_table.rowCount(), 0)
        self.assertIn("Chưa có đợt chạy nào", empty_page.lbl_detail_title.text())
        self.assertFalse(empty_page.btn_detail_readme.isEnabled())

    def test_09_formatting_helpers(self):
        """Kiểm tra các hàm định dạng hiển thị ngày và dung lượng byte."""
        self.assertEqual(format_bytes_to_human(500), "500 B")
        self.assertEqual(format_bytes_to_human(2048), "2.0 KB")
        self.assertEqual(format_bytes_to_human(1048576 * 3), "3.00 MB")

        self.assertEqual(format_iso_to_display("2026-10-03T10:20:30"), "03/10/2026 10:20")
        self.assertEqual(format_iso_to_display(""), "-")


if __name__ == "__main__":
    unittest.main()
