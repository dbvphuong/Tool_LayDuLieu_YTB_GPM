"""Kiểm thử tự động cho Task 3.1: Parser đọc file Excel/CSV từ YouTube Studio.

Kiểm tra chi tiết:
1. Nhận diện các cột tiếng Việt chuẩn và biến thể:
   - Lượt xem / Số lượt xem
   - Thời gian xem (giờ)
   - Tỷ lệ nhấp của lượt hiển thị / Tỷ lệ nhấp vào hình thu nhỏ (%)
   - Số lượt hiển thị / Số lượt hiển thị hình thu nhỏ
   - Thời lượng xem trung bình / Thời lượng xem trung bình (giây)
2. Chuẩn hóa ký tự Unicode tiếng Việt (NFC vs NFD combining marks).
3. Đọc dữ liệu số nguyên, số thực, tỷ lệ %, chuỗi thời lượng (HH:MM:SS, MM:SS).
4. Phân tách chính xác dòng Tổng (Total) và danh sách video.
5. Đọc file CSV thực tế từ runs/, file Excel (.xlsx), và file nén .zip.
"""

import io
import shutil
import sys
import tempfile
import unittest
import unicodedata
from pathlib import Path
import pandas as pd

# Thêm src vào sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ytb_gpm_collector.integrations.exports.readers import (
    identify_columns,
    normalize_vietnamese_text,
    parse_numeric,
    parse_integer,
    parse_duration_to_seconds,
    parse_date_string,
    parse_table_dataframe,
    parse_daily_dataframe,
    read_csv_file,
    read_excel_file,
    read_table_file,
    read_daily_metrics_file,
    read_export_zip,
    read_export_bundle,
    COLUMN_ALIASES,
)


class TestTask31ExportReaders(unittest.TestCase):
    """Bộ kiểm thử đơn vị cho module readers (Task 3.1)."""

    def setUp(self):
        self.fixtures_dir = Path(__file__).parent / "fixtures"
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)

    def test_01_vietnamese_unicode_normalization(self):
        """Kiểm tra xử lý chuẩn hóa ký tự Unicode tiếng Việt NFC vs NFD."""
        # 'Thơ\u0300i' dùng dấu huyền tổ hợp (NFD)
        nfd_text = "Thơ\u0300i gian xu\u1ea5t ba\u0309n video"
        # 'Thời' dùng ký tự đúc sẵn (NFC)
        nfc_text = "Thời gian xuất bản video"

        self.assertNotEqual(nfd_text, nfc_text, "Chuỗi NFD và NFC gốc phải khác nhau về byte")
        self.assertEqual(
            normalize_vietnamese_text(nfd_text),
            normalize_vietnamese_text(nfc_text),
            "Sau khi normalize_vietnamese_text, hai chuỗi phải đồng nhất"
        )

    def test_02_identify_required_vietnamese_columns(self):
        """Kiểm tra nhận diện 5 cột tiếng Việt bắt buộc trong Task 3.1 và các cột chính."""
        raw_cols = [
            "Nội dung",
            "Tiêu đề video",
            "Lượt xem",
            "Thời gian xem (giờ)",
            "Tỷ lệ nhấp của lượt hiển thị",
            "Số lượt hiển thị",
            "Thời lượng xem trung bình",
        ]

        mapping, unmapped = identify_columns(raw_cols)

        self.assertEqual(len(unmapped), 0, f"Các cột không nhận diện được: {unmapped}")
        self.assertEqual(mapping.get("Lượt xem"), "views")
        self.assertEqual(mapping.get("Thời gian xem (giờ)"), "watch_time_hours")
        self.assertEqual(mapping.get("Tỷ lệ nhấp của lượt hiển thị"), "ctr_percent")
        self.assertEqual(mapping.get("Số lượt hiển thị"), "impressions")
        self.assertEqual(mapping.get("Thời lượng xem trung bình"), "average_view_duration_seconds")
        self.assertEqual(mapping.get("Nội dung"), "video_id")
        self.assertEqual(mapping.get("Tiêu đề video"), "video_title")

    def test_03_identify_column_variations(self):
        """Kiểm tra nhận diện các biến thể tên cột thực tế từ YouTube Studio."""
        variations = [
            "Số lượt xem",
            "Thời gian xem",
            "Tỷ lệ nhấp vào hình thu nhỏ (%)",
            "Số lượt hiển thị hình thu nhỏ",
            "Thời lượng xem trung bình (giây)",
            "Thơ\u0300i gian xuất bản video",  # NFD
            "Thời lượng",
            "Số người đăng ký",
            "Doanh thu ước tính (USD)",
        ]

        mapping, unmapped = identify_columns(variations)
        self.assertEqual(len(unmapped), 0, f"Các cột chưa khớp: {unmapped}")
        self.assertEqual(mapping["Số lượt xem"], "views")
        self.assertEqual(mapping["Thời gian xem"], "watch_time_hours")
        self.assertEqual(mapping["Tỷ lệ nhấp vào hình thu nhỏ (%)"], "ctr_percent")
        self.assertEqual(mapping["Số lượt hiển thị hình thu nhỏ"], "impressions")
        self.assertEqual(mapping["Thời lượng xem trung bình (giây)"], "average_view_duration_seconds")
        self.assertEqual(mapping["Thơ\u0300i gian xuất bản video"], "publish_date")
        self.assertEqual(mapping["Thời lượng"], "duration_seconds")
        self.assertEqual(mapping["Số người đăng ký"], "subscribers")
        self.assertEqual(mapping["Doanh thu ước tính (USD)"], "estimated_revenue")

    def test_04_parse_numeric_and_integer_values(self):
        """Kiểm tra ép kiểu dữ liệu số, xử lý dấu phẩy, %, khoảng trắng, nan."""
        self.assertEqual(parse_numeric("3,795"), 3795.0)
        self.assertEqual(parse_numeric("2.11%"), 2.11)
        self.assertEqual(parse_numeric("16.5065"), 16.5065)
        self.assertEqual(parse_numeric(406), 406.0)
        self.assertIsNone(parse_numeric("nan"))
        self.assertIsNone(parse_numeric("-"))
        self.assertIsNone(parse_numeric(None))
        self.assertIsNone(parse_numeric(""))

        self.assertEqual(parse_integer("3,795"), 3795)
        self.assertEqual(parse_integer(406.0), 406)
        self.assertEqual(parse_integer("0"), 0)
        self.assertIsNone(parse_integer("nan"))

    def test_05_parse_duration_to_seconds(self):
        """Kiểm tra chuyển đổi thời lượng dạng số và chuỗi HH:MM:SS / MM:SS."""
        # Định dạng giây số nguyên
        self.assertEqual(parse_duration_to_seconds(4380), 4380.0)
        self.assertEqual(parse_duration_to_seconds("4380.0"), 4380.0)
        # Định dạng MM:SS
        self.assertEqual(parse_duration_to_seconds("03:15"), 195.0)
        # Định dạng HH:MM:SS
        self.assertEqual(parse_duration_to_seconds("01:13:00"), 4380.0)
        # Dữ liệu rỗng
        self.assertIsNone(parse_duration_to_seconds(None))
        self.assertIsNone(parse_duration_to_seconds("-"))

    def test_06_parse_date_string(self):
        """Kiểm tra chuẩn hóa ngày tháng sang YYYY-MM-DD."""
        self.assertEqual(parse_date_string("Sep 14, 2026"), "2026-09-14")
        self.assertEqual(parse_date_string("2026-09-04"), "2026-09-04")
        self.assertEqual(parse_date_string("14/09/2026"), "2026-09-14")
        self.assertIsNone(parse_date_string(None))
        self.assertIsNone(parse_date_string("nan"))

    def test_07_parse_table_dataframe_with_summary_row(self):
        """Kiểm tra phân tách dòng Tổng và các dòng video chi tiết."""
        df = pd.DataFrame({
            "Nội dung": ["Tổng", "vid_01", "vid_02"],
            "Tiêu đề video": [None, "Video 1 Tiêu Đề", "Video 2 Tiêu Đề"],
            "Lượt xem": [500, 300, 200],
            "Thời gian xem (giờ)": [25.0, 15.0, 10.0],
            "Số lượt hiển thị": [5000, 3000, 2000],
            "Tỷ lệ nhấp của lượt hiển thị": ["5.0%", "5.5%", "4.5%"],
            "Thời lượng xem trung bình": ["03:00", "03:10", "02:50"],
        })

        parsed = parse_table_dataframe(df, source_file="test_data.csv")

        # Kiểm tra dòng Tổng
        self.assertIsNotNone(parsed.summary_row)
        self.assertEqual(parsed.summary_row.label, "Tổng")
        self.assertEqual(parsed.summary_row.views, 500)
        self.assertEqual(parsed.summary_row.watch_time_hours, 25.0)
        self.assertEqual(parsed.summary_row.impressions, 5000)
        self.assertEqual(parsed.summary_row.ctr_percent, 5.0)
        self.assertEqual(parsed.summary_row.average_view_duration_seconds, 180.0)

        # Kiểm tra danh sách video
        self.assertEqual(len(parsed.video_rows), 2)
        v1 = parsed.video_rows[0]
        self.assertEqual(v1.video_id, "vid_01")
        self.assertEqual(v1.video_title, "Video 1 Tiêu Đề")
        self.assertEqual(v1.views, 300)
        self.assertEqual(v1.watch_time_hours, 15.0)
        self.assertEqual(v1.impressions, 3000)
        self.assertEqual(v1.ctr_percent, 5.5)
        self.assertEqual(v1.average_view_duration_seconds, 190.0)

    def test_08_read_real_csv_files_from_runs(self):
        """Kiểm tra đọc file CSV thực tế được xuất từ YouTube Studio trong runs/."""
        raw_table_csv = Path("runs/2026-10-03_113609_misteri-dello-spaziotempo_28d/raw/Dữ liệu trong bảng.csv")
        if not raw_table_csv.exists():
            self.skipTest("Thư mục runs thực tế không tồn tại để kiểm tra")

        parsed = read_table_file(raw_table_csv)

        # Kiểm tra nhận diện tất cả các cột
        self.assertEqual(len(parsed.unmapped_columns), 0)
        self.assertIsNotNone(parsed.summary_row)
        self.assertEqual(parsed.summary_row.views, 406)
        self.assertEqual(parsed.summary_row.watch_time_hours, 28.143)
        self.assertEqual(parsed.summary_row.subscribers, 2)
        self.assertEqual(parsed.summary_row.impressions, 3795)
        self.assertEqual(parsed.summary_row.ctr_percent, 2.11)

        # Kiểm tra 10 video chi tiết
        self.assertEqual(len(parsed.video_rows), 10)
        first_video = parsed.video_rows[0]
        self.assertEqual(first_video.video_id, "WHiSZd7Ln2E")
        self.assertIn("Pulsar", first_video.video_title)
        self.assertEqual(first_video.publish_date, "2026-09-14")
        self.assertEqual(first_video.duration_seconds, 4380.0)
        self.assertEqual(first_video.views, 238)
        self.assertEqual(first_video.watch_time_hours, 16.5065)
        self.assertEqual(first_video.subscribers, 1)
        self.assertEqual(first_video.impressions, 2115)
        self.assertEqual(first_video.ctr_percent, 1.94)

    def test_09_read_real_zip_export(self):
        """Kiểm tra đọc trực tiếp file .zip xuất từ YouTube Studio."""
        zip_path = Path("runs/2026-10-03_113609_misteri-dello-spaziotempo_28d/raw/Nội dung 2026-09-04_2026-10-02 Misteri dello Spaziotempo.zip")
        if not zip_path.exists():
            self.skipTest("File zip thực tế không tồn tại để kiểm tra")

        bundle = read_export_zip(zip_path)

        self.assertIsNotNone(bundle.table_data)
        self.assertEqual(len(bundle.table_data.video_rows), 10)
        self.assertEqual(len(bundle.daily_chart_data), 140)
        self.assertEqual(len(bundle.daily_totals_data), 28)

    def test_10_read_excel_file(self):
        """Kiểm tra đọc file Excel (.xlsx) với đủ 5 cột tiếng Việt của Task 3.1."""
        df = pd.DataFrame({
            "Nội dung": ["Tổng", "test_video_100"],
            "Tiêu đề video": [None, "Excel Test Video Title"],
            "Lượt xem": [1200, 1200],
            "Thời gian xem (giờ)": [60.0, 60.0],
            "Số lượt hiển thị": [20000, 20000],
            "Tỷ lệ nhấp của lượt hiển thị": ["5.2%", "5.2%"],
            "Thời lượng xem trung bình": ["03:00", "03:00"],
        })
        test_file = self.fixtures_dir / "test_readers_excel.xlsx"
        df.to_excel(test_file, index=False)

        parsed = read_table_file(test_file)
        self.assertEqual(len(parsed.unmapped_columns), 0)
        self.assertEqual(parsed.summary_row.views, 1200)
        self.assertEqual(len(parsed.video_rows), 1)
        self.assertEqual(parsed.video_rows[0].video_id, "test_video_100")
        self.assertEqual(parsed.video_rows[0].average_view_duration_seconds, 180.0)

    def test_11_video_status_evaluation(self):
        """Kiểm tra logic phân loại trạng thái video: ok, zero, not_available, failed (Task 3.2)."""
        from ytb_gpm_collector.integrations.exports.normalize import evaluate_video_status
        from ytb_gpm_collector.domain.models import ParsedVideoRow

        # 1. Bình thường -> ok
        row_ok = ParsedVideoRow(video_id="v_ok", views=100, impressions=1000)
        status, reason = evaluate_video_status(row_ok)
        self.assertEqual(status, "ok")
        self.assertIsNone(reason)

        # 2. Không có lượt xem và không có hiển thị -> zero
        row_zero = ParsedVideoRow(video_id="v_zero", views=0, impressions=0)
        status, reason = evaluate_video_status(row_zero)
        self.assertEqual(status, "zero")
        self.assertEqual(reason, "zero_views_and_impressions")

        # 3. Thiếu video_id -> failed
        row_failed = ParsedVideoRow(video_id="unknown_row_5", views=10)
        status, reason = evaluate_video_status(row_failed)
        self.assertEqual(status, "failed")
        self.assertEqual(reason, "missing_or_invalid_video_id")

        # 4. Không có dữ liệu số liệu từ YouTube -> not_available
        row_na = ParsedVideoRow(video_id="v_na", views=None, impressions=None, watch_time_hours=None)
        status, reason = evaluate_video_status(row_na)
        self.assertEqual(status, "not_available")
        self.assertEqual(reason, "metrics_not_reported_by_youtube")

    def test_12_extract_period_dates(self):
        """Kiểm tra trích xuất khoảng thời gian từ tên file và dữ liệu ngày (Task 3.2)."""
        from ytb_gpm_collector.integrations.exports.normalize import extract_period_dates
        from ytb_gpm_collector.domain.models import StudioRawBundle, ParsedDailyMetricRow

        # Trích xuất từ tên file nén
        bundle_file = StudioRawBundle(
            source_path="raw/Nội dung 2026-09-04_2026-10-02 Misteri.zip",
            discovered_files=["Nội dung 2026-09-04_2026-10-02 Misteri.zip"]
        )
        s, e, k = extract_period_dates(bundle_file)
        self.assertEqual(s, "2026-09-04")
        self.assertEqual(e, "2026-10-02")
        self.assertEqual(k, "fixed_calendar_range")

        # Trích xuất từ min/max dữ liệu theo ngày
        bundle_daily = StudioRawBundle(
            source_path="raw/custom",
            daily_totals_data=[
                ParsedDailyMetricRow(date="2026-08-01", views=10),
                ParsedDailyMetricRow(date="2026-08-28", views=50),
            ]
        )
        s2, e2, k2 = extract_period_dates(bundle_daily)
        self.assertEqual(s2, "2026-08-01")
        self.assertEqual(e2, "2026-08-28")

    def test_13_normalize_null_preservation(self):
        """Kiểm tra quy tắc không suy diễn số: giá trị trống giữ nguyên null (Task 3.2)."""
        from ytb_gpm_collector.integrations.exports.normalize import normalize_video_records
        from ytb_gpm_collector.domain.models import ParsedTableData, ParsedVideoRow
        import json

        table = ParsedTableData(
            source_file="table.csv",
            video_rows=[
                ParsedVideoRow(
                    video_id="v_null_test",
                    video_title="Null Test Video",
                    views=100,
                    watch_time_hours=5.0,
                    average_view_duration_seconds=None,  # YouTube không xuất
                    impressions=None,
                    ctr_percent=None,
                )
            ]
        )

        records = normalize_video_records(
            table_data=table,
            channel_id="UC_TEST",
            period_start="2026-09-01",
            period_end="2026-09-28",
        )

        self.assertEqual(len(records), 1)
        rec = records[0]
        # Không được tự ý bịa hay suy diễn số thành 0 khi YouTube không cung cấp
        self.assertIsNone(rec.average_view_duration_seconds)
        self.assertIsNone(rec.impressions)
        self.assertIsNone(rec.ctr_percent)

        # Kiểm tra khi dump ra dict / JSON phải ra null
        rec_json = json.loads(rec.model_dump_json())
        self.assertIsNone(rec_json["average_view_duration_seconds"])
        self.assertIsNone(rec_json["impressions"])
        self.assertEqual(rec_json["views"], 100)

    def test_14_clean_files_generation(self):
        """Kiểm tra sinh các file sạch videos.csv, videos.jsonl, traffic_sources.csv trong data/ (Task 3.2)."""
        from ytb_gpm_collector.integrations.exports.normalize import (
            write_videos_csv,
            write_videos_jsonl,
            write_traffic_sources_csv,
            write_daily_metrics_csv,
            write_channel_json,
        )
        from ytb_gpm_collector.domain.models import (
            NormalizedVideoRecord,
            NormalizedChannelOverview,
            ParsedDailyMetricRow,
        )
        import json

        test_data_dir = self.fixtures_dir / "test_out_data"
        test_data_dir.mkdir(parents=True, exist_ok=True)

        rec = NormalizedVideoRecord(
            channel_id="UC_DEMO",
            video_id="vid_demo",
            video_title="Video Demo Tiếng Việt Có Dấu",
            period_start="2026-09-01",
            period_end="2026-09-28",
            views=500,
            watch_time_hours=20.5,
            average_view_duration_seconds=None,
            source_file="raw/test.csv",
        )

        # 1. Ghi CSV
        csv_file = test_data_dir / "videos.csv"
        write_videos_csv([rec], csv_file)
        self.assertTrue(csv_file.exists())
        # Đọc lại và kiểm tra BOM
        content_bytes = csv_file.read_bytes()
        self.assertTrue(content_bytes.startswith(b"\xef\xbb\xbf"), "videos.csv phải có UTF-8 BOM cho Excel")
        df_read = pd.read_csv(csv_file)
        self.assertEqual(len(df_read), 1)
        self.assertEqual(df_read.iloc[0]["video_id"], "vid_demo")
        self.assertTrue(pd.isna(df_read.iloc[0]["average_view_duration_seconds"]))

        # 2. Ghi JSONL
        jsonl_file = test_data_dir / "videos.jsonl"
        write_videos_jsonl([rec], jsonl_file)
        self.assertTrue(jsonl_file.exists())
        lines = jsonl_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(obj["video_id"], "vid_demo")
        self.assertIsNone(obj["average_view_duration_seconds"])

        # 3. Ghi traffic_sources.csv
        traffic_file = test_data_dir / "traffic_sources.csv"
        write_traffic_sources_csv([], traffic_file)
        self.assertTrue(traffic_file.exists())

        # 4. Ghi channel.json
        ch_file = test_data_dir / "channel.json"
        overview = NormalizedChannelOverview(
            channel_id="UC_DEMO",
            period_start="2026-09-01",
            period_end="2026-09-28",
            source_file="raw/test.csv",
            normalized_at="2026-10-03T12:00:00",
        )
        write_channel_json(overview, ch_file)
        self.assertTrue(ch_file.exists())

    def test_15_normalize_run_directory_e2e(self):
        """Kiểm tra quy trình chuẩn hóa trọn vẹn toàn bộ một run directory (Task 3.2)."""
        from ytb_gpm_collector.integrations.exports.normalize import normalize_run_directory

        real_run = Path("runs/2026-10-03_113609_misteri-dello-spaziotempo_28d")
        if not real_run.exists():
            self.skipTest("Thư mục runs thực tế không tồn tại để kiểm tra")

        with tempfile.TemporaryDirectory() as temporary:
            copied_run = Path(temporary) / real_run.name
            shutil.copytree(real_run, copied_run)
            res = normalize_run_directory(copied_run)

            self.assertTrue(res.success)
            self.assertEqual(res.videos_count, 10)
            self.assertEqual(res.channel_id, "UCFrluilrmcfap2ZWvuTeA0A")
            self.assertEqual(res.period_start, "2026-09-04")
            self.assertEqual(res.period_end, "2026-10-01")

            data_dir = copied_run / "data"
            self.assertTrue((data_dir / "videos.csv").exists())
            self.assertTrue((data_dir / "videos.jsonl").exists())
            self.assertTrue((data_dir / "traffic_sources.csv").exists())
            self.assertTrue((data_dir / "daily_metrics.csv").exists())
            self.assertTrue((data_dir / "daily_channel_metrics.csv").exists())
            self.assertTrue((data_dir / "channel.json").exists())


if __name__ == "__main__":
    unittest.main()

