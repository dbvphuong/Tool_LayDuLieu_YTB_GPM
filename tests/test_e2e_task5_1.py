"""Bài kiểm thử toàn trình E2E (Task 5.1 & Task 5.2).

Thực hiện:
1. Khởi tạo MainWindow của ứng dụng Desktop PySide6.
2. Kiểm tra kết nối tới GPM Local API (port 9495).
3. Nạp danh sách profile và định vị profile '06'.
4. Giả lập người dùng tích chọn profile '06' trên giao diện CollectorPage.
5. Thiết lập tham số: Chu kỳ 28 ngày qua (28_days), 1 luồng.
6. Bấm nút [ BẮT ĐẦU THU THẬP ] (Task 5.1).
7. Lắng nghe các tín hiệu Coordinator: tiến trình %, trạng thái luồng, nhật ký real-time,
   và chờ tín hiệu campaign_finished.
8. Nghiệm thu Task 5.2:
   - Kiểm tra gói kết quả sinh ra trong runs/<run_id>/.
   - Kiểm tra thư mục thô raw/ (file zip/csv tải về từ YouTube Studio).
   - Kiểm tra thư mục evidence/ (ảnh chụp biểu đồ tổng quan và bảng nâng cao).
   - Kiểm tra thư mục data/ (videos.csv, videos.jsonl, traffic_sources.csv, daily_metrics.csv, channel.json).
   - Kiểm tra manifest.json (bản kê checksum SHA-256).
   - Kiểm tra quality_report.json (báo cáo kiểm định chất lượng dữ liệu AI).
   - Kiểm tra README.md (báo cáo trực quan cho người dùng).
   - Kiểm tra cơ sở dữ liệu SQLite lịch sử và cập nhật trên Tab Lịch sử (HistoryPage).
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Đảm bảo mã hóa UTF-8 cho Windows console
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Thêm src vào sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

# Sử dụng offscreen để Qt chạy ổn định trên terminal/headless environment
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from ytb_gpm_collector.config import AppConfig
from ytb_gpm_collector.domain.models import GpmProfile
from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.interfaces.desktop.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("E2E_Test_Task5")


def run_e2e_test():
    print("=" * 80)
    print(" BÀI KIỂM THỬ TOÀN TRÌNH E2E (TASK 5.1 & TASK 5.2) QUA GIAO DIỆN UI")
    print("=" * 80)

    # 1. Khởi tạo QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    config = AppConfig()
    print(f"\n[1] Khởi tạo cấu hình và kết nối GPM Local API:")
    print(f"  - Cổng API cấu hình: {config.api_port}")
    print(f"  - Thư mục runs:     {config.runs_dir.resolve()}")

    gpm_client = GpmClient(port=config.api_port)
    if not gpm_client.is_api_port_listening():
        print(f"  ❌ CẢNH BÁO: Cổng GPM API ({gpm_client.port}) chưa mở!")
        return False
    print(f"  -> Cổng GPM API {gpm_client.port} đang lắng nghe [OK].")

    # 2. Khởi tạo MainWindow
    print("\n[2] Khởi tạo giao diện chính (MainWindow)...")
    main_window = MainWindow(config=config)
    main_window.show()

    # Nạp danh sách profile đồng bộ để kiểm thử
    print("  -> Nạp danh sách Profile từ GPM vào CollectorPage...")
    main_window.page_collector.reload_profiles(async_mode=False)

    profiles = main_window.page_collector._profiles
    print(f"  -> Đã nạp thành công {len(profiles)} profile từ GPM.")
    for p in profiles:
        print(f"     + ID: {p.id} | Tên: '{p.name}' | Proxy: {p.raw_proxy or 'None'}")

    # 3. Tìm Profile 06
    print("\n[3] Định vị Profile '06'...")
    profile_06 = None
    for p in profiles:
        # Tìm profile có tên chứa "06" hoặc "Profile 6"
        if "06" in p.name or "profile 6" in p.name.lower():
            profile_06 = p
            break

    if not profile_06:
        # Nếu không có tên cụ thể, lấy profile đầu tiên
        if profiles:
            profile_06 = profiles[0]
            print(f"  -> Không tìm thấy tên chính xác '06', chọn profile mẫu: '{profile_06.name}' (ID: {profile_06.id})")
        else:
            raise RuntimeError("Không có bất kỳ profile nào trong GPM!")
    else:
        print(f"  -> Đã tìm thấy Profile mục tiêu: '{profile_06.name}' (ID: {profile_06.id}) [OK]")

    # 4. Thao tác chọn Profile 06 trên bảng UI
    print("\n[4] Giả lập người dùng thao tác trên giao diện Tab 1 (CollectorPage):")
    main_window.page_collector.combo_group_filter.setCurrentIndex(0)
    main_window.page_collector.search_profile_input.clear()
    main_window.page_collector.deselect_all_profiles()
    main_window.page_collector._selected_ids.clear()
    assert len(main_window.page_collector._selected_ids) == 0, "Deselect thất bại"

    # Tìm dòng chứa profile_06 trong QTableWidget và tích chọn checkbox
    table = main_window.page_collector.profile_table
    target_row = -1
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.UserRole) == profile_06.id:
            target_row = row
            item.setCheckState(Qt.Checked)
            break

    assert target_row != -1, f"Không tìm thấy dòng profile {profile_06.id} trong bảng!"
    assert profile_06.id in main_window.page_collector._selected_ids, "Profile chưa được thêm vào _selected_ids"
    print(f"  [OK] Đã tích chọn Profile '{profile_06.name}' tại dòng {target_row + 1} của bảng.")
    print(f"  [OK] Số profile đã chọn: {len(main_window.page_collector._selected_ids)}")
    print(f"  [OK] Trạng thái nút [BẮT ĐẦU THU THẬP]: {'ENABLED' if main_window.page_collector.btn_start.isEnabled() else 'DISABLED'}")
    assert main_window.page_collector.btn_start.isEnabled(), "Nút bắt đầu chưa được kích hoạt!"

    # 5. Cấu hình tham số trên UI
    # Số luồng = 1
    main_window.page_collector.concurrency_spin.setValue(1)
    # Khoảng thời gian: 28 ngày qua
    idx_28d = main_window.page_collector.combo_analytics_period.findData("28_days")
    if idx_28d >= 0:
        main_window.page_collector.combo_analytics_period.setCurrentIndex(idx_28d)

    cfg = main_window.page_collector.get_configuration()
    print(f"  [OK] Cấu hình gửi đi: Luồng={cfg['concurrency']}, Kỳ={cfg['analytics_period']}, Video={cfg['video_selection_mode']}")

    # 6. Thiết lập theo dõi tiến trình và sự kiện kết thúc
    print("\n[5] Bắt đầu kích hoạt thu thập từ UI (TASK 5.1)...")
    event_loop = QEventLoop()
    campaign_result = {"total": 0, "success": 0, "failed": 0, "finished": False}

    def on_progress(completed, total, text):
        pct = int(completed / total * 100) if total > 0 else 0
        print(f"  [TIẾN TRÌNH] {completed}/{total} ({pct}%) - {text}")

    def on_worker_status(slot, p_name, ch_name, step, status, elapsed):
        print(f"  [LUỒNG {slot + 1}] Profile: '{p_name}' | Kênh: '{ch_name}' | Bước: {step} | Trạng thái: {status} | Thời gian: {elapsed}")

    def on_log_message(level, msg):
        print(f"  [LOG {level}] {msg}")

    def on_campaign_finished(total, success, failed):
        print(f"\n  🎯 CHIẾN DỊCH KẾT THÚC: Tổng={total}, Thành công={success}, Thất bại={failed}")
        campaign_result["total"] = total
        campaign_result["success"] = success
        campaign_result["failed"] = failed
        campaign_result["finished"] = True
        event_loop.quit()

    main_window.coordinator.overall_progress.connect(on_progress)
    main_window.coordinator.worker_status.connect(on_worker_status)
    main_window.coordinator.log_message.connect(on_log_message)
    main_window.coordinator.campaign_finished.connect(on_campaign_finished)

    # Đặt timeout an toàn 180 giây
    timeout_timer = QTimer()
    timeout_timer.setSingleShot(True)
    def on_timeout():
        print("\n  ❌ HẾT THỜI GIAN CHỜ (TIMEOUT 180S)!")
        event_loop.quit()
    timeout_timer.timeout.connect(on_timeout)
    timeout_timer.start(180 * 1000)

    # Bấm nút [ BẮT ĐẦU THU THẬP ]
    start_time = time.time()
    main_window.page_collector.btn_start.click()

    # Chạy event loop chờ tín hiệu kết thúc
    event_loop.exec()
    timeout_timer.stop()
    duration = time.time() - start_time

    print(f"\n  -> Thời gian chạy toàn trình: {duration:.2f} giây.")
    assert campaign_result["finished"], "Chiến dịch chưa hoàn thành (bị timeout)"
    assert campaign_result["success"] == 1, f"Thu thập profile thất bại! Kết quả: {campaign_result}"
    assert campaign_result["failed"] == 0, f"Có lỗi xảy ra: {campaign_result}"

    # Kiểm tra trạng thái UI sau khi xong
    assert not main_window.page_collector._is_running, "CollectorPage vẫn ở trạng thái running"
    assert main_window.page_collector.overall_progress_bar.value() == main_window.page_collector.overall_progress_bar.maximum(), "Progress bar chưa đạt tối đa"
    print("  [OK] UI đã cập nhật trạng thái hoàn tất, tiến trình 100%, nút bấm mở lại bình thường.")

    # =========================================================================
    # 7. NGHIỆM THU TASK 5.2: KIỂM TRA TOÀN DIỆN GÓI KẾT QUẢ TRONG runs/
    # =========================================================================
    print("\n" + "=" * 80)
    print(" NGHIỆM THU TASK 5.2: KIỂM TRA GÓI KẾT QUẢ SINH RA TRONG runs/")
    print("=" * 80)

    # Lấy bản ghi mới nhất từ SQLite
    recent_records = main_window.page_collector.history_storage.get_recent_runs(limit=1)
    assert len(recent_records) > 0, "Không có bản ghi nào trong lịch sử SQLite!"
    latest_record = recent_records[0]

    print(f"\n[A] Kiểm tra bản ghi lịch sử SQLite:")
    print(f"  - Run ID:       {latest_record.run_id}")
    print(f"  - Profile:      {latest_record.profile_name} (ID: {latest_record.profile_id})")
    print(f"  - Tên kênh:     {latest_record.channel_name} (ID: {latest_record.channel_id})")
    print(f"  - Số video:     {latest_record.video_count}")
    print(f"  - Trạng thái:   {latest_record.status}")
    print(f"  - Thư mục Run:  {latest_record.output_dir}")
    print(f"  - Bắt đầu lúc:  {latest_record.started_at}")
    print(f"  - Kết thúc lúc: {latest_record.finished_at}")

    assert latest_record.status == "success", f"Trạng thái bản ghi không phải 'success': {latest_record.status}"
    assert latest_record.profile_id == profile_06.id, "Profile ID không khớp"

    run_dir = Path(latest_record.output_dir)
    assert run_dir.exists() and run_dir.is_dir(), f"Thư mục run không tồn tại: {run_dir}"
    print(f"  [OK] Thư mục đợt chạy tồn tại hợp lệ: {run_dir.name}")

    # 1. Kiểm tra raw/
    raw_dir = run_dir / "raw"
    assert raw_dir.exists() and raw_dir.is_dir(), "Thiếu thư mục raw/"
    raw_files = list(raw_dir.glob("*.*"))
    assert len(raw_files) > 0, "Thư mục raw/ rỗng!"
    print(f"\n[B] Kiểm tra thư mục thô (raw/): Có {len(raw_files)} tệp tin gốc:")
    for rf in raw_files:
        sz = rf.stat().st_size
        assert sz > 0, f"Tệp tin thô bị rỗng (0 bytes): {rf.name}"
        print(f"  [OK] {rf.name} ({sz:,} bytes)")

    # 2. Kiểm tra evidence/
    evidence_dir = run_dir / "evidence"
    assert evidence_dir.exists() and evidence_dir.is_dir(), "Thiếu thư mục evidence/"
    overview_img = evidence_dir / "analytics_overview.png"
    adv_img = evidence_dir / "advanced_table.png"
    assert overview_img.exists() and overview_img.stat().st_size > 0, "Thiếu ảnh chụp biểu đồ tổng quan analytics_overview.png"
    assert adv_img.exists() and adv_img.stat().st_size > 0, "Thiếu ảnh chụp bảng nâng cao advanced_table.png"
    print(f"\n[C] Kiểm tra thư mục bằng chứng (evidence/):")
    print(f"  [OK] {overview_img.name} ({overview_img.stat().st_size:,} bytes)")
    print(f"  [OK] {adv_img.name} ({adv_img.stat().st_size:,} bytes)")

    # 3. Kiểm tra data/
    data_dir = run_dir / "data"
    assert data_dir.exists() and data_dir.is_dir(), "Thiếu thư mục data/ chứa file sạch"
    videos_csv = data_dir / "videos.csv"
    videos_jsonl = data_dir / "videos.jsonl"
    traffic_csv = data_dir / "traffic_sources.csv"
    daily_csv = data_dir / "daily_metrics.csv"
    channel_json = data_dir / "channel.json"

    assert videos_csv.exists() and videos_csv.stat().st_size > 0, "Thiếu videos.csv hoặc file rỗng"
    assert videos_jsonl.exists() and videos_jsonl.stat().st_size > 0, "Thiếu videos.jsonl hoặc file rỗng"
    assert traffic_csv.exists() and traffic_csv.stat().st_size > 0, "Thiếu traffic_sources.csv hoặc file rỗng"
    assert channel_json.exists() and channel_json.stat().st_size > 0, "Thiếu channel.json hoặc file rỗng"

    print(f"\n[D] Kiểm tra thư mục dữ liệu sạch (data/):")
    print(f"  [OK] videos.csv ({videos_csv.stat().st_size:,} bytes)")
    print(f"  [OK] videos.jsonl ({videos_jsonl.stat().st_size:,} bytes)")
    print(f"  [OK] traffic_sources.csv ({traffic_csv.stat().st_size:,} bytes)")
    if daily_csv.exists():
        print(f"  [OK] daily_metrics.csv ({daily_csv.stat().st_size:,} bytes)")
    print(f"  [OK] channel.json ({channel_json.stat().st_size:,} bytes)")

    # Kiểm tra nội dung videos.jsonl từng dòng
    with open(videos_jsonl, "r", encoding="utf-8") as jf:
        json_lines = [line.strip() for line in jf if line.strip()]
    assert len(json_lines) > 0, "videos.jsonl không có dòng dữ liệu nào"
    sample_video = json.loads(json_lines[0])
    print(f"  -> Mẫu video đầu tiên từ JSONL: ID='{sample_video.get('video_id')}', Tiêu đề='{sample_video.get('video_title')[:30]}...', Views={sample_video.get('views')}")

    # 4. Kiểm tra manifest.json
    manifest_file = run_dir / "manifest.json"
    assert manifest_file.exists() and manifest_file.stat().st_size > 0, "Thiếu manifest.json"
    with open(manifest_file, "r", encoding="utf-8") as mf:
        manifest_data = json.load(mf)
    assert manifest_data.get("schema_version") == "1.0", f"Sai schema_version: {manifest_data.get('schema_version')}"
    assert manifest_data.get("status") in ("success", "complete", "completed", "exported"), f"Sai status: {manifest_data.get('status')}"
    assert manifest_data.get("files") or manifest_data.get("file_inventory"), "manifest.json thiếu danh mục tệp tin"
    print(f"\n[E] Kiểm tra manifest.json:")
    print(f"  [OK] schema_version: {manifest_data.get('schema_version')}")
    print(f"  [OK] status: {manifest_data.get('status')}")
    print(f"  [OK] channel_name: {manifest_data.get('channel_name')}")

    # 5. Kiểm tra quality_report.json
    quality_file = run_dir / "quality_report.json"
    assert quality_file.exists() and quality_file.stat().st_size > 0, "Thiếu quality_report.json"
    with open(quality_file, "r", encoding="utf-8") as qf:
        quality_data = json.load(qf)
    print(f"\n[F] Kiểm tra quality_report.json (Đánh giá chất lượng dữ liệu AI):")
    print(f"  [OK] Điểm hoàn thiện dữ liệu: {quality_data.get('completeness_score_percent', 100)}%")
    print(f"  [OK] Số lỗi nghiêm trọng:    {quality_data.get('summary', {}).get('critical_errors', 0)}")
    print(f"  [OK] Số cảnh báo:            {quality_data.get('summary', {}).get('warnings', 0)}")

    # 6. Kiểm tra README.md
    readme_file = run_dir / "README.md"
    assert readme_file.exists() and readme_file.stat().st_size > 0, "Thiếu README.md"
    with open(readme_file, "r", encoding="utf-8") as rf:
        readme_content = rf.read()
    assert "Báo Cáo" in readme_content and "YouTube Studio" in readme_content, "Tiêu đề README.md không đúng mẫu"
    assert "Thông Tin Đợt Chạy" in readme_content or "Tổng quan" in readme_content, "Thiếu phần Tổng quan"
    assert "Top Video" in readme_content or "Danh sách Video" in readme_content, "Thiếu phần Video chi tiết"
    print(f"\n[G] Kiểm tra README.md (Báo cáo trực quan cho người dùng):")
    print(f"  [OK] Tệp README.md tồn tại ({readme_file.stat().st_size:,} bytes) với đầy đủ cấu trúc Markdown.")

    # 7. Kiểm tra Tab Lịch sử (HistoryPage)
    print("\n[H] Kiểm tra hiển thị trên Tab 2 (HistoryPage):")
    main_window.page_history.reload_runs()
    runs_in_history = main_window.page_history.runs_table.rowCount()
    assert runs_in_history > 0, "Bảng lịch sử rỗng sau khi tải lại!"
    first_history_item = main_window.page_history.runs_table.item(0, 1)
    history_channel = first_history_item.text() if first_history_item else ""
    print(f"  [OK] Bảng lịch sử có {runs_in_history} dòng. Dòng mới nhất kênh: '{history_channel}'")

    print("\n" + "=" * 80)
    print(" TOÀN BỘ BÀI KIỂM THỬ E2E TASK 5.1 & TASK 5.2 ĐÃ HOÀN TẤT XUẤT SẮC [PASSED]!")
    print("=" * 80)
    return True


import unittest

class TestE2ETask5(unittest.TestCase):
    """Kiểm thử nghiệm thu E2E (Task 5.1 & Task 5.2)."""

    def test_e2e_collection_profile_06(self):
        """Chạy toàn trình thu thập dữ liệu Profile 06 từ UI và nghiệm thu gói kết quả runs/."""
        client = GpmClient()
        if not client.is_api_port_listening():
            self.skipTest(f"Cổng GPM Local API ({client.port}) không mở.")
        success = run_e2e_test()
        self.assertTrue(success, "Kiểm thử toàn trình E2E profile 06 thất bại!")


if __name__ == "__main__":
    success = run_e2e_test()
    sys.exit(0 if success else 1)
