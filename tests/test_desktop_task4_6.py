"""Unit tests for Task 4.6: Worker Thread Pool & Concurrency Queue Manager."""

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src in sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Headless Qt platform for offscreen testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from ytb_gpm_collector.domain.models import GpmProfile
from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.integrations.storage.history import LocalStorage
from ytb_gpm_collector.application.coordinator import CollectionCoordinator, ProfileWorker
from ytb_gpm_collector.interfaces.desktop.main_window import MainWindow


class TestCoordinatorTask46(unittest.TestCase):
    """Bộ kiểm thử cho Worker Thread Pool & Concurrency Queue (Task 4.6)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_ytb_task46_"))
        self.runs_dir = self.test_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.storage = LocalStorage(self.test_dir / "state" / "test.db")
        self.mock_client = MagicMock(spec=GpmClient)
        self.mock_client.port = 9495

        # Danh sách 4 profile mẫu
        self.sample_profiles = [
            GpmProfile(id="p1", name="Profile 01 - Gaming", is_running=False),
            GpmProfile(id="p2", name="Profile 02 - Tin tức", is_running=False),
            GpmProfile(id="p3", name="Profile 03 - Vlogs", is_running=False),
            GpmProfile(id="p4", name="Profile 04 - Âm nhạc", is_running=False),
        ]

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_coordinator_initialization(self):
        """Kiểm tra khởi tạo CollectionCoordinator với các giá trị mặc định."""
        coord = CollectionCoordinator(
            gpm_client=self.mock_client,
            history_storage=self.storage,
            runs_dir=self.runs_dir,
            timeout_seconds=25.0,
        )
        self.assertFalse(coord.running)
        self.assertEqual(coord.concurrency, 2)
        self.assertEqual(len(coord.active_workers), 0)
        self.assertEqual(len(coord.queue), 0)

    def test_02_concurrency_queue_rotation_and_progress(self):
        """
        Kiểm tra cơ chế hàng đợi luân phiên:
        4 profile chạy trên 2 luồng (concurrency=2):
        - Ban đầu: 2 luồng bốc p1 và p2.
        - Xong p1 -> luồng 0 bốc tiếp p3.
        - Xong p2 -> luồng 1 bốc tiếp p4.
        - Hoàn thành toàn bộ 4/4 profile và phát campaign_finished(4, 4, 0).
        """
        completed_order = []
        progress_events = []
        worker_statuses = []

        def mock_worker_fn(worker: ProfileWorker):
            # Giả lập worker thực thi qua các bước và xong trong 30ms
            p = worker.profile
            worker.status_updated.emit(worker.worker_idx, p.name, "Kênh Mẫu", "Đang xuất dữ liệu...", "Đang chạy", "00:01")
            worker.log_emitted.emit("INFO", f"Đang xử lý {p.name}")
            time.sleep(0.03)
            completed_order.append(p.id)
            worker.status_updated.emit(worker.worker_idx, p.name, "Kênh Mẫu", "Hoàn tất", "✅ Xong", "00:02")
            worker.worker_finished.emit(worker.worker_idx, p.id, True, "Thành công")

        coord = CollectionCoordinator(
            gpm_client=self.mock_client,
            history_storage=self.storage,
            runs_dir=self.runs_dir,
            worker_fn=mock_worker_fn,
        )

        coord.overall_progress.connect(lambda c, t, s: progress_events.append((c, t, s)))
        coord.worker_status.connect(lambda idx, p, ch, st, stat, el: worker_statuses.append((idx, p, stat)))

        # Vòng lặp chờ sự kiện kết thúc
        loop = QEventLoop()
        finished_results = []
        coord.campaign_finished.connect(lambda total, succ, fail: (finished_results.append((total, succ, fail)), loop.quit()))

        # Khởi động với concurrency = 2
        config = {"concurrency": 2, "analytics_period": "28_days"}
        ok = coord.start(config, self.sample_profiles)
        self.assertTrue(ok)
        self.assertTrue(coord.running)

        # Chờ tối đa 3 giây cho các worker chạy xong
        QTimer.singleShot(3000, loop.quit)
        loop.exec()

        # Kiểm chứng kết quả
        self.assertFalse(coord.running)
        self.assertEqual(len(finished_results), 1)
        total, succ, fail = finished_results[0]
        self.assertEqual(total, 4)
        self.assertEqual(succ, 4)
        self.assertEqual(fail, 0)

        # Đã xử lý đủ cả 4 profile
        self.assertEqual(len(completed_order), 4)
        self.assertIn("p1", completed_order)
        self.assertIn("p2", completed_order)
        self.assertIn("p3", completed_order)
        self.assertIn("p4", completed_order)

        # Kiểm tra tiến trình cập nhật từng bước tới 4/4
        self.assertGreaterEqual(len(progress_events), 4)
        last_progress = progress_events[-1]
        self.assertEqual(last_progress[0], 4)
        self.assertEqual(last_progress[1], 4)

    def test_03_error_resilience_in_worker_slot(self):
        """
        Kiểm tra độ bền bỉ khi gặp lỗi:
        Profile thứ 2 gặp lỗi ném Exception, Coordinator phải:
        - Bắt lỗi an toàn, đóng profile.
        - Không làm chết app, tiếp tục bốc profile thứ 3.
        - Kết thúc với: 3 total, 2 success, 1 failed.
        """
        def mock_worker_error_fn(worker: ProfileWorker):
            p = worker.profile
            if p.id == "p2":
                time.sleep(0.02)
                raise RuntimeError("Lỗi mạng proxy trên profile 02")
            else:
                time.sleep(0.02)
                worker.worker_finished.emit(worker.worker_idx, p.id, True, "Thành công")

        coord = CollectionCoordinator(
            gpm_client=self.mock_client,
            history_storage=self.storage,
            runs_dir=self.runs_dir,
            worker_fn=mock_worker_error_fn,
        )

        loop = QEventLoop()
        finished_results = []
        coord.campaign_finished.connect(lambda t, s, f: (finished_results.append((t, s, f)), loop.quit()))

        # Chạy 3 profile với 1 luồng
        profiles = self.sample_profiles[:3]
        coord.start({"concurrency": 1}, profiles)

        QTimer.singleShot(3000, loop.quit)
        loop.exec()

        self.assertFalse(coord.running)
        self.assertEqual(len(finished_results), 1)
        total, succ, fail = finished_results[0]
        self.assertEqual(total, 3)
        self.assertEqual(succ, 2)
        self.assertEqual(fail, 1)

    def test_04_cancellation_and_stop(self):
        """Kiểm tra nút Dừng lại (Stop) hủy bỏ hàng đợi và dừng các luồng an toàn."""
        def mock_slow_worker_fn(worker: ProfileWorker):
            # Giả lập worker chạy chậm
            for _ in range(20):
                if worker._is_aborted:
                    worker.worker_finished.emit(worker.worker_idx, worker.profile.id, False, "Bị hủy")
                    return
                time.sleep(0.05)
            worker.worker_finished.emit(worker.worker_idx, worker.profile.id, True, "Xong")

        coord = CollectionCoordinator(
            gpm_client=self.mock_client,
            history_storage=self.storage,
            runs_dir=self.runs_dir,
            worker_fn=mock_slow_worker_fn,
        )

        loop = QEventLoop()
        finished_results = []
        coord.campaign_finished.connect(lambda t, s, f: (finished_results.append((t, s, f)), loop.quit()))

        # Khởi động với 4 profile
        coord.start({"concurrency": 2}, self.sample_profiles)
        self.assertTrue(coord.running)

        # Chờ 80ms rồi dừng lại
        QTimer.singleShot(80, coord.stop)
        QTimer.singleShot(3000, loop.quit)
        loop.exec()

        self.assertFalse(coord.running)
        self.assertTrue(coord.is_cancelled)
        # Hàng đợi đã bị xóa sạch
        self.assertEqual(len(coord.queue), 0)

    def test_05_main_window_coordinator_integration(self):
        """Kiểm tra đấu nối giữa MainWindow, CollectorPage và CollectionCoordinator."""
        window = MainWindow()
        self.assertIsNotNone(window.coordinator)

        # Giả lập nạp profile vào CollectorPage
        window.page_collector._profiles = self.sample_profiles[:2]
        window.page_collector._selected_ids = {"p1", "p2"}
        window.page_collector._sync_start_button_state()

        # Đổi worker_fn thành mock để chạy mượt mà
        def mock_fast_fn(worker):
            time.sleep(0.05)
            worker.status_updated.emit(worker.worker_idx, worker.profile.name, "Kênh Test", "Thành công", "✅ Xong", "00:01")
            worker.worker_finished.emit(worker.worker_idx, worker.profile.id, True, "OK")

        window.coordinator.worker_fn = mock_fast_fn

        loop = QEventLoop()
        window.coordinator.campaign_finished.connect(lambda t, s, f: loop.quit())

        # Người dùng bấm BẮT ĐẦU THU THẬP từ CollectorPage
        window.page_collector.btn_start.click()
        self.assertTrue(window.coordinator.running)
        self.assertTrue(window.page_collector._is_running)

        QTimer.singleShot(2000, loop.quit)
        loop.exec()

        # Sau khi chạy xong
        self.assertFalse(window.coordinator.running)
        self.assertFalse(window.page_collector._is_running)
        window.close()


if __name__ == "__main__":
    unittest.main()
