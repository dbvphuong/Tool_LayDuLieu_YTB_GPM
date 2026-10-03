# BẢN THIẾT KẾ GIAO DIỆN CHI TIẾT (UI/UX SPECIFICATION)
## Tool Lấy Dữ Liệu YouTube Studio Qua GPM-Login

---

## 1. Nguyên tắc thiết kế (Design Philosophy)

* **Phong cách tổng thể:** Hiện đại, thanh thoát, lấy cảm hứng từ các công cụ quản trị chuyên nghiệp (Modern SaaS Desktop App).
* **Tông màu chủ đạo:** **Xanh dương nhẹ nhàng dịu mắt (Soft Slate & Calm Blue)**.
  * Giúp người dùng nhìn nhiều giờ liền mà không bị chói hay mỏi mắt.
  * Độ tương phản giữa chữ và nền đạt chuẩn WCAG AA để đảm bảo đọc số liệu rõ ràng.
* **Kiểu cấu trúc:** **1 Cửa sổ duy nhất (Single Window)** với thanh Sidebar chọn Tab bên trái và Vùng hiển thị nội dung bên phải. Không mở pop-up rời rạc gây rối màn hình.

---

## 2. Bảng mã màu & Typography (Color Palette & Fonts)

| Vai trò | Tên màu | Mã HEX | Mục đích sử dụng |
|---|---|---|---|
| **Nền cửa sổ chính** | Slate Light Background | `#F1F5F9` | Nền tổng thể của toàn bộ phần mềm (mát mắt, dịu) |
| **Nền Sidebar bên trái** | Navy Slate Dark | `#1E293B` | Thanh menu điều hướng bên trái (chuyên nghiệp, sang trọng) |
| **Nền thẻ nội dung** | Pure White Card | `#FFFFFF` | Nền các khung form nhập liệu, bảng số liệu |
| **Màu thương hiệu / Điểm nhấn** | Calm Royal Blue | `#2563EB` | Nút bấm chính, tiêu đề tab đang chọn, thanh tiến trình |
| **Màu hover / tương tác** | Ocean Blue Hover | `#3B82F6` | Hiệu ứng khi rê chuột vào nút, viền focus |
| **Chữ chính (Tiêu đề, số liệu)** | Dark Slate Text | `#0F172A` | Đậm, sắc nét, tương phản tối đa trên nền sáng |
| **Chữ phụ (Nhãn, chú thích)** | Muted Gray Text | `#64748B` | Dễ chịu, không làm phân tâm |
| **Màu Log [INFO]** | Slate Blue | `#2563EB` | Thông báo dòng thông tin bình thường |
| **Màu Log [SUCCESS]** | Emerald Green | `#059669` | Báo cáo hoàn tất tác vụ, lấy dữ liệu xong |
| **Màu Log [WARNING]** | Amber Warning | `#D97706` | Cảnh báo thiếu số liệu, tải chậm |
| **Màu Log [ERROR]** | Crimson Danger | `#DC2626` | Báo lỗi kết nối, lỗi trang |

* **Font chữ hệ thống:** `Segoe UI`, `SF Pro Display`, `Roboto` (Kích thước: 13px - 14px cho chữ thường; 16px - 20px cho tiêu đề).

---

## 3. Bản vẽ phác thảo bố cục (Wireframe ASCII Layout)

```text
+-------------------------------------------------------------------------------------------------------------------------+
| [O] YTB Studio Data Collector v1.0 - GPM Automation                                                          [-] [x]    |
+-------------------+-----------------------------------------------------------------------------------------------------+
|                   |                                                                                                     |
|  [>] YTB COLLECT  |   [ Tab: THU THẬP DỮ LIỆU ]                                                                         |
|  GPM Edition      |                                                                                                     |
|                   |   +-- 1. CHỌN PROFILE GPM (MULTI-PROFILE & ĐA LUỒNG) --------------------------------------------+  |
|  ================ |   | [x] Chọn tất cả | Đã chọn: 3/12 profile  | Số luồng song song: [ 2 ] [ Làm mới ]                 |  |
|                   |   | +------------------------------------------------------------------------------------------+ |  |
|  [+] Thu thập     |   | | [x] 06 - Kênh Hướng Dẫn    | Proxy: 103.23.x.x:8080 | Đã sẵn sàng                        | |  |
|      (Active)     |   | | [x] 01 - Kênh Tin Tức      | Proxy: 103.21.x.x:8080 | Đã sẵn sàng                        | |  |
|                   |   | | [x] 07 - Kênh Giải Trí     | Proxy: 103.24.x.x:8080 | Đã sẵn sàng                        | |  |
|  [*] Lịch sử      |   | | [ ] 02 - Kênh Âm Nhạc      | Proxy: 103.22.x.x:8080 | Chưa chọn                          | |  |
|                   |   | +------------------------------------------------------------------------------------------+ |  |
|  [#] Nhật ký Logs |   +----------------------------------------------------------------------------------------------+  |
|                   |                                                                                                     |
|  [o] Cài đặt      |   +-- 2. CẤU HÌNH DỮ LIỆU CẦN LẤY ---------------------------------------------------------------+  |
|                   |   | Áp dụng:     Cho toàn bộ các profile/kênh đã chọn ở trên                                     |  |
|                   |   | Chọn video:  (o) Theo số lượng gần nhất: [ 10 ] video mới nhất (hoặc chọn 5, 20, 50)         |  |
|                   |   |              ( ) Theo thời gian đăng:    [ 28 ngày qua              [v] ]                    |  |
|                   |   |              ( ) Toàn bộ video trên kênh ( ) Chọn thủ công cụ thể...                         |  |
|                   |   | Khung ngày:  Phân tích số liệu trong:    [ 28 ngày qua              [v] ]                    |  |
|                   |   | Mức cào:     ( ) Nhanh (Tổng quan)       (o) Tiêu chuẩn (Reach + Traffic)   ( ) Đầy đủ       |  |
|                   |   +----------------------------------------------------------------------------------------------+  |
|                   |                                                                                                     |
|                   |   +-- 3. ĐIỀU KHIỂN & TIẾN TRÌNH ĐA LUỒNG -------------------------------------------------------+  |
|                   |   |  [ >>> BẮT ĐẦU THU THẬP <<< ]      [ || Tạm dừng ]      [ [] Mở thư mục kết quả ]            |  |
|                   |   |                                                                                              |  |
|                   |   |  Tiến trình tổng: [==================>                             ] 33% (1/3 kênh hoàn tất) |  |
|                   |   |  +-- Trạng thái các luồng đang chạy: ------------------------------------------------------+ |  |
|                   |   |  | Luồng 1 [06 - Kênh Hướng Dẫn]: Đang xuất báo cáo Nguồn truy cập (Video 3/10)            | |  |
|                   |   |  | Luồng 2 [01 - Kênh Tin Tức]:   Đang mở tab Analytics trang tổng quan                    | |  |
|                   |   |  | Chờ trong hàng đợi: [07 - Kênh Giải Trí]                                                | |  |
|                   |   |  +-----------------------------------------------------------------------------------------+ |  |
|  ---------------- |   +----------------------------------------------------------------------------------------------+  |
|  GPM API: 19996   |                                                                                                     |
|  Trạng thái: OK   |   [ Xem nhanh log mới nhất: ]                                                                       |
|  Số luồng: 2      |   | [10:25:01] [SUCCESS] [Luồng 1] Đã kết nối vào profile 06 qua CDP port 54321                  |  |
+-------------------+-----------------------------------------------------------------------------------------------------+
```

---

## 4. Chi tiết các màn hình bên phải (Content Views)

### 4.1. Màn hình 1: Thu thập dữ liệu (Collector View)
* **Khối 1: Quản lý Profile GPM (Multi-Profile & Chạy Đa Luồng)**
  * Bảng danh sách toàn bộ Profile lấy từ GPM:
    * Cột Checkbox tích chọn từng profile hoặc nút **"Chọn tất cả"** / **"Bỏ chọn tất cả"**.
    * Hiển thị rõ: Tên Profile, ID, Địa chỉ Proxy được gán, Trạng thái.
    * Nhãn đếm: *"Đã chọn: X profile"*.
  * **Cấu hình Số luồng chạy song song (Concurrency)**:
    * Ô số `SpinBox`: Mặc định `2` luồng (cho phép chọn từ `1` đến `10` luồng tùy theo tài nguyên RAM/CPU và proxy của bạn).
    * Hàng đợi tự động (Queue): Khi chạy, tool mở đồng thời tối đa `N` profile. Bất kỳ profile nào hoàn thành sẽ tự động nhường chỗ cho profile tiếp theo trong hàng đợi cho đến khi hoàn tất 100%.
  * Nút "Làm mới danh sách" để tự động tải lại nếu vừa tạo thêm profile trong GPM.
* **Khối 2: Cấu hình Thu thập (Áp dụng đồng loạt cho các kênh đã chọn)**
  * Tự động nhận diện `channel_id` và tên kênh của từng profile khi vào Studio.
  * **Cách chọn danh sách video cần cào:**
    * **Chế độ 1: Theo số lượng video gần nhất (Mặc định):** Cho phép nhập số lượng tùy ý hoặc bấm chọn nhanh `5`, `10`, `20`, `50` video mới xuất bản gần đây nhất.
    * **Chế độ 2: Theo thời gian đăng video:** Chọn các video được xuất bản trong *7 ngày qua*, *28 ngày qua*, *90 ngày qua*, hoặc tùy chỉnh ngày bắt đầu/kết thúc.
    * **Chế độ 3: Toàn bộ video** trên kênh.
  * **Khung thời gian phân tích số liệu (Analytics Date Range):**
    * Chọn cửa sổ ngày cần lấy số liệu trong YouTube Studio: *28 ngày qua* (mặc định), *90 ngày qua*, *365 ngày qua*, hoặc *Toàn thời gian (Lifetime)*.
  * **Mức độ thu thập:** *Nhanh* / *Tiêu chuẩn* / *Đầy đủ*.
* **Khối 3: Bảng điều khiển hành động & Giám sát tiến độ đa luồng**
  * Nút to nhất: "BẮT ĐẦU THU THẬP" (Primary Blue).
  * Thanh tiến trình tổng thể (ví dụ: `1/3 kênh hoàn thành - 33%`).
  * Khung danh sách trạng thái từng luồng (Worker Status List): Thấy rõ luồng nào đang làm gì, ở video nào, kênh nào đang chờ trong hàng đợi.

---

### 4.2. Màn hình 2: Lịch sử & Kết quả (Runs & History View)
```text
+-----------------------------------------------------------------------------------------------------+
|  LỊCH SỬ CÁC LẦN THU THẬP                                                  [ Làm mới ] [ Mở folder ]|
+-----------------------------------------------------------------------------------------------------+
|  Thời gian          | Tên Kênh       | Phạm vi  | Số video | Trạng thái        | Thao tác           |
|---------------------+----------------+----------+----------+-------------------+--------------------|
|  03/10/2026 10:20   | Kênh Hướng Dẫn | 28 ngày  | 10 video | [x] Hoàn tất 100% | [Mở thư mục] [Xem] |
|  02/10/2026 15:10   | Kênh Tin Tức   | 90 ngày  | 5 video  | [!] Thiếu 1 video | [Chạy lại lỗi]     |
|  01/10/2026 09:00   | Kênh Âm Nhạc   | 28 ngày  | 20 video | [x] Hoàn tất      | [Mở thư mục] [Xem] |
+-----------------------------------------------------------------------------------------------------+
|  Chi tiết lần chạy đang chọn:                                                                       |
|  - Thư mục: runs/2026-10-03_kenh-huong-dan_28d/                                                    |
|  - File tóm tắt: README.md (Đã sinh đầy đủ cho AI & Người dùng)                                    |
+-----------------------------------------------------------------------------------------------------+
```

---

### 4.3. Màn hình 3: Nhật ký chi tiết (Live Logs View)
* Khung Text Area chiếm trọn màn hình, font chữ Monospace (`Consolas` / `Fira Code`) để đọc log thẳng hàng.
* Nền tối dịu mắt (`#0F172A`) với các dòng chữ có màu theo cấp độ (INFO, SUCCESS, WARN, ERROR).
* Thanh công cụ trên đầu:
  * Nút "Sao chép toàn bộ" (Copy all)
  * Nút "Xóa nhật ký" (Clear)
  * Checkbox "Tự động cuộn theo dòng mới" (Auto-scroll)

---

### 4.4. Màn hình 4: Cài đặt (Settings View)
* **Kết nối GPM:**
  * Địa chỉ GPM API: `http://127.0.0.1:19996`
  * Nút "Kiểm tra kết nối ngay" (Ping API)
  * Thư mục cài đặt GPM: `D:\GPMLogin\GPMLoginGlobal`
* **Lưu trữ & Automation:**
  * Thư mục lưu kết quả: `e:\YOUTOBE\.TẠO SKILL\Tool_LayDuLieu_YTB_GPM\runs`
  * Thời gian chờ tải trang (Page Timeout): 30s
  * Checkbox: "Giữ file thô (raw XLSX/CSV) từ YouTube Studio" (Mặc định: BẬT)
  * Checkbox: "Tự động xuất file README.md và JSONL cho AI" (Mặc định: BẬT)
  * Nút "Lưu Cài Đặt" (Xanh dương)

---

## 5. Kiến trúc kỹ thuật PySide6 (Widget Tree)

```text
MainWindow (QMainWindow)
├── CentralWidget (QWidget)
│   └── MainLayout (QHBoxLayout - margins: 0, spacing: 0)
│       ├── SidebarWidget (QWidget - fixed width: 220px, style: Navy Slate)
│       │   ├── AppHeader (Logo + Title Label)
│       │   ├── NavButtonGroup (QButtonGroup)
│       │   │   ├── btn_nav_collector (QPushButton - checked)
│       │   │   ├── btn_nav_history (QPushButton)
│       │   │   ├── btn_nav_logs (QPushButton)
│       │   │   └── btn_nav_settings (QPushButton)
│       │   ├── Spacer (QSpacerItem)
│       │   └── StatusIndicator (GPM API status LED + label)
│       │
│       └── ContentStack (QStackedWidget - background: #F1F5F9)
│           ├── PageCollector (QWidget) -> Chứa Form chọn profile, video, nút Bắt đầu
│           ├── PageHistory (QWidget)   -> Chứa QTableWidget lịch sử runs
│           ├── PageLogs (QWidget)      -> Chứa QTextEdit màu đen cho live logs
│           └── PageSettings (QWidget)  -> Chứa Form cấu hình GPM và thư mục
```
