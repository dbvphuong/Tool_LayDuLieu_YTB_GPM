"""Kiểm thử kết nối Playwright CDP với trình duyệt Chrome của GPM-Login (Task 2.1)."""

import sys
from pathlib import Path
import time
import logging

# Đảm bảo mã hóa UTF-8 cho Windows console
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Thêm src vào sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ytb_gpm_collector.domain.models import GpmStartResult
from ytb_gpm_collector.domain.errors import CdpConnectionError
from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.integrations.studio.session import StudioSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestStudioSession")


def test_normalization():
    """Kiểm tra logic chuẩn hóa CDP endpoint."""
    print("\n--- [Kiểm tra chuẩn hóa CDP Endpoint] ---")
    
    # 1. Host:port
    norm1 = StudioSession._normalize_endpoint("127.0.0.1:53962")
    assert norm1 == "http://127.0.0.1:53962", f"Sai: {norm1}"
    print("  [OK] '127.0.0.1:53962' ->", norm1)

    # 2. http://
    norm2 = StudioSession._normalize_endpoint("http://localhost:9222")
    assert norm2 == "http://localhost:9222", f"Sai: {norm2}"
    print("  [OK] 'http://localhost:9222' ->", norm2)

    # 3. ws://
    ws_sample = "ws://127.0.0.1:53962/devtools/browser/abc-123"
    norm3 = StudioSession._normalize_endpoint(ws_sample)
    assert norm3 == ws_sample, f"Sai: {norm3}"
    print("  [OK] 'ws://...' ->", norm3)

    # 4. GpmStartResult
    sr = GpmStartResult(
        success=True,
        profile_id="test-id",
        remote_debugging_address="127.0.0.1:44556"
    )
    norm4 = StudioSession._normalize_endpoint(sr)
    assert norm4 == "http://127.0.0.1:44556", f"Sai: {norm4}"
    print("  [OK] GpmStartResult ->", norm4)

    # 5. Invalid
    try:
        StudioSession._normalize_endpoint("")
        assert False, "Phải báo lỗi khi endpoint rỗng"
    except CdpConnectionError:
        print("  [OK] Bắt lỗi chính xác khi endpoint rỗng")


def test_real_cdp_connection():
    """Kiểm thử kết nối thực tế qua CDP với Profile 06."""
    print("\n--- [Kiểm thử kết nối Playwright CDP với Profile 06] ---")
    client = GpmClient()
    
    if not client.is_api_port_listening():
        print(f"Cảnh báo: Cổng GPM API ({client.port}) không mở. Bỏ qua kiểm thử thực tế.")
        return

    # Tìm profile 06
    p6 = client.find_profile("06")
    print(f"1. Tìm thấy Profile: {p6.name} (ID: {p6.id})")

    # Bật profile
    print(f"2. Khởi động Profile '{p6.name}' qua GPM API...")
    start_res = client.start_profile(p6.id, window_scale=0.8)
    print(f"   + Cổng CDP: {start_res.remote_debugging_address}")
    print(f"   + WebSocket: {start_res.websocket_debugging_url}")

    try:
        # Chờ 2 giây để Chromium ổn định
        time.sleep(2)

        # Kết nối qua Playwright CDP với StudioSession
        print("3. Khởi tạo StudioSession và kết nối CDP Playwright...")
        session = StudioSession(start_res, timeout_seconds=20.0)
        session.connect()

        assert session.is_connected, "session.is_connected phải là True"
        print("   -> Đã kết nối thành công tới Chromium của GPM [OK]")

        # Kiểm tra BrowserContext
        assert session.context is not None, "session.context không được None"
        print(f"   -> Sử dụng context mặc định của GPM (Số context: {len(session.browser.contexts)}) [OK]")
        print(f"   -> Số tab đang có trong context: {len(session.context.pages)}")

        # Lấy trang đang mở
        page = session.get_page()
        current_url = page.url
        current_title = page.title()
        print(f"   -> Thông tin tab hiện tại: URL='{current_url}', Title='{current_title}' [OK]")

        # Mở thêm tab kiểm thử nhanh
        print("4. Kiểm tra mở tab mới và điều hướng trong context GPM...")
        new_tab = session.new_page()
        new_tab.goto("about:blank")
        print("   -> Mở tab mới thành công [OK]")
        new_tab.close()
        print("   -> Đóng tab mới thành công [OK]")

        # Ngắt kết nối CDP
        print("5. Ngắt kết nối StudioSession (CDP)...")
        session.disconnect()
        assert not session.is_connected, "session.is_connected phải là False sau khi disconnect"
        print("   -> Ngắt kết nối CDP thành công, tiến trình Chrome GPM vẫn an toàn [OK]")

    finally:
        # Đóng Profile qua GPM API
        print(f"6. Gọi GPM API đóng profile '{p6.name}'...")
        close_ok = client.close_profile(p6.id)
        print(f"   -> Đóng profile: {'THÀNH CÔNG [OK]' if close_ok else 'THẤT BẠI'}")


def main():
    print("=" * 70)
    print(" KIỂM THỬ TASK 2.1: KẾT NỐI PLAYWRIGHT CDP (STUDIOSESSION)")
    print("=" * 70)

    test_normalization()
    test_real_cdp_connection()

    print("\n" + "=" * 70)
    print(" TẤT CẢ KIỂM THỬ CHO TASK 2.1 ĐÃ HOÀN TẤT THÀNH CÔNG [PASSED]!")
    print("=" * 70)


if __name__ == "__main__":
    main()
