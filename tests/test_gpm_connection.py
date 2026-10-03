"""Script kiểm thử độc lập kết nối GPM Local API và mở Profile 06."""

import sys
from pathlib import Path

# Đảm bảo mã hóa UTF-8 cho Windows console
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import time
import logging

# Thêm src vào sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.domain.errors import GpmConnectionError, GpmProfileNotFoundError, GpmStartProfileError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestGpmConnection")


def main():
    print("=" * 70)
    print(" BÀI KIỂM THỬ KẾT NỐI GPM LOCAL API VÀ KHỞI ĐỘNG PROFILE 06")
    print("=" * 70)

    client = GpmClient()
    print(f"\n[1] Kiểm tra cấu hình kết nối GPM:")
    print(f"  - Cổng API (đọc từ setting.dat): {client.port}")
    print(f"  - Địa chỉ API Base URL:         {client.base_url}")
    print(f"  - File database GPM:             {client.db_path}")

    # Kiểm tra cổng API
    is_listening = client.is_api_port_listening()
    print(f"\n[2] Trạng thái cổng API ({client.port}):")
    if is_listening:
        print(f"  -> Cổng {client.port} ĐANG LẮNG NGHE [OK]")
        conn_ok = client.check_connection()
        print(f"  -> Kiểm tra phản hồi HTTP API: {'THÀNH CÔNG [OK]' if conn_ok else 'CHƯA PHẢN HỒI'}")
    else:
        print(f"  -> Cổng {client.port} CHƯA MỞ HOẶC BỊ TỪ CHỐI KẾT NỐI.")
        print(f"     (Gợi ý: Mở phần mềm GPMLoginGlobal -> Menu 'API' -> Bấm 'Khởi động lại cổng API')")

    # Tìm thông tin profile 06
    print(f"\n[3] Truy vấn thông tin Profile '06':")
    try:
        p6 = client.find_profile("06")
        print(f"  -> Tìm thấy profile thành công [OK]:")
        print(f"     + ID Profile:      {p6.id}")
        print(f"     + Tên Profile:     {p6.name}")
        print(f"     + Proxy gán riêng: {p6.raw_proxy or 'Không dùng proxy'}")
        print(f"     + Nhân Browser:    {p6.browser_type} (Version: {p6.browser_version or 'Mặc định'})")
    except GpmProfileNotFoundError as e:
        print(f"  -> LỖI: {e}")
        return

    # Nếu API đang mở, tiến hành khởi động thử nghiệm profile
    if is_listening:
        print(f"\n[4] Gọi API GPM để khởi động Profile '{p6.name}' (ID: {p6.id})...")
        try:
            start_res = client.start_profile(p6.id, window_scale=0.9)
            print(f"  -> Khởi động THÀNH CÔNG [OK]!")
            print(f"     + Cổng CDP (Remote Debugging): {start_res.remote_debugging_address}")
            print(f"     + WebSocket URL:               {start_res.websocket_debugging_url}")
            print(f"     + Driver Path:                 {start_res.driver_path}")

            print("\n  -> Trình duyệt Chrome GPM của profile 06 đã được bật lên.")
            print("  -> Chờ 8 giây để quan sát trình duyệt...")
            time.sleep(8)

            # Đóng profile
            print(f"\n[5] Gọi API GPM để đóng Profile '{p6.name}'...")
            close_ok = client.close_profile(p6.id)
            print(f"  -> Đóng profile: {'THÀNH CÔNG [OK]' if close_ok else 'CHƯA ĐÓNG ĐƯỢC'}")

        except GpmStartProfileError as e:
            print(f"  -> LỖI khi khởi động profile: {e}")
    else:
        print(f"\n[4] Bỏ qua bước gọi API bật trình duyệt vì cổng API {client.port} chưa kết nối được.")

    print("\n" + "=" * 70)
    print(" KẾT THÚC BÀI KIỂM THỬ GIAI ĐOẠN 1")
    print("=" * 70)


if __name__ == "__main__":
    main()
