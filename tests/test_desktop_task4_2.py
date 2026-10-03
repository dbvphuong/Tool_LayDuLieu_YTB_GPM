"""Unit tests for Task 4.2: Tab 1 - Thu thập dữ liệu (CollectorPage)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Ensure src in sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Headless Qt platform for offscreen testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QApplication

from ytb_gpm_collector.domain.models import GpmProfile, ChannelCache, AppSessionState
from ytb_gpm_collector.integrations.storage.history import LocalStorage
from ytb_gpm_collector.interfaces.desktop.pages.collector_page import CollectorPage


class TestCollectorPageTask42(unittest.TestCase):
    """Test suite cho Tab 1: Thu thập dữ liệu (Task 4.2)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        # Tạo mock GpmClient
        self.mock_client = MagicMock()
        self.sample_profiles = [
            GpmProfile(
                id="prof-01",
                name="Profile 01 - Gaming",
                raw_proxy="127.0.0.1:8080",
                proxy_host="127.0.0.1",
                proxy_port=8080,
                is_running=False,
                note="Kênh gaming top 1<br>team A",
            ),
            GpmProfile(
                id="prof-02",
                name="Profile 02 - Vlogs",
                raw_proxy=None,
                is_running=True,
                note=None,
            ),
            GpmProfile(
                id="prof-03",
                name="Profile 06 - Music",
                raw_proxy="192.168.1.100:9999",
                proxy_host="192.168.1.100",
                proxy_port=9999,
                is_running=False,
                note="Nhạc EDM hot",
            ),
        ]
        self.mock_client.get_profiles.return_value = self.sample_profiles
        self.mock_client.port = 9495

        # Dùng temp storage cho test
        self.storage = MagicMock(spec=LocalStorage)
        self.storage.get_all_channel_caches.return_value = {
            "prof-01": ChannelCache(
                profile_id="prof-01",
                channel_id="UC1234567890",
                channel_name="Kênh Game Đỉnh Cao",
                is_authenticated=True,
            )
        }
        self.storage.load_session_state.return_value = AppSessionState(
            selected_profile_ids=[],
            video_selection_mode="recent_count",
            video_limit=10,
            date_range_preset="28_days",
            concurrency=2,
        )

        self.page = CollectorPage(
            parent=None,
            gpm_client=self.mock_client,
            history_storage=self.storage,
            auto_load=False,
        )

    def tearDown(self):
        if hasattr(self, "page") and self.page:
            self.page.cleanup()

    def test_three_main_card_blocks_exist(self):
        """Kiểm tra có đủ 3 khối container chính theo kiến trúc Task 4.2."""
        self.assertIsNotNone(self.page.card_profile)
        self.assertIsNotNone(self.page.card_config)
        self.assertIsNotNone(self.page.card_execution)

        self.assertEqual(self.page.card_profile.property("class"), "card")
        self.assertEqual(self.page.card_config.property("class"), "card")
        self.assertEqual(self.page.card_execution.property("class"), "card")

    def test_profile_table_structure_and_headers(self):
        """Kiểm tra cấu trúc và tiêu đề 7 cột của bảng Profile."""
        table = self.page.profile_table
        self.assertEqual(table.columnCount(), 7)

        headers = [table.horizontalHeaderItem(i).text() for i in range(7)]
        self.assertEqual(headers[0], "")
        self.assertEqual(headers[1], "Tên Profile")
        self.assertEqual(headers[2], "Nhóm")
        self.assertEqual(headers[3], "Ghi chú")
        self.assertEqual(headers[4], "Proxy / IP")
        self.assertEqual(headers[5], "Kênh YouTube đã lưu")
        self.assertEqual(headers[6], "Trạng thái GPM")

    def test_populate_profiles_and_channel_cache(self):
        """Kiểm tra nạp dữ liệu profile và cache kênh vào bảng."""
        self.page.reload_profiles(async_mode=False)

        table = self.page.profile_table
        self.assertEqual(table.rowCount(), 3)

        # Hàng 1: Profile 01 có kênh đã cache & ghi chú
        self.assertEqual(table.item(0, 1).text(), "Profile 01 - Gaming")
        self.assertEqual(table.item(0, 2).text(), "📁 Chưa phân nhóm")
        self.assertEqual(table.item(0, 3).text(), "Kênh gaming top 1 team A")
        self.assertEqual(table.item(0, 4).text(), "127.0.0.1:8080")
        self.assertIn("Kênh Game Đỉnh Cao", table.item(0, 5).text())
        self.assertEqual(table.item(0, 6).text(), "Sẵn sàng")

        # Hàng 2: Profile 02 không proxy, không ghi chú (-), đang chạy
        self.assertEqual(table.item(1, 1).text(), "Profile 02 - Vlogs")
        self.assertEqual(table.item(1, 2).text(), "📁 Chưa phân nhóm")
        self.assertEqual(table.item(1, 3).text(), "-")
        self.assertEqual(table.item(1, 4).text(), "Trực tiếp (Không proxy)")
        self.assertEqual(table.item(1, 5).text(), "Chưa liên kết")
        self.assertEqual(table.item(1, 6).text(), "Đang chạy")

    def test_profile_checkbox_selection_and_counter(self):
        """Kiểm tra tích chọn checkbox cập nhật nhãn đếm và tập hợp ID."""
        self.page.reload_profiles(async_mode=False)
        table = self.page.profile_table

        self.assertEqual(len(self.page._selected_ids), 0)
        self.assertIn("0 / 3 profile", self.page.lbl_selected_count.text())
        self.assertFalse(self.page.btn_start.isEnabled())

        # Tích chọn hàng 0
        table.item(0, 0).setCheckState(Qt.Checked)
        self.assertIn("prof-01", self.page._selected_ids)
        self.assertEqual(len(self.page._selected_ids), 1)
        self.assertIn("1 / 3 profile", self.page.lbl_selected_count.text())
        self.assertTrue(self.page.btn_start.isEnabled())

        # Tích chọn thêm hàng 2 (prof-03)
        table.item(2, 0).setCheckState(Qt.Checked)
        self.assertIn("prof-03", self.page._selected_ids)
        self.assertEqual(len(self.page._selected_ids), 2)
        self.assertIn("2 / 3 profile", self.page.lbl_selected_count.text())

        # Bỏ tích hàng 0
        table.item(0, 0).setCheckState(Qt.Unchecked)
        self.assertNotIn("prof-01", self.page._selected_ids)
        self.assertEqual(len(self.page._selected_ids), 1)

    def test_select_all_and_deselect_all_buttons(self):
        """Kiểm tra 2 nút 'Chọn tất cả' và 'Bỏ chọn'."""
        self.page.reload_profiles(async_mode=False)

        # Chọn tất cả
        self.page.btn_select_all.click()
        self.assertEqual(len(self.page._selected_ids), 3)
        self.assertIn("3 / 3 profile", self.page.lbl_selected_count.text())
        self.assertTrue(self.page.btn_start.isEnabled())

        # Bỏ chọn tất cả
        self.page.btn_deselect_all.click()
        self.assertEqual(len(self.page._selected_ids), 0)
        self.assertIn("0 / 3 profile", self.page.lbl_selected_count.text())
        self.assertFalse(self.page.btn_start.isEnabled())

    def test_search_filter_profile_rows(self):
        """Kiểm tra tìm kiếm profile theo tên, ID hoặc proxy."""
        self.page.reload_profiles(async_mode=False)
        table = self.page.profile_table

        # Tìm kiếm "Music" -> chỉ khớp hàng 2 (Profile 06 - Music)
        self.page.search_profile_input.setText("Music")
        self.assertTrue(table.isRowHidden(0))
        self.assertTrue(table.isRowHidden(1))
        self.assertFalse(table.isRowHidden(2))

        # Chọn tất cả khi đang lọc -> chỉ chọn các hàng đang hiển thị
        self.page.btn_select_all.click()
        self.assertEqual(len(self.page._selected_ids), 1)
        self.assertIn("prof-03", self.page._selected_ids)

        # Xóa tìm kiếm -> hiển thị lại tất cả
        self.page.search_profile_input.setText("")
        self.assertFalse(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))
        self.assertFalse(table.isRowHidden(2))

    def test_concurrency_spinbox_and_worker_table(self):
        """Kiểm tra số luồng song song (1 - 10) cập nhật bảng Live Worker Slots."""
        spin = self.page.concurrency_spin
        self.assertEqual(spin.minimum(), 1)
        self.assertEqual(spin.maximum(), 10)
        self.assertEqual(spin.value(), 2)
        self.assertEqual(self.page.worker_table.rowCount(), 2)

        # Tăng lên 4 luồng
        spin.setValue(4)
        self.assertEqual(self.page.worker_table.rowCount(), 4)
        self.assertEqual(self.page.worker_table.item(3, 0).text(), "Luồng #4")

        # Giảm về 1 luồng
        spin.setValue(1)
        self.assertEqual(self.page.worker_table.rowCount(), 1)

    def test_video_selection_modes_toggle(self):
        """Kiểm tra chuyển đổi các chế độ chọn video (recent, date range, all)."""
        # Mặc định: recent_count được chọn
        self.assertTrue(self.page.radio_recent.isChecked())
        self.assertTrue(self.page.spin_video_limit.isEnabled())
        self.assertFalse(self.page.combo_video_date.isEnabled())

        # Chuyển sang date range
        self.page.radio_date_range.setChecked(True)
        self.assertFalse(self.page.spin_video_limit.isEnabled())
        self.assertTrue(self.page.combo_video_date.isEnabled())

        # Chọn 'custom' trong combo_video_date -> widget ngày tùy chỉnh hiện ra
        idx = self.page.combo_video_date.findData("custom")
        self.page.combo_video_date.setCurrentIndex(idx)
        self.assertFalse(self.page.widget_custom_video_dates.isHidden())

        # Chuyển sang all videos
        self.page.radio_all_videos.setChecked(True)
        self.assertFalse(self.page.spin_video_limit.isEnabled())
        self.assertTrue(self.page.widget_custom_video_dates.isHidden())

    def test_analytics_period_and_depth_options(self):
        """Kiểm tra khung thời gian phân tích và mức độ thu thập."""
        combo = self.page.combo_analytics_period
        self.assertGreaterEqual(combo.count(), 5)
        self.assertEqual(combo.currentData(), "28_days")
        self.assertTrue(self.page.widget_custom_analytics_dates.isHidden())

        # Chọn tùy chỉnh ngày cho Analytics
        c_idx = combo.findData("custom")
        combo.setCurrentIndex(c_idx)
        self.assertFalse(self.page.widget_custom_analytics_dates.isHidden())

        # Mức độ thu thập
        self.assertTrue(self.page.radio_depth_std.isChecked())
        self.page.radio_depth_fast.setChecked(True)
        self.assertTrue(self.page.radio_depth_fast.isChecked())

    def test_get_configuration_dictionary(self):
        """Kiểm tra hàm get_configuration trả về đầy đủ các trường tham số chuẩn."""
        self.page.reload_profiles(async_mode=False)
        self.page.profile_table.item(0, 0).setCheckState(Qt.Checked)
        self.page.concurrency_spin.setValue(3)
        self.page.spin_video_limit.setValue(25)

        cfg = self.page.get_configuration()
        self.assertIsInstance(cfg, dict)
        self.assertEqual(cfg["selected_profile_ids"], ["prof-01"])
        self.assertEqual(cfg["concurrency"], 3)
        self.assertEqual(cfg["video_selection_mode"], "recent_count")
        self.assertEqual(cfg["video_limit"], 25)
        self.assertEqual(cfg["analytics_period"], "28_days")
        self.assertEqual(cfg["collection_depth"], "standard")

    def test_start_and_stop_button_execution_signals(self):
        """Kiểm tra phát tín hiệu start_requested và stop_requested."""
        self.page.reload_profiles(async_mode=False)
        self.page.btn_select_all.click()

        received_configs = []
        self.page.start_requested.connect(lambda c: received_configs.append(c))

        stop_called = []
        self.page.stop_requested.connect(lambda: stop_called.append(True))

        # Nhấn BẮT ĐẦU
        self.page.btn_start.click()
        self.assertEqual(len(received_configs), 1)
        self.assertEqual(len(received_configs[0]["selected_profile_ids"]), 3)
        self.assertTrue(self.page._is_running)
        self.assertFalse(self.page.btn_start.isEnabled())
        self.assertTrue(self.page.btn_stop.isEnabled())

        # Nhấn DỪNG LẠI
        self.page.btn_stop.click()
        self.assertEqual(len(stop_called), 1)

    def test_worker_status_update_and_progress_bar(self):
        """Kiểm tra hàm cập nhật tiến trình tổng và từng dòng worker slot."""
        self.page.concurrency_spin.setValue(2)

        # Cập nhật tiến độ tổng
        self.page.set_overall_progress(1, 4, "Đang cào...")
        self.assertEqual(self.page.overall_progress_bar.value(), 1)
        self.assertEqual(self.page.overall_progress_bar.maximum(), 4)
        self.assertIn("1/4 profile hoàn thành", self.page.lbl_progress_detail.text())
        self.assertIn("Đang cào...", self.page.lbl_overall_status.text())

        # Cập nhật Worker 1
        self.page.update_worker_status(
            worker_idx=0,
            profile_name="Profile 06",
            channel_name="Kênh Âm Nhạc",
            step="Đang xuất báo cáo YouTube Studio",
            status="Đang chạy",
            elapsed="01:23",
        )
        self.assertEqual(self.page.worker_table.item(0, 1).text(), "Profile 06")
        self.assertEqual(self.page.worker_table.item(0, 2).text(), "Kênh Âm Nhạc")
        self.assertEqual(self.page.worker_table.item(0, 3).text(), "Đang xuất báo cáo YouTube Studio")
        self.assertEqual(self.page.worker_table.item(0, 4).text(), "Đang chạy")
        self.assertEqual(self.page.worker_table.item(0, 5).text(), "01:23")

    def test_open_runs_folder_creates_directory(self):
        """Kiểm tra nút mở thư mục runs tự động tạo thư mục nếu chưa có."""
        self.page.btn_open_runs.click()
        self.assertTrue(Path("runs").exists())

    def test_group_filter_combobox_and_filtering(self):
        """Kiểm tra dropdown lọc Nhóm GPM và lọc các hàng trong bảng."""
        from ytb_gpm_collector.domain.models import GpmGroup

        self.sample_profiles[0].group_id = "g-01"
        self.sample_profiles[1].group_id = "g-02"
        self.sample_profiles[2].group_id = "g-01"
        self.mock_client.get_groups.return_value = [
            GpmGroup(id="g-01", name="Nhóm Gaming"),
            GpmGroup(id="g-02", name="Nhóm Vlog"),
        ]

        self.page.reload_profiles(async_mode=False)
        combo = self.page.combo_group_filter
        table = self.page.profile_table

        # Kiểm tra số lượng mục trong combobox
        self.assertEqual(combo.count(), 3)  # Tất cả nhóm (3), Nhóm Gaming (2), Nhóm Vlog (1)
        self.assertEqual(combo.itemData(0), "")
        self.assertIn("Tất cả nhóm", combo.itemText(0))
        self.assertEqual(combo.itemData(1), "g-01")
        self.assertIn("Nhóm Gaming", combo.itemText(1))
        self.assertEqual(combo.itemData(2), "g-02")
        self.assertIn("Nhóm Vlog", combo.itemText(2))

        # Cột nhóm trong bảng hiển thị đúng tên nhóm
        self.assertEqual(table.item(0, 2).text(), "📁 Nhóm Gaming")
        self.assertEqual(table.item(1, 2).text(), "📁 Nhóm Vlog")
        self.assertEqual(table.item(2, 2).text(), "📁 Nhóm Gaming")

        # Mặc định tất cả đều hiển thị
        self.assertFalse(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))
        self.assertFalse(table.isRowHidden(2))

        # Chọn "Nhóm Gaming" (g-01) -> chỉ hàng 0 và 2 hiển thị
        combo.setCurrentIndex(1)
        self.assertFalse(table.isRowHidden(0))
        self.assertTrue(table.isRowHidden(1))
        self.assertFalse(table.isRowHidden(2))
        self.assertIn("Hiển thị: 2/3", self.page.lbl_selected_count.text())

        # Chọn tất cả khi đang lọc Nhóm Gaming -> chỉ chọn prof-01 và prof-03
        self.page.btn_select_all.click()
        self.assertEqual(self.page._selected_ids, {"prof-01", "prof-03"})

        # Chuyển sang "Nhóm Vlog" (g-02) -> chỉ hàng 1 hiển thị
        combo.setCurrentIndex(2)
        self.assertTrue(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))
        self.assertTrue(table.isRowHidden(2))
        self.assertIn("Hiển thị: 1/3", self.page.lbl_selected_count.text())

        # Bỏ chọn trong nhóm Vlog -> prof-01 và prof-03 vẫn giữ nguyên
        self.page.btn_deselect_all.click()
        self.assertEqual(self.page._selected_ids, {"prof-01", "prof-03"})

        # Trở về Tất cả nhóm
        combo.setCurrentIndex(0)
        self.assertFalse(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))
        self.assertFalse(table.isRowHidden(2))

    def test_group_filter_combined_with_search(self):
        """Kiểm tra kết hợp lọc Nhóm GPM và tìm kiếm từ khóa."""
        from ytb_gpm_collector.domain.models import GpmGroup

        self.sample_profiles[0].group_id = "g-01"
        self.sample_profiles[1].group_id = "g-02"
        self.sample_profiles[2].group_id = "g-01"
        self.mock_client.get_groups.return_value = [
            GpmGroup(id="g-01", name="Nhóm Gaming"),
            GpmGroup(id="g-02", name="Nhóm Vlog"),
        ]

        self.page.reload_profiles(async_mode=False)
        combo = self.page.combo_group_filter
        table = self.page.profile_table

        # Chọn Nhóm Gaming
        combo.setCurrentIndex(1)
        self.assertFalse(table.isRowHidden(0))
        self.assertTrue(table.isRowHidden(1))
        self.assertFalse(table.isRowHidden(2))

        # Tìm kiếm "Music" trong Nhóm Gaming -> chỉ hàng 2 khớp
        self.page.search_profile_input.setText("Music")
        self.assertTrue(table.isRowHidden(0))
        self.assertTrue(table.isRowHidden(1))
        self.assertFalse(table.isRowHidden(2))
        self.assertIn("Hiển thị: 1/3", self.page.lbl_selected_count.text())


if __name__ == "__main__":
    unittest.main()
