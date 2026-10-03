# KẾ HOẠCH TRIỂN KHAI CHI TIẾT (IMPLEMENTATION PLAN)
## Dự án: Tool Lấy Dữ Liệu YouTube Studio Qua GPM-Login

---

## 1. Nguyên tắc triển khai

1. **Tuân thủ đúng yêu cầu người dùng:** Đúng profile GPM, đúng Chrome GPM, giữ nguyên Proxy, hỗ trợ tiếng Việt, giao diện Xanh dương dịu mắt (Soft Blue), 1 cửa sổ có Sidebar.
2. **Làm đến đâu kiểm thử đến đó:** Mỗi Phase đều có bài test cụ thể để nghiệm thu trước khi bước sang Phase tiếp theo.
3. **Không làm hỏng dữ liệu hoặc tài khoản:** Chế độ chỉ đọc (read-only), không chỉnh sửa cài đặt kênh YouTube.

---

## 2. Danh sách Task theo từng giai đoạn (Checklist)

### Giai đoạn 0: Khởi tạo Môi trường & Git
- [x] **Task 0.1:** Khởi tạo Git repository cục bộ, cấu hình remote `https://github.com/dbvphuong/Tool_LayDuLieu_YTB_GPM.git` và commit bộ tài liệu thiết kế.
- [x] **Task 0.2:** Tạo môi trường ảo Python `.venv` tại thư mục dự án.
- [x] **Task 0.3:** Cài đặt toàn bộ dependencies trong `requirements.txt` (`pyside6`, `playwright`, `httpx`, `pandas`, `openpyxl`, `pydantic`).

---

### Giai đoạn 1: Kết nối GPM Local API & Kiểm thử Profile 06
- [x] **Task 1.1:** Xây dựng module `src/ytb_gpm_collector/integrations/gpm/client.py`:
  - Đọc cấu hình port API từ `setting.dat` (mặc định `19996`).
  - Hàm `get_profiles()`: Lấy danh sách profile (ID, Tên, Proxy).
  - Hàm `start_profile(profile_id)`: Gọi API GPM để mở profile, nhận lại `remote_debugging_address` (CDP URL).
  - Hàm `close_profile(profile_id)`: Đóng profile qua API khi cần.
- [x] **Task 1.2:** Viết script kiểm thử độc lập (`tests/test_gpm_connection.py`):
  - Kiểm tra kết nối tới GPM API.
  - Mở thử nghiệm profile **`06`**.
  - Kiểm tra và in ra thông tin: Tên profile, IP/Proxy của profile, Cổng CDP.
  - *Tiêu chí nghiệm thu:* Cửa sổ Chromium GPM của profile 06 tự bật lên với đúng proxy, script lấy được cổng CDP hợp lệ.

---

### Giai đoạn 2: Tự động hóa YouTube Studio qua Playwright CDP
- [ ] **Task 2.1:** Xây dựng module kết nối Playwright CDP (`integrations/studio/session.py`):
  - Kết nối vào Chrome GPM bằng `playwright.chromium.connect_over_cdp(cdp_url)`.
  - Không khởi tạo trình duyệt mới, dùng chính context đang chạy.
- [ ] **Task 2.2:** Xây dựng module nhận diện kênh & điều hướng (`integrations/studio/pages/analytics.py`):
  - Truy cập `https://studio.youtube.com`.
  - Kiểm tra trạng thái đăng nhập và trích xuất `channel_id`, `channel_name`.
  - Điều hướng tới trang "Số liệu phân tích" (Analytics).
- [ ] **Task 2.3:** Xây dựng module xuất báo cáo Studio tiếng Việt:
  - Chọn khoảng thời gian (28 ngày qua).
  - Thao tác mở chế độ xem nâng cao và xuất báo cáo (Export) Excel/CSV.
  - Bắt sự kiện tải file và lưu nguyên vẹn vào thư mục `runs/<run_id>/raw/`.
  - Chụp ảnh biểu đồ tổng quan đối chiếu lưu vào `runs/<run_id>/evidence/`.

---

### Giai đoạn 3: Chuẩn hóa dữ liệu & Sinh báo cáo
- [ ] **Task 3.1:** Xây dựng module Parser đọc file Excel/CSV (`integrations/exports/readers.py`):
  - Nhận diện các cột tiếng Việt: *Lượt xem, Thời gian xem (giờ), Tỷ lệ nhấp của lượt hiển thị, Số lượt hiển thị, Thời lượng xem trung bình*.
- [ ] **Task 3.2:** Xây dựng module Chuẩn hóa (`integrations/exports/normalize.py`):
  - Chuyển đổi về cấu trúc số chuẩn, xử lý dữ liệu trống (`zero`, `not_available`, `failed`).
  - Xuất ra các file sạch: `videos.csv`, `videos.jsonl`, `traffic_sources.csv` trong `data/`.
- [ ] **Task 3.3:** Xây dựng module Báo cáo (`storage/runs.py`):
  - Tự động sinh `README.md` tóm tắt kết quả (cho người dùng đọc).
  - Sinh `manifest.json` và `quality_report.json` (cho AI đọc và đối chiếu chất lượng).

---

### Giai đoạn 4: Giao diện PySide6 (Giao diện Xanh dương, 1 Cửa sổ, Sidebar)
- [ ] **Task 4.1:** Xây dựng kiến trúc giao diện & Stylesheet chuẩn Soft Blue:
  - Khung chính `MainWindow` gồm Sidebar bên trái (Navy Slate `#1E293B`) và `QStackedWidget` bên phải.
  - Bộ QSS (Qt Style Sheet) tối ưu màu sắc xanh dương nhẹ nhàng dịu mắt, chữ tương phản cao.
- [ ] **Task 4.2:** Xây dựng **Tab 1: Thu thập dữ liệu**:
  - Bảng danh sách chọn nhiều Profile GPM (kèm proxy, checkbox chọn từng cái hoặc chọn tất cả).
  - Cấu hình số luồng chạy song song (1 - 10 luồng, mặc định 2).
  - Nút "Làm mới danh sách profile".
  - Lựa chọn video: Theo số lượng gần nhất (5, 10, 20...) HOẶC theo khoảng ngày đăng, hoặc toàn bộ video.
  - Lựa chọn khung thời gian phân tích số liệu (28 ngày qua, 90 ngày...).
  - Nút bấm to nổi bật **[ BẮT ĐẦU THU THẬP ]**.
  - Thanh tiến trình tổng (% hoàn thành) và bảng trạng thái các luồng đang chạy.
- [ ] **Task 4.3:** Xây dựng **Tab 2: Lịch sử & Kết quả**:
  - Bảng danh sách các đợt chạy trong `runs/`.
  - Nút mở thư mục chứa file, nút xem nhanh README tóm tắt.
- [ ] **Task 4.4:** Xây dựng **Tab 3: Nhật ký (Logs)**:
  - Khung hiển thị log real-time màu sắc trực quan (INFO, SUCCESS, WARNING, ERROR).
  - Nút "Sao chép toàn bộ log", nút "Xóa log".
- [ ] **Task 4.5:** Xây dựng **Tab 4: Cài đặt (Settings)**:
  - Form cấu hình cổng GPM API (`19996`), số luồng song song mặc định, thư mục lưu kết quả, timeout.
- [ ] **Task 4.6:** Đấu nối Worker Thread Pool (`QThreadPool` / `QThread` Concurrency Queue):
  - Cơ chế hàng đợi luân phiên: chạy tối đa N luồng cùng lúc; xong profile nào lập tức đóng profile đó và bốc profile tiếp theo trong hàng đợi.
  - Bắn tín hiệu `Signal` cập nhật UI mượt mà, log real-time theo từng luồng, không đơ lag app.

---

### Giai đoạn 5: Kiểm thử hoàn chỉnh (E2E Test) & Hoàn thiện
- [ ] **Task 5.1:** Thực hiện chạy kiểm thử toàn trình từ UI với profile **`06`**.
- [ ] **Task 5.2:** Kiểm tra gói kết quả sinh ra trong `runs/`: file gốc `raw/`, file sạch `data/`, ảnh `evidence/`, báo cáo `README.md`.
- [ ] **Task 5.3:** Viết hướng dẫn sử dụng chi tiết trong `README.md` gốc của dự án.
- [ ] **Task 5.4:** Git commit toàn bộ mã nguồn và hướng dẫn cách đẩy lên GitHub.
