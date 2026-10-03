"""Kiểm thử nghiệm thu Task 2.3: Xuất báo cáo YouTube Studio tiếng Việt & Bắt file tải về."""

import sys
from pathlib import Path
import time
import logging
import json

# Đảm bảo mã hóa UTF-8 cho Windows console
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Thêm src vào sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.integrations.studio.session import StudioSession
from ytb_gpm_collector.integrations.studio.pages.analytics import StudioAnalyticsPage
from ytb_gpm_collector.integrations.storage import LocalStorage, create_run_directory
from ytb_gpm_collector.domain.models import RunHistoryRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestTask23Export")


def main():
    print("=" * 75)
    print(" KIỂM THỬ NGHIỆM THU TASK 2.3: XUẤT BÁO CÁO STUDIO TIẾNG VIỆT & TẢI FILE")
    print("=" * 75)

    client = GpmClient()
    if not client.is_api_port_listening():
        print(f"Cảnh báo: Cổng GPM API ({client.port}) không mở. Dừng kiểm thử.")
        return False

    # 1. Tìm và khởi động Profile 06
    p6 = client.find_profile("06")
    print(f"\n[1] Khởi động Profile: '{p6.name}' (ID: {p6.id})...")
    start_res = client.start_profile(p6.id, window_scale=0.85)
    print(f"  -> Cổng CDP: {start_res.remote_debugging_address}")

    storage = LocalStorage()
    run_storage = None
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        # Chờ 2 giây để trình duyệt ổn định
        time.sleep(2)

        # 2. Kết nối Playwright CDP
        print("\n[2] Kết nối Playwright CDP qua StudioSession...")
        with StudioSession(start_res, timeout_seconds=35.0) as session:
            page = session.get_or_create_page()
            analytics_page = StudioAnalyticsPage(page, timeout_seconds=35.0)

            # 3. Điều hướng tới YouTube Studio & Nhận diện kênh
            print("\n[3] Truy cập YouTube Studio & Xác thực thông tin kênh...")
            identity = analytics_page.navigate_to_studio()
            print(f"  -> Channel Name: '{identity.channel_name}'")
            print(f"  -> Channel ID:   '{identity.channel_id}'")
            print(f"  -> Trạng thái:   {'Đã đăng nhập [OK]' if identity.is_authenticated else 'Chưa đăng nhập'}")

            # 4. Khởi tạo cấu trúc thư mục đợt chạy runs/<run_id>/
            print("\n[4] Khởi tạo cấu trúc gói dữ liệu đợt chạy runs/<run_id>/...")
            run_storage = create_run_directory(
                channel_name=identity.channel_name,
                channel_id=identity.channel_id,
                period_preset="28_days",
            )
            print(f"  -> Thư mục Run:      {run_storage.run_dir}")
            print(f"  -> Thư mục Raw:      {run_storage.raw_dir}")
            print(f"  -> Thư mục Evidence: {run_storage.evidence_dir}")
            print(f"  -> Thư mục Data:     {run_storage.data_dir}")

            # 5. Thực hiện toàn bộ quy trình xuất báo cáo Task 2.3
            print("\n[5] Thực hiện quy trình xuất báo cáo Task 2.3:")
            print("  - Bước a: Điều hướng tới Analytics và chọn khoảng thời gian '28 ngày qua'...")
            print("  - Bước b: Chụp ảnh biểu đồ tổng quan đối chiếu vào runs/<run_id>/evidence/...")
            print("  - Bước c: Mở Chế độ xem nâng cao (Advanced Mode)...")
            print("  - Bước d: Chụp ảnh bảng Chế độ xem nâng cao làm bằng chứng...")
            print("  - Bước e: Bấm nút Xuất và bắt sự kiện tải file vào runs/<run_id>/raw/...")

            export_result = analytics_page.export_channel_analytics(
                run_storage=run_storage,
                date_preset="28_days",
            )

            # 6. Kiểm chứng các tiêu chí nghiệm thu Task 2.3
            print("\n[6] Kiểm chứng các tiêu chí nghiệm thu Task 2.3:")
            assert export_result.success, "Quy trình xuất báo cáo trả về False"
            print(f"  [OK] export_result.success == True")

            raw_file = Path(export_result.raw_file_path)
            assert raw_file.exists(), f"File tải về không tồn tại: {raw_file}"
            assert raw_file.stat().st_size > 0, f"File tải về rỗng (0 bytes): {raw_file}"
            print(f"  [OK] File gốc lưu nguyên vẹn: {raw_file.name} ({raw_file.stat().st_size:,} bytes)")

            # Kiểm tra ảnh chụp bằng chứng
            overview_img = run_storage.evidence_dir / "analytics_overview.png"
            adv_img = run_storage.evidence_dir / "advanced_table.png"
            assert overview_img.exists() and overview_img.stat().st_size > 0, "Thiếu ảnh chụp tổng quan"
            assert adv_img.exists() and adv_img.stat().st_size > 0, "Thiếu ảnh chụp chế độ nâng cao"
            print(f"  [OK] Ảnh biểu đồ tổng quan:    {overview_img.name} ({overview_img.stat().st_size:,} bytes)")
            print(f"  [OK] Ảnh bảng Chế độ nâng cao: {adv_img.name} ({adv_img.stat().st_size:,} bytes)")

            # Kiểm tra manifest.json
            manifest_file = run_storage.run_dir / "manifest.json"
            assert manifest_file.exists(), "Thiếu manifest.json"
            with open(manifest_file, "r", encoding="utf-8") as mf:
                manifest_data = json.load(mf)
            assert manifest_data["status"] == "exported", f"Status sai: {manifest_data['status']}"
            print(f"  [OK] File manifest.json hợp lệ (status: '{manifest_data['status']}')")

            # Liệt kê các file giải nén trong raw/
            extracted_csvs = list(run_storage.raw_dir.glob("*.csv"))
            print(f"  [OK] Các file CSV báo cáo sẵn sàng cho Phase 3:")
            for csv_f in extracted_csvs:
                print(f"       + {csv_f.name} ({csv_f.stat().st_size:,} bytes)")

            # 7. Lưu bản ghi lịch sử vào LocalStorage SQLite
            finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            storage.save_run_record(
                RunHistoryRecord(
                    run_id=run_storage.run_id,
                    profile_id=p6.id,
                    profile_name=p6.name,
                    channel_id=identity.channel_id,
                    channel_name=identity.channel_name,
                    period="28_days",
                    video_count=len(extracted_csvs),
                    status="success",
                    output_dir=str(run_storage.run_dir),
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )
            print("  [OK] Đã lưu bản ghi đợt chạy vào cơ sở dữ liệu lịch sử SQLite")

    finally:
        # Đóng Profile
        print(f"\n[7] Đóng Profile '{p6.name}' qua GPM API...")
        close_ok = client.close_profile(p6.id)
        print(f"  -> Đóng profile: {'THÀNH CÔNG [OK]' if close_ok else 'THẤT BẠI'}")

    print("\n" + "=" * 75)
    print(" TOÀN BỘ BÀI KIỂM THỬ TASK 2.3 ĐÃ HOÀN TẤT THÀNH CÔNG [PASSED]!")
    print("=" * 75)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
