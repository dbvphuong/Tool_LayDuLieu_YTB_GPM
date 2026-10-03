"""Kiểm thử nhận diện kênh và điều hướng Analytics YouTube Studio (Task 2.2)."""

import sys
from pathlib import Path
import time
import logging

# Đảm bảo mã hóa UTF-8 cho Windows console
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Thêm src vào sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.integrations.studio.session import StudioSession
from ytb_gpm_collector.integrations.studio.pages.analytics import StudioAnalyticsPage
from ytb_gpm_collector.integrations.storage.history import LocalStorage
from ytb_gpm_collector.domain.models import ChannelCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestStudioAnalytics")


def main():
    print("=" * 70)
    print(" KIỂM THỬ TASK 2.2: NHẬN DIỆN KÊNH & ĐIỀU HƯỚNG ANALYTICS")
    print("=" * 70)

    client = GpmClient()
    if not client.is_api_port_listening():
        print(f"Cảnh báo: Cổng GPM API ({client.port}) không mở. Dừng kiểm thử.")
        return

    # 1. Tìm và khởi động Profile 06
    p6 = client.find_profile("06")
    print(f"\n[1] Khởi động Profile: '{p6.name}' (ID: {p6.id})...")
    start_res = client.start_profile(p6.id, window_scale=0.85)
    print(f"  -> Cổng CDP: {start_res.remote_debugging_address}")

    storage = LocalStorage()

    try:
        # Chờ 2 giây để trình duyệt ổn định
        time.sleep(2)

        # 2. Kết nối Playwright CDP
        print("\n[2] Kết nối Playwright CDP qua StudioSession...")
        with StudioSession(start_res, timeout_seconds=30.0) as session:
            page = session.get_or_create_page()
            analytics_page = StudioAnalyticsPage(page, timeout_seconds=30.0)

            # 3. Truy cập https://studio.youtube.com & Kiểm tra đăng nhập + Trích xuất kênh
            print("\n[3] Truy cập YouTube Studio & Nhận diện Kênh...")
            identity = analytics_page.navigate_to_studio()

            print(f"  -> Kết quả nhận diện kênh thành công [OK]:")
            print(f"     + Channel ID:   {identity.channel_id}")
            print(f"     + Channel Name: {identity.channel_name}")
            print(f"     + URL Kênh:     {identity.url}")
            print(f"     + Đã đăng nhập: {identity.is_authenticated}")

            assert identity.channel_id.startswith("UC"), f"Channel ID không hợp lệ: {identity.channel_id}"
            assert len(identity.channel_name) > 0, "Channel Name rỗng"
            assert identity.is_authenticated, "Chưa xác thực đăng nhập"

            # Lưu cache vào SQLite cục bộ để tái sử dụng
            storage.save_channel_cache(
                ChannelCache(
                    profile_id=p6.id,
                    channel_id=identity.channel_id,
                    channel_name=identity.channel_name,
                    is_authenticated=True,
                )
            )
            print("  -> Đã lưu thông tin kênh vào LocalStorage SQLite cache [OK]")

            # 4. Điều hướng tới trang "Số liệu phân tích" (Analytics)
            print("\n[4] Điều hướng tới trang 'Số liệu phân tích' (Analytics)...")
            nav_ok = analytics_page.navigate_to_analytics()
            assert nav_ok, "Điều hướng Analytics thất bại"
            print(f"  -> Điều hướng Analytics thành công [OK]")
            print(f"     + URL hiện tại:   {page.url}")
            print(f"     + Tiêu đề trang:  {page.title()}")

            # 5. Kiểm tra các Tab phân tích và Chế độ nâng cao
            tabs = analytics_page.get_analytics_tabs()
            print(f"  -> Các Tab số liệu phân tích: {tabs} [OK]")
            has_adv = analytics_page.is_advanced_mode_available()
            print(f"  -> Chế độ xem nâng cao (Advanced Mode): {'CÓ SẴN [OK]' if has_adv else 'CHƯA TÌM THẤY'}")

            # 6. Chụp ảnh bằng chứng
            screenshot_path = Path("runs/test_evidence/analytics_06.png")
            saved_img = analytics_page.capture_screenshot(screenshot_path)
            print(f"  -> Đã chụp ảnh màn hình làm bằng chứng: {saved_img} [OK]")

            time.sleep(2)

    finally:
        # Đóng Profile
        print(f"\n[5] Đóng Profile '{p6.name}' qua GPM API...")
        close_ok = client.close_profile(p6.id)
        print(f"  -> Đóng profile: {'THÀNH CÔNG [OK]' if close_ok else 'THẤT BẠI'}")

    print("\n" + "=" * 70)
    print(" BÀI KIỂM THỬ TASK 2.2 ĐÃ HOÀN TẤT THÀNH CÔNG [PASSED]!")
    print("=" * 70)


if __name__ == "__main__":
    main()
