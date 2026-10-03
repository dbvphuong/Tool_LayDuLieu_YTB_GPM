# Tool Lấy Dữ Liệu YouTube Studio Qua GPM-Login

Hệ thống desktop automation chuyên nghiệp thu thập dữ liệu phân tích chuyên sâu từ **YouTube Studio** thông qua trình duyệt antidetect **GPMLogin Global**, phục vụ nghiên cứu và phân tích kênh YouTube bằng AI và con người.

---

## 🌟 Tính năng nổi bật

* **Bảo toàn 100% môi trường GPM & Proxy độc lập:** 
  Tự động gọi API của GPMLogin để mở profile, kết nối điều khiển qua giao thức Chrome DevTools Protocol (CDP), giữ nguyên tuyệt đối dấu vân tay trình duyệt (browser fingerprint), cookie đăng nhập và **Proxy riêng biệt đã gán cho từng profile**, ngăn chặn triệt để nguy cơ lộ IP thật hay checkpoint tài khoản Google.
* **Hỗ trợ Multi-Kênh & Chạy Đa Luồng (Concurrency Thread Pool):** 
  Cho phép tích chọn hàng loạt kênh cùng lúc, lọc theo Nhóm Profile GPM, cấu hình số luồng chạy song song tối đa (1 - 10 luồng). Cơ chế hàng đợi luân phiên tự động: hoàn tất profile nào lập tức giải phóng và bốc profile tiếp theo, tối ưu tài nguyên RAM và CPU.
* **Hỗ trợ trọn vẹn YouTube Studio tiếng Việt:** 
  Tự động nhận diện kênh (tên kênh, Channel ID), điều hướng mục Số liệu phân tích (Analytics), chọn kỳ báo cáo (28 ngày qua, 90 ngày, 365 ngày...), mở Chế độ xem nâng cao (`/explore`), và tải trọn vẹn gói báo cáo nén.
* **Chụp ảnh bằng chứng Full HD (1920×1080) không co rút:** 
  Tích hợp cơ chế Viewport ảo độ phân giải cao độc lập với kích thước cửa sổ vật lý của Chromium trên màn hình. Bức ảnh chụp bảng nâng cao và biểu đồ đối chiếu luôn hiển thị đầy đủ 100% tất cả các cột (*Số lượt xem, Thời gian xem, Người đăng ký, Doanh thu, Lượt hiển thị hình thu nhỏ, Tỷ lệ nhấp CTR...*) và các dòng video mà không bị che khuất hay xuất hiện thanh cuộn ngang.
* **Cơ chế Timeout linh hoạt tùy chỉnh:** 
  Tích hợp cấu hình Timeout (10s – 300s, mặc định 60s) ngay tại giao diện Cài đặt, tự động co giãn theo tỷ lệ thông minh cho từng thao tác DOM, click và tải file, giúp công cụ chạy mượt mà ngay cả khi proxy chậm hoặc mạng lag.
* **Dữ liệu 2 lớp chuẩn hóa cao cấp:** 
  * Lớp 1 (`raw/`): Bảo toàn nguyên vẹn file thô gốc tải về từ YouTube Studio (tệp zip, các bảng dữ liệu gốc tiếng Việt UTF-8/UTF-16).
  * Lớp 2 (`data/`): Tự động giải nén và làm sạch, chuẩn hóa thành các tệp tiêu chuẩn gồm `videos.csv`, `videos.jsonl`, `traffic_sources.csv`, `daily_metrics.csv`, `channel.json`.
* **Báo cáo tự động cho AI và Người dùng:** 
  Mỗi lượt chạy tự động sinh:
  * `manifest.json`: Chứa bản kê chi tiết toàn bộ tệp tin kèm mã băm SHA-256 đối chiếu tính toàn vẹn.
  * `quality_report.json`: Báo cáo đánh giá chất lượng dữ liệu và tỷ lệ hoàn thiện theo tiêu chuẩn AI (Data Completeness Score).
  * `README.md`: Báo cáo markdown trực quan tóm tắt hiệu suất kênh, top video thịnh hành và bảng phân phối nguồn lưu lượng.
* **Giao diện Desktop hiện đại (PySide6 / Qt):** 
  Thiết kế chuẩn màu **Soft Slate & Navy Blue** dịu mắt, gồm Sidebar điều hướng và 4 Tab chức năng:
  1. *Thu thập dữ liệu*: Chọn profile, nhóm, số luồng, kỳ báo cáo, theo dõi tiến trình và trạng thái các luồng thời gian thực.
  2. *Lịch sử & Kết quả*: Xem lại lịch sử các đợt chạy từ cơ sở dữ liệu SQLite, 1-click mở thư mục đợt chạy hoặc xem nhanh báo cáo.
  3. *Nhật ký (Logs)*: Màn hình log real-time phân loại màu sắc (INFO, SUCCESS, WARNING, ERROR), hỗ trợ tìm kiếm và sao chép.
  4. *Cài đặt*: Tùy chỉnh cổng API GPM, số luồng mặc định, timeout chờ mạng, thư mục lưu dữ liệu.
* **Khởi động 1-Click tiện lợi:** Cung cấp sẵn file `CHAY_TOOL.bat` và `CHAY_TOOL.vbs` giúp mở ứng dụng ngay tức thì trên Windows.

---

## 📂 Cấu trúc thư mục dự án

```text
Tool_LayDuLieu_YTB_GPM/
├── docs/                               # Toàn bộ tài liệu đặc tả và thiết kế kỹ thuật
│   ├── KIEN_TRUC_TOOL_LAY_DU_LIEU_YTB_GPM.md  # Clean Architecture & luồng dữ liệu
│   ├── YEU_CAU_VA_DAC_TA_KY_THUAT.md          # Đặc tả yêu cầu kỹ thuật chi tiết
│   ├── THIET_KE_GIAO_DIEN.md                  # Bản thiết kế giao diện PySide6 & QSS
│   └── PLAN_TRIEN_KHAI.md                     # Kế hoạch và tiến độ triển khai chi tiết
├── src/                                # Mã nguồn chính của ứng dụng
│   └── ytb_gpm_collector/
│       ├── domain/                     # Entities & Value Objects (kênh, video, run, chất lượng)
│       ├── integrations/
│       │   ├── gpm/                    # Client kết nối GPM Local API
│       │   ├── studio/                 # Playwright CDP session, nhận diện kênh, Analytics Page
│       │   ├── exports/                # Đọc tệp xuất Studio, chuẩn hóa sạch và sinh báo cáo AI
│       │   └── storage/                # Quản lý thư mục runs/, manifest SHA-256, SQLite History
│       ├── application/                # Concurrency Thread Pool Coordinator (QThreadPool)
│       ├── interfaces/desktop/         # Giao diện PySide6 (MainWindow, Sidebar, 4 Pages, Theme)
│       └── config.py                   # Quản lý cấu hình toàn cục (config.json)
├── tests/                              # Bộ kiểm thử tự động (Unit tests & E2E tests)
├── runs/                               # Thư mục chứa kết quả sau mỗi đợt chạy (tự sinh)
├── CHAY_TOOL.bat                       # Script khởi động tool 1-click (hiện cửa sổ cmd)
├── CHAY_TOOL.vbs                       # Script khởi động tool 1-click không hiện màn hình đen
├── main.py                             # Điểm khởi chạy chính của ứng dụng
├── config.example.json                 # Tệp cấu hình mẫu
├── requirements.txt                    # Danh sách thư viện Python cần thiết
└── README.md                           # Hướng dẫn sử dụng và giới thiệu dự án
```

---

## 📦 Cấu trúc gói dữ liệu đầu ra (`runs/<run_id>/`)

Sau mỗi lượt thu thập kênh thành công, hệ thống tự động lưu trữ và đóng gói kết quả như sau:

```text
runs/2026-10-03_144611_misteri-dello-spaziotempo_28d/
├── raw/                                # 1. Dữ liệu thô gốc từ YouTube Studio
│   ├── Nội dung 2026-09-04_... .zip    # Tệp zip gốc tải về từ Studio
│   ├── Dữ liệu trong bảng.csv          # Bảng video gốc
│   ├── Dữ liệu biểu đồ.csv             # Dữ liệu timeline theo ngày
│   └── Tổng số.csv                     # Số liệu tổng hợp
├── evidence/                           # 2. Ảnh chụp bằng chứng Full HD (1920x1080)
│   ├── analytics_overview.png          # Ảnh chụp trang Số liệu phân tích tổng quan
│   └── advanced_table.png              # Ảnh chụp bảng Chế độ xem nâng cao đủ cột
├── data/                               # 3. Dữ liệu đã chuẩn hóa sạch (AI-Ready)
│   ├── videos.csv                      # Danh sách video kèm metrics chuẩn hóa
│   ├── videos.jsonl                    # Dạng JSON Lines từng video (dễ nạp vào LLM)
│   ├── traffic_sources.csv             # Phân phối nguồn lưu lượng (Đề xuất, Tìm kiếm...)
│   ├── daily_metrics.csv               # Số liệu theo từng ngày
│   └── channel.json                    # Metadata kênh, ID, kỳ báo cáo, thời gian chạy
├── manifest.json                       # 4. Bảng kê toàn vẹn kèm SHA-256 checksum từng file
├── quality_report.json                 # 5. Đánh giá chất lượng dữ liệu AI (Điểm 100%, 0 lỗi)
└── README.md                           # 6. Báo cáo markdown tóm tắt trực quan cho người dùng
```

---

## 🚀 Hướng dẫn cài đặt & Khởi chạy

### 1. Yêu cầu tiên quyết
* **Hệ điều hành:** Windows 10 hoặc Windows 11 (64-bit).
* **Python:** Phiên bản Python 3.10 trở lên.
* **GPMLogin:** Ứng dụng **GPMLogin Global** đang mở trên máy tính, và **Local API** đang được bật (mặc định cổng `19996` hoặc `9495`).

### 2. Cài đặt môi trường
Mở PowerShell hoặc Command Prompt tại thư mục dự án và thực hiện:

```powershell
# 1. Tạo môi trường ảo Python
python -m venv .venv

# 2. Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# 3. Cài đặt các thư viện cần thiết
pip install -r requirements.txt

# 4. Cài đặt Playwright Browser Drivers (nếu chưa có)
playwright install chromium
```

### 3. Khởi chạy ứng dụng
Bạn có thể khởi chạy bằng một trong các cách sau:
* **Cách 1 (Khuyên dùng - 1 Click):** Nhấp đúp chuột vào file **`CHAY_TOOL.bat`** (hoặc `CHAY_TOOL.vbs`).
* **Cách 2 (Dòng lệnh):**
  ```powershell
  .\.venv\Scripts\python.exe main.py
  ```

---

## 🖥️ Hướng dẫn sử dụng chi tiết

### Bước 1: Mở ứng dụng và kiểm tra kết nối GPM
* Khi ứng dụng mở lên, hệ thống sẽ tự động kết nối tới cổng Local API của GPM.
* Nếu GPM dùng cổng khác (ví dụ `9495`), bạn chỉ cần chuyển sang **Tab 4 (Cài đặt)**, nhập cổng API tương ứng và bấm **[LƯU CẤU HÌNH]**.

### Bước 2: Chọn kênh và thiết lập chiến dịch thu thập (Tab 1)
1. Bấm nút **[LÀM MỚI DANH SÁCH]** để nạp danh sách các profile đang có trên GPM.
2. Lọc profile theo **Nhóm** (GPM Group) hoặc tìm kiếm nhanh theo tên.
3. Tích chọn các profile cần thu thập (có thể bấm *Chọn tất cả*).
4. Thiết lập tham số:
   * **Số luồng song song:** Chọn từ 1 đến 10 luồng (khuyên dùng 2-4 luồng tùy cấu hình máy).
   * **Khoảng thời gian phân tích:** 28 ngày qua (mặc định), 7 ngày, 90 ngày, 365 ngày hoặc Toàn thời gian.
   * **Chế độ lấy video:** Số lượng video gần nhất (5, 10, 20...), Theo khoảng ngày đăng, hoặc Toàn bộ video.

### Bước 3: Bắt đầu thu thập & Giám sát tiến trình
* Bấm nút **[ BẮT ĐẦU THU THẬP ]**.
* Theo dõi thanh tiến trình tổng quát (%) và bảng trạng thái chi tiết của từng luồng (Tên Profile, Tên kênh, Bước thực hiện, Trạng thái, Thời gian chạy).
* Bạn có thể chuyển sang **Tab 3 (Nhật ký)** để xem chi tiết log hoạt động real-time.

### Bước 4: Xem và khai thác kết quả (Tab 2)
* Sau khi hoàn tất, chuyển sang **Tab 2 (Lịch sử & Kết quả)**:
  * Xem danh sách các đợt chạy đã hoàn thành.
  * Bấm nút **Mở thư mục** để truy cập trực tiếp thư mục chứa file dữ liệu.
  * Bấm nút **Xem báo cáo** để đọc ngay bản tóm tắt phân tích hiệu suất kênh.

---

## 🧪 Kiểm thử tự động (Test Suite)

Dự án được bảo vệ bởi bộ kiểm thử tự động toàn diện:

```powershell
# Chạy toàn bộ 74 bài unit tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# Chạy riêng bài kiểm thử toàn trình E2E (Task 5.1 & Task 5.2)
.\.venv\Scripts\python.exe tests/test_e2e_task5_1.py
```

---

## 📄 Bản quyền
Phát triển phục vụ nghiên cứu & phân tích dữ liệu YouTube tự động hóa.
Mọi thắc mắc và đóng góp vui lòng tạo Issue trên GitHub repository.
