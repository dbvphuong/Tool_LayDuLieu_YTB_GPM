# YÊU CẦU VÀ ĐẶC TẢ KỸ THUẬT DỰ ÁN
## Tool Lấy Dữ Liệu YouTube Studio Qua GPM-Login

---

## 1. Thông tin chung & Môi trường triển khai

* **Kho mã nguồn (Git Repository):** [https://github.com/dbvphuong/Tool_LayDuLieu_YTB_GPM.git](https://github.com/dbvphuong/Tool_LayDuLieu_YTB_GPM.git)
* **Hệ điều hành:** Windows 10/11 x64
* **Môi trường Python:** Python 3.12.1 x64 (sử dụng môi trường ảo `.venv` đặt tại thư mục dự án)
* **Phần mềm Antidetect Browser:**
  * Tên phần mềm: **GPMLogin Global** (Bản quyền trả phí).
  * Thư mục cài đặt: `D:\GPMLogin\GPMLoginGlobal` (chứa `GPMLoginGlobal.exe`).
  * Thư mục lưu dữ liệu profile: `D:\GPMLogin\Profile_Chrome_GPM`.
  * Cổng Local API mặc định: **`19996`** (đọc tự động từ cấu hình `setting.dat` của GPM).
* **Profile kiểm thử mẫu:** Profile mang tên hoặc ID **`06`**.
* **Ngôn ngữ YouTube Studio:** **Tiếng Việt** (YouTube Studio giao diện tiếng Việt Nam).

---

## 2. Yêu cầu vận hành cốt lõi (Core Requirements)

### 2.1. Quản lý Profile và Giữ nguyên Proxy (Cực kỳ quan trọng)
* **Tự động mở profile:** Tool có tính năng lấy danh sách profile từ API GPM, cho phép người dùng chọn và bấm chạy thì tool sẽ **tự động gọi API của GPM để bật profile lên**.
* **Tuyệt đối tuân thủ Browser & Proxy của GPM:**
  * BẮT BUỘC sử dụng đúng trình duyệt Chrome do chính GPM khởi chạy (GPMLogin Chromium với fingerprint tùy biến).
  * BẮT BUỘC giữ nguyên 100% **Proxy đã gán cho profile đó** trong GPM. Không mở Chrome bên ngoài làm lộ IP thật.
  * **Cơ chế kỹ thuật thực thi:**
    1. Tool gửi request `GET /api/v3/profiles/start/{id}` tới GPM API Local (`127.0.0.1:19996`).
    2. GPM tự khởi chạy Chromium của profile với đúng proxy và fingerprint đã cấu hình, trả về chuỗi kết nối CDP (ví dụ `127.0.0.1:xxxxx` hoặc `ws://127.0.0.1:xxxxx/devtools/browser/...`).
    3. Playwright chỉ thực hiện lệnh `playwright.chromium.connect_over_cdp(cdp_url)` để gắn vào trình duyệt đó. Tuyệt đối không gọi `chromium.launch()`.

### 2.2. Hỗ trợ giao diện tiếng Việt của YouTube Studio
* Robot nhận diện chính xác các phần tử trên YouTube Studio:
  * Nút điều hướng: "Số liệu phân tích" (Analytics), "Nội dung" (Content).
  * Bộ lọc ngày: "28 ngày qua", "90 ngày qua", tùy chỉnh ngày.
  * Tab phân tích: "Tổng quan", "Phạm vi tiếp cận", "Mức độ tương tác", "Đối tượng người xem".
  * Thao tác xuất dữ liệu: "Xuất dữ liệu" -> Tải file Excel/CSV.
* Bộ parser đọc file Excel/CSV xuất ra phải ánh xạ chính xác các tiêu đề cột tiếng Việt (ví dụ: *Lượt xem, Thời gian xem (giờ), Thời lượng xem trung bình, Số người đăng ký, Số lượt hiển thị, Tỷ lệ nhấp của lượt hiển thị*) về các trường dữ liệu tiếng Anh chuẩn trong hệ thống (`views`, `watch_time_hours`, `average_view_duration_seconds`, `impressions`, `ctr_percent`).

---

## 3. Đặc tả Yêu cầu Giao diện Người dùng (UI/UX Requirements)

### 3.1. Phong cách & Màu sắc chủ đạo
* **Chủ đạo:** **Xanh dương nhẹ nhàng dịu mắt (Soft Slate & Blue)**.
* **Mục tiêu thị giác:** Dịu mắt, làm việc thoải mái khi chạy liên tục trong thời gian dài; màu chữ sắc nét, độ tương phản cao, dễ nhìn, font chữ hiện đại (Segoe UI / Roboto).
* **Bảng màu định hướng:**
  * Nền chính (Window Background): `#F0F4F8` (Sáng nhẹ êm dịu) hoặc `#1A2232` (Dark Blue êm mắt). Hỗ trợ Dark/Light chuyển đổi êm dịu.
  * Màu thanh Sidebar: `#1E293B` (Xanh navy trầm thanh lịch).
  * Màu thương hiệu / Nút nhấn (Primary Accent): `#2563EB` / `#3B82F6` (Xanh dương tươi vừa, nổi bật nút hành động).
  * Nút hover / active: `#1D4ED8` / `#60A5FA`.
  * Khối thẻ (Cards/Panels): `#FFFFFF` với bo góc mềm mại (Border Radius 8px - 10px).
  * Chữ chính: `#0F172A` (trên nền sáng) hoặc `#F8FAFC` (trên nền tối), chữ phụ `#64748B`.

### 3.2. Bố cục 1 Cửa Sổ (Single Window Navigation)
Giao diện không mở cửa sổ con rải rác mà gom trong 1 cửa sổ ứng dụng duy nhất, chia làm 2 phần:
* **Bên trái: Thanh điều hướng (Sidebar Navigation - Chiều rộng cố định ~220px):**
  * Logo và Tên Tool ("YTB Studio Collector").
  * Nút Tab 1: **Thu thập dữ liệu** (Icon thu thập / Dashboard - Tab mặc định).
  * Nút Tab 2: **Lịch sử & Kết quả** (Icon thư mục / Báo cáo).
  * Nút Tab 3: **Nhật ký (Logs)** (Icon terminal / văn bản - Bấm vào là xem chi tiết log tiến độ thực thi).
  * Nút Tab 4: **Cài đặt (Settings)** (Icon bánh răng).
  * Chân Sidebar: Hiển thị trạng thái kết nối GPM API (Đèn xanh: Đã kết nối / Đèn đỏ: Chưa bật GPM).
* **Bên phải: Vùng nội dung chính (Main Content Panel - Chiều rộng co giãn theo cửa sổ):**
  * Hiển thị giao diện tương ứng với Tab được chọn ở Sidebar.

---

## 4. Chi tiết các Tab chức năng

### Tab 1: Thu thập dữ liệu (Trang chủ)
* **Khu vực chọn Profile GPM:**
  * Dropdown danh sách profile lấy trực tiếp từ GPM (tự động load, có nút "Làm mới").
  * Nút bấm tiện ích: "Bật Profile" / "Kiểm tra Studio".
* **Khu vực chọn Phạm vi dữ liệu (Linh hoạt theo Số lượng hoặc Thời gian):**
  * Chọn Kênh (tự nhận diện sau khi kết nối Studio).
  * **Cách chọn danh sách video:**
    * **Chế độ 1: Theo số lượng video gần nhất (Mặc định):** Cho phép nhập số lượng (ví dụ: 5, 10, 20, 50 video mới nhất).
    * **Chế độ 2: Theo thời gian đăng video:** Lọc các video xuất bản trong *7 ngày qua*, *28 ngày qua*, *90 ngày qua*, hoặc tùy chỉnh ngày.
    * **Chế độ 3: Toàn bộ video** trên kênh.
    * **Chế độ 4: Tự chọn thủ công** trong danh sách.
  * **Khung thời gian phân tích số liệu (Analytics Date Range):** *28 ngày qua*, *90 ngày qua*, *365 ngày qua*, hoặc *Toàn thời gian (Lifetime)*.
  * Mức thu thập: Radio chọn *Nhanh* / *Tiêu chuẩn* / *Đầy đủ*.
* **Khu vực Nút Hành động & Tiến độ:**
  * Nút to nổi bật: **[ BẮT ĐẦU THU THẬP ]** (Màu xanh dương).
  * Nút phụ: **[ Tạm dừng ]**, **[ Mở thư mục kết quả ]**.
  * Thanh tiến trình tổng (Progress bar 0 - 100%).
  * Khung tóm tắt trạng thái hiện tại (Ví dụ: *"Đang xuất báo cáo Nguồn truy cập cho video 06..."*).

### Tab 2: Lịch sử & Kết quả
* Danh sách các đợt chạy trước đó trong thư mục `runs/`.
* Bảng hiển thị: Ngày giờ chạy, Tên kênh, Số video đã cào, Trạng thái (Thành công / Thiếu lỗi).
* Các nút thao tác nhanh:
  * Nút "Mở thư mục chứa file"
  * Nút "Xem file README tóm tắt"
  * Nút "Chạy lại các mục lỗi (Retry)"

### Tab 3: Nhật ký (Logs)
* Cửa sổ hiển thị toàn bộ log chi tiết dòng lệnh (real-time stream).
* Phân loại màu log: [INFO] trắng/xanh, [SUCCESS] xanh lá, [WARNING] vàng, [ERROR] đỏ.
* Các nút tiện ích:
  * Nút "Sao chép toàn bộ log" (Copy to clipboard).
  * Nút "Xóa màn hình log".
  * Nút "Lưu file log ra máy".

### Tab 4: Cài đặt (Settings)
* **Cấu hình GPM:**
  * Cổng API GPM: Mặc định `19996` (có ô nhập để sửa nếu đổi port).
  * Đường dẫn GPM: `D:\GPMLogin\GPMLoginGlobal`.
  * Nút "Kiểm tra kết nối API GPM ngay".
* **Cấu hình Thu thập:**
  * Đường dẫn lưu dữ liệu kết quả: Mặc định `runs/` (có nút Browse chọn thư mục khác).
  * Thời gian chờ tối đa (Timeout) mỗi trang: Mặc định 30 giây.
  * Tùy chọn thu thập doanh thu: Checkbox (Mặc định: TẮT để bảo mật thông tin nhạy cảm).
  * Tự động đóng profile sau khi cào xong: Checkbox.

---

## 5. Quy tắc Kiểm tra & Nghiệm thu chất lượng (Quality Gates)

1. **Khởi chạy đúng profile & proxy:** Mở đúng profile GPM đã chọn, IP và proxy không bị thay đổi hoặc rò rỉ.
2. **Kiểm tra kênh đúng:** Xác nhận `channel_id` trong Studio trùng khớp với kênh muốn lấy, nếu sai phải cảnh báo dừng.
3. **Tính toàn vẹn dữ liệu:**
   * Lưu trọn vẹn file thô (raw) của YouTube Studio tải về.
   * File chuẩn hóa CSV/JSONL không được suy diễn số, nếu YouTube không có số thì ghi rõ `null` và lý do.
4. **Trải nghiệm ứng dụng không giật lag:** Quá trình robot chạy automation Playwright phải chạy trên Worker Thread riêng biệt, giao diện PySide6 luôn mượt mà, log nhảy liên tục, không bị treo ứng dụng ("Not Responding").
