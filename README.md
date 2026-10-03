# Tool Lấy Dữ Liệu YouTube Studio Qua GPM-Login

Hệ thống desktop automation thu thập dữ liệu phân tích từ **YouTube Studio** thông qua trình duyệt antidetect **GPMLogin Global**, phục vụ nghiên cứu và phân tích kênh YouTube bằng AI và con người.

---

## 🌟 Tính năng nổi bật

* **Bảo toàn 100% môi trường GPM:** Tự động gọi API của GPMLogin để mở profile, kết nối điều khiển qua giao thức Chrome DevTools Protocol (CDP), giữ nguyên tuyệt đối trình duyệt Chromium tùy biến và **Proxy đã gán cho từng profile**.
* **Hỗ trợ Multi-Kênh & Chạy Đa Luồng (Concurrency Pool):** Cho phép tích chọn nhiều kênh cùng lúc, cấu hình số luồng chạy song song tối đa (1 - 10 luồng), tự động luân phiên hàng đợi giúp tối ưu thời gian mà không gây nghẽn RAM máy.
* **Linh hoạt chọn video:** 
  * Lấy theo **số lượng video gần nhất** (ví dụ: 5, 10, 20 video mới xuất bản gần đây nhất).
  * Lấy theo **khoảng thời gian đăng video** (7 ngày, 28 ngày, 90 ngày...).
  * Lấy toàn bộ video trên kênh.
* **Hỗ trợ YouTube Studio tiếng Việt:** Nhận diện chuẩn xác toàn bộ nhãn, bộ lọc ngày và xuất báo cáo từ giao diện tiếng Việt Nam.
* **Dữ liệu 2 lớp chuẩn hóa:** Lưu trọn vẹn file thô gốc (`raw/` XLSX/CSV) và tự động chuẩn hóa sang định dạng sạch (`data/` CSV và JSONL), kèm ảnh đối chiếu (`evidence/`) và file báo cáo tổng hợp `README.md`.
* **Giao diện 1 cửa sổ hiện đại (PySide6):** Tông màu **Xanh dương dịu mắt (Soft Slate & Blue)**, bố cục Sidebar thanh điều hướng bên trái và khung nội dung bên phải, tích hợp màn hình xem Log thời gian thực.

---

## 📚 Tài liệu chi tiết dự án (Thư mục `docs/`)

Toàn bộ tài liệu phân tích, đặc tả và kế hoạch được tổ chức gọn gàng trong thư mục [`docs/`](docs/):

1. **[YEU_CAU_VA_DAC_TA_KY_THUAT.md](docs/YEU_CAU_VA_DAC_TA_KY_THUAT.md):** Bản đặc tả yêu cầu chi tiết, môi trường GPM, cơ chế giữ proxy, đa luồng và quy tắc nghiệm thu.
2. **[KIEN_TRUC_TOOL_LAY_DU_LIEU_YTB_GPM.md](docs/KIEN_TRUC_TOOL_LAY_DU_LIEU_YTB_GPM.md):** Thiết kế kiến trúc phần mềm Clean Architecture, luồng dữ liệu và mô hình tổ chức source code.
3. **[THIET_KE_GIAO_DIEN.md](docs/THIET_KE_GIAO_DIEN.md):** Bản vẽ phác thảo bố cục (Wireframe ASCII), bảng mã màu Soft Blue, chi tiết các màn hình và cây widget PySide6.
4. **[PLAN_TRIEN_KHAI.md](docs/PLAN_TRIEN_KHAI.md):** Kế hoạch triển khai theo từng giai đoạn (Milestones) kèm checklist từng Task cụ thể.

---

## 📂 Cấu trúc thư mục

```text
Tool_LayDuLieu_YTB_GPM/
├── docs/                               # Toàn bộ tài liệu thiết kế và đặc tả kỹ thuật
│   ├── KIEN_TRUC_TOOL_LAY_DU_LIEU_YTB_GPM.md
│   ├── YEU_CAU_VA_DAC_TA_KY_THUAT.md
│   ├── THIET_KE_GIAO_DIEN.md
│   └── PLAN_TRIEN_KHAI.md
├── src/                                # Mã nguồn chính của ứng dụng
│   └── ytb_gpm_collector/
├── tests/                              # Bộ kiểm thử tự động
├── runs/                               # Dữ liệu xuất ra sau mỗi lần chạy (raw, data, evidence)
├── config.example.json                 # Cấu hình mẫu ban đầu
├── requirements.txt                    # Danh sách thư viện Python
├── .gitignore                          # Cấu hình bỏ qua file rác / dữ liệu cào
└── README.md                           # Giới thiệu tổng quan dự án
```

---

## 🚀 Hướng dẫn cài đặt nhanh

```bash
# 1. Tạo môi trường ảo
python -m venv .venv

# 2. Kích hoạt môi trường ảo (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 3. Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```
