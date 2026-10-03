"""Kiểm thử tự động cho Task 3.3: Module Báo cáo & Kiểm định chất lượng (storage/runs.py).

Kiểm tra chi tiết:
1. Tính toán mã băm SHA-256 (compute_file_sha256) và các hàm định dạng hiển thị.
2. Sinh báo cáo chất lượng dữ liệu (quality_report.json):
   - Kiểm tra phát hiện lỗi (missing video_id, negative views, invalid CTR > 100%).
   - Kiểm tra cảnh báo (missing CTR khi có lượt hiển thị, AVD vượt thời lượng).
   - Đối chiếu số liệu dòng Tổng kênh vs tổng video chi tiết (reconciliation).
   - Tính điểm hoàn thiện dữ liệu (completeness_score_percent).
   - Kiểm tra toàn vẹn file thô (raw/) và bằng chứng (evidence/).
3. Sinh bản kê gói dữ liệu (manifest.json):
   - Kiểm tra schema_version, thông tin kênh, đợt chạy.
   - Quét toàn bộ tệp tin, tính dung lượng và mã SHA-256.
   - Tóm tắt số lượng video, daily metrics, raw, evidence.
4. Sinh báo cáo trực quan cho người dùng (README.md):
   - Bảng tổng quan kênh (Views, Watch time, Impressions, CTR, Subscribers).
   - Bảng "Đã lấy / Thiếu / Cần đăng nhập lại" theo quy chuẩn kiến trúc.
   - Bảng Top video có liên kết YouTube (https://youtu.be/...).
   - Bảng đánh giá chất lượng và danh mục tệp tin liên kết tương đối.
5. Quy trình trọn vẹn (End-to-End) với RunDirectory và thư mục runs thực tế.
"""

import json
import shutil
import sys
import unittest
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ytb_gpm_collector.domain.models import (
    NormalizedVideoRecord,
    NormalizedChannelOverview,
    QualityReport,
    RunManifest,
)
from ytb_gpm_collector.integrations.storage.runs import (
    slugify,
    compute_file_sha256,
    format_seconds_to_display,
    format_number,
    load_normalized_videos_from_dir,
    load_channel_overview_from_dir,
    generate_quality_report,
    generate_manifest,
    generate_readme,
    RunDirectory,
    build_run_reports,
)


class TestTask33Reporting(unittest.TestCase):
    """Bộ kiểm thử cho module Báo cáo & Kiểm định chất lượng (Task 3.3)."""

    def setUp(self):
        # Tạo thư mục tạm thời để test độc lập
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_ytb_task33_"))
        self.run_dir = self.test_dir / "2026-10-03_test-channel_28d"
        self.run_storage = RunDirectory(run_id=self.run_dir.name, base_dir=self.test_dir)
        self.run_storage.init_folders()

    def tearDown(self):
        # Xóa thư mục tạm sau khi test
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. KIỂM THỬ CÁC HÀM TIỆN ÍCH ĐỊNH DẠNG & BĂM SHA-256
    # =========================================================================

    def test_01_slugify_and_sha256(self):
        """Kiểm tra hàm slugify và tính toán mã băm SHA-256."""
        # Test slugify
        self.assertEqual(slugify("Kênh Thí Nghiệm & Khoa Học"), "kenh-thi-nghiem-khoa-hoc")
        self.assertEqual(slugify(""), "channel")

        # Test compute_file_sha256
        test_file = self.run_dir / "sample.txt"
        test_file.write_text("Hello YouTube Studio Collector", encoding="utf-8")
        sha = compute_file_sha256(test_file)
        self.assertEqual(len(sha), 64, "SHA-256 hex string phải có độ dài 64 ký tự")

        # Kiểm tra file không tồn tại
        self.assertEqual(compute_file_sha256(self.run_dir / "non_existent.txt"), "")

    def test_02_format_helpers(self):
        """Kiểm tra các hàm định dạng hiển thị thời gian và số."""
        # format_seconds_to_display
        self.assertEqual(format_seconds_to_display(None), "-")
        self.assertEqual(format_seconds_to_display(45), "00:45")
        self.assertEqual(format_seconds_to_display(154), "02:34")
        self.assertEqual(format_seconds_to_display(3665), "01:01:05")

        # format_number
        self.assertEqual(format_number(None), "-")
        self.assertEqual(format_number(1234), "1,234")
        self.assertEqual(format_number(1234567.89, decimal_places=2), "1,234,567.89")
        self.assertEqual(format_number(28.143, decimal_places=1), "28.1")

    # =========================================================================
    # 2. KIỂM THỬ SINH BÁO CÁO CHẤT LƯỢNG (QUALITY REPORT)
    # =========================================================================

    def _create_mock_run_data(self, inject_issues: bool = False):
        """Tạo dữ liệu giả lập chuẩn trong run_dir để kiểm thử."""
        # 1. raw/
        raw_zip = self.run_storage.raw_dir / "raw_export.zip"
        raw_zip.write_bytes(b"MOCK_ZIP_DATA_BYTES")

        # 2. evidence/
        img = self.run_storage.evidence_dir / "analytics_overview.png"
        img.write_bytes(b"MOCK_IMAGE_PNG")

        # 3. data/channel.json
        ch_overview = NormalizedChannelOverview(
            channel_id="UC_TEST_123",
            channel_name="Kênh Thử Nghiệm",
            period_start="2026-09-01",
            period_end="2026-09-28",
            period_kind="fixed_calendar_range",
            total_views=1000 if not inject_issues else 800,
            total_watch_time_hours=50.0,
            total_impressions=10000,
            average_ctr_percent=5.0,
            total_subscribers=10,
            video_count=2,
            source_file="raw/raw_export.zip",
            normalized_at="2026-10-03T12:00:00",
        )
        (self.run_storage.data_dir / "channel.json").write_text(
            ch_overview.model_dump_json(indent=2), encoding="utf-8"
        )

        # 4. data/videos.jsonl
        videos = [
            NormalizedVideoRecord(
                channel_id="UC_TEST_123",
                video_id="vid_valid_01",
                video_title="Video Chuẩn Số 1",
                period_start="2026-09-01",
                period_end="2026-09-28",
                views=600,
                watch_time_hours=30.0,
                duration_seconds=600.0,
                average_view_duration_seconds=180.0,
                impressions=6000,
                ctr_percent=5.2,
                subscribers=6,
                status="ok",
                source_file="raw/raw_export.zip",
            ),
            NormalizedVideoRecord(
                channel_id="UC_TEST_123",
                video_id="vid_valid_02",
                video_title="Video Chuẩn Số 2",
                period_start="2026-09-01",
                period_end="2026-09-28",
                views=400,
                watch_time_hours=20.0,
                duration_seconds=1200.0,
                average_view_duration_seconds=300.0,
                impressions=4000,
                ctr_percent=4.8,
                subscribers=4,
                status="ok",
                source_file="raw/raw_export.zip",
            ),
        ]

        if inject_issues:
            # Thêm video có lỗi
            videos.append(
                NormalizedVideoRecord(
                    channel_id="UC_TEST_123",
                    video_id="unknown_row_99",  # Lỗi ID
                    video_title=None,           # Thiếu tiêu đề
                    period_start="2026-09-01",
                    period_end="2026-09-28",
                    views=-10,                  # Lượt xem âm
                    watch_time_hours=5.0,
                    duration_seconds=100.0,
                    average_view_duration_seconds=500.0, # AVD vượt quá thời lượng
                    impressions=1000,
                    ctr_percent=150.0,          # CTR > 100%
                    status="failed",
                    source_file="raw/raw_export.zip",
                )
            )

        with open(self.run_storage.data_dir / "videos.jsonl", "w", encoding="utf-8") as f:
            for v in videos:
                f.write(v.model_dump_json() + "\n")

        # 5. data/daily_metrics.csv
        daily_csv = self.run_storage.data_dir / "daily_metrics.csv"
        daily_csv.write_text("date,video_id,views,watch_time_hours\n2026-09-28,vid_valid_01,600,30.0\n2026-09-28,vid_valid_02,400,20.0\n", encoding="utf-8")

        # 6. data/traffic_sources.csv
        traffic_csv = self.run_storage.data_dir / "traffic_sources.csv"
        traffic_csv.write_text("video_id,traffic_source,views\n,YouTube Search,1000\nvid_valid_01,Suggested,600\nvid_valid_02,Suggested,400\n", encoding="utf-8")

    def test_03_quality_report_perfect_data(self):
        """Kiểm tra báo cáo chất lượng khi dữ liệu hoàn hảo (100% khớp, status passed)."""
        self._create_mock_run_data(inject_issues=False)

        report = generate_quality_report(self.run_dir)
        self.assertIsInstance(report, QualityReport)
        self.assertEqual(report.status, "passed")
        self.assertEqual(report.summary.total_videos_checked, 2)
        self.assertEqual(report.summary.valid_videos_count, 2)
        self.assertEqual(report.summary.total_errors, 0)
        self.assertEqual(report.summary.total_warnings, 0)
        self.assertEqual(report.summary.completeness_score_percent, 100.0)

        # Kiểm tra đối chiếu (Reconciliation): 600 + 400 = 1000 views
        self.assertTrue(report.checks.summary_reconciliation.reconciled)
        self.assertEqual(report.checks.summary_reconciliation.total_video_views, 1000)
        self.assertEqual(report.checks.summary_reconciliation.channel_summary_views, 1000)
        self.assertEqual(report.checks.summary_reconciliation.views_difference, 0)
        self.assertTrue(report.checks.raw_files_intact)
        self.assertTrue(report.checks.evidence_images_present)

    def test_04_quality_report_with_issues(self):
        """Kiểm tra báo cáo chất lượng phát hiện đúng các cảnh báo và lỗi."""
        self._create_mock_run_data(inject_issues=True)

        report = generate_quality_report(self.run_dir)
        self.assertEqual(report.status, "failed")
        self.assertGreater(report.summary.total_errors, 0)
        self.assertGreater(report.summary.total_warnings, 0)
        self.assertEqual(report.summary.failed_videos_count, 1)

        # Kiểm tra các mã lỗi được phát hiện
        issue_codes = [iss.code for iss in report.issues]
        self.assertIn("MISSING_VIDEO_ID", issue_codes)
        self.assertIn("NEGATIVE_VIEWS", issue_codes)
        self.assertIn("INVALID_CTR", issue_codes)
        self.assertIn("AVD_EXCEEDS_DURATION", issue_codes)
        self.assertIn("VIEW_RECONCILIATION_MISMATCH", issue_codes)

        # Kiểm tra suggestions
        self.assertGreater(len(report.suggestions), 0)

    # =========================================================================
    # 3. KIỂM THỬ SINH BẢN KÊ GÓI DỮ LIỆU (MANIFEST)
    # =========================================================================

    def test_05_manifest_generation(self):
        """Kiểm tra sinh manifest.json đầy đủ thông tin metadata và SHA-256."""
        self._create_mock_run_data(inject_issues=False)
        q_report = generate_quality_report(self.run_dir)

        manifest = generate_manifest(self.run_dir, quality_report=q_report)
        self.assertIsInstance(manifest, RunManifest)
        self.assertEqual(manifest.schema_version, "1.0")
        self.assertEqual(manifest.channel_id, "UC_TEST_123")
        self.assertEqual(manifest.channel_name, "Kênh Thử Nghiệm")
        self.assertEqual(manifest.period_start, "2026-09-01")
        self.assertEqual(manifest.period_end, "2026-09-28")
        self.assertEqual(manifest.status, "success")

        # Kiểm tra danh mục tệp tin và mã băm SHA-256
        self.assertGreater(len(manifest.files), 0)
        file_paths = [f.path for f in manifest.files]
        self.assertIn("data/videos.jsonl", file_paths)
        self.assertIn("data/channel.json", file_paths)
        self.assertIn("data/daily_metrics.csv", file_paths)
        self.assertIn("raw/raw_export.zip", file_paths)
        self.assertIn("evidence/analytics_overview.png", file_paths)

        # Đảm bảo mỗi file đều có sha256 hợp lệ
        for f_info in manifest.files:
            self.assertEqual(len(f_info.sha256), 64, f"File {f_info.path} phải có mã SHA-256")
            self.assertGreater(f_info.size_bytes, 0)

        # Kiểm tra summary đếm số lượng
        self.assertEqual(manifest.summary["video_count"], 2)
        self.assertEqual(manifest.summary["daily_metrics_count"], 2)
        self.assertEqual(manifest.summary["traffic_sources_count"], 3)
        self.assertEqual(manifest.summary["raw_files_count"], 1)
        self.assertEqual(manifest.summary["evidence_files_count"], 1)

    # =========================================================================
    # 4. KIỂM THỬ SINH BÁO CÁO README.md CHO NGƯỜI DÙNG
    # =========================================================================

    def test_06_readme_generation(self):
        """Kiểm tra sinh README.md với đầy đủ bảng biểu và liên kết tương đối."""
        self._create_mock_run_data(inject_issues=False)
        q_report = generate_quality_report(self.run_dir)
        manifest = generate_manifest(self.run_dir, quality_report=q_report)

        readme_text = generate_readme(
            run_dir=self.run_dir,
            manifest=manifest,
            quality_report=q_report,
        )

        self.assertIsInstance(readme_text, str)
        # 1. Kiểm tra tiêu đề và nhận diện kênh
        self.assertIn("# 📊 Báo Cáo Thu Thập Dữ Liệu YouTube Studio", readme_text)
        self.assertIn("Kênh Thử Nghiệm", readme_text)
        self.assertIn("UC_TEST_123", readme_text)
        self.assertIn("2026-09-01", readme_text)
        self.assertIn("2026-09-28", readme_text)

        # 2. Bảng chỉ số tổng quan kênh
        self.assertIn("1,000", readme_text)  # views
        self.assertIn("50.0", readme_text)   # watch time
        self.assertIn("5.00%", readme_text)  # ctr

        # 3. Bảng "Đã Lấy / Thiếu / Cần Đăng Nhập Lại"
        self.assertIn("Đã Lấy / Thiếu / Cần Đăng Nhập Lại", readme_text)
        self.assertIn("Bảng chi tiết video", readme_text)
        self.assertIn("Số liệu theo ngày", readme_text)
        self.assertIn("Nguồn lưu lượng", readme_text)
        self.assertIn("Trạng thái đăng nhập Studio", readme_text)
        self.assertIn("chốt đến hết ngày **`2026-09-28`**", readme_text)

        # 4. Top Video có link YouTube
        self.assertIn("Top Video Xem Nhiều Nhất", readme_text)
        self.assertIn("Video Chuẩn Số 1", readme_text)
        self.assertIn("600", readme_text)

        # 5. Danh mục tệp tin và liên kết tương đối
        self.assertIn("[`data/videos.csv`](data/videos.csv)", readme_text)
        self.assertIn("[`data/videos.jsonl`](data/videos.jsonl)", readme_text)
        self.assertIn("[`data/channel.json`](data/channel.json)", readme_text)
        self.assertIn("[`quality_report.json`](quality_report.json)", readme_text)
        self.assertIn("[`manifest.json`](manifest.json)", readme_text)

    # =========================================================================
    # 5. KIỂM THỬ TRỌN VẸN RUNDIRECTORY.BUILD_ALL_REPORTS
    # =========================================================================

    def test_07_build_all_reports_e2e(self):
        """Kiểm tra quy trình RunDirectory.build_all_reports sinh đủ 3 file."""
        self._create_mock_run_data(inject_issues=False)

        report_files = self.run_storage.build_all_reports()

        self.assertIn("quality_report", report_files)
        self.assertIn("manifest", report_files)
        self.assertIn("readme", report_files)

        self.assertTrue((self.run_dir / "quality_report.json").exists())
        self.assertTrue((self.run_dir / "manifest.json").exists())
        self.assertTrue((self.run_dir / "README.md").exists())

        # Đọc lại manifest.json để đảm bảo có cấu trúc chuẩn
        with open(self.run_dir / "manifest.json", "r", encoding="utf-8") as f:
            manifest_json = json.load(f)
            self.assertEqual(manifest_json["status"], "success")
            self.assertIn("quality_summary", manifest_json)
            self.assertEqual(manifest_json["quality_summary"]["completeness_score_percent"], 100.0)

    # =========================================================================
    # 6. KIỂM THỬ TRÊN THƯ MỤC RUN THỰC TẾ
    # =========================================================================

    def test_08_real_run_build_reports(self):
        """Kiểm tra sinh báo cáo trên dữ liệu thực tế từ Task 2.3 và Task 3.2."""
        real_run = Path("runs/2026-10-03_113609_misteri-dello-spaziotempo_28d")
        if not real_run.exists():
            self.skipTest("Thư mục runs thực tế không tồn tại để kiểm tra")

        # Gọi hàm build_run_reports
        reports = build_run_reports(real_run)

        # Kiểm tra 3 file sinh ra
        q_path = real_run / "quality_report.json"
        m_path = real_run / "manifest.json"
        r_path = real_run / "README.md"

        self.assertTrue(q_path.exists())
        self.assertTrue(m_path.exists())
        self.assertTrue(r_path.exists())

        # Đọc và kiểm tra nội dung quality_report.json thực tế
        with open(q_path, "r", encoding="utf-8") as f:
            q_data = json.load(f)
            self.assertEqual(q_data["channel_id"], "UCFrluilrmcfap2ZWvuTeA0A")
            self.assertEqual(q_data["summary"]["total_videos_checked"], 10)
            self.assertEqual(q_data["summary"]["valid_videos_count"], 10)
            # Đối chiếu 100% khớp 406 views!
            self.assertTrue(q_data["checks"]["summary_reconciliation"]["reconciled"])
            self.assertEqual(q_data["checks"]["summary_reconciliation"]["total_video_views"], 406)
            self.assertEqual(q_data["checks"]["summary_reconciliation"]["channel_summary_views"], 406)

        # Đọc và kiểm tra README.md
        readme_content = r_path.read_text(encoding="utf-8")
        self.assertIn("Misteri dello Spaziotempo", readme_content)
        self.assertIn("UCFrluilrmcfap2ZWvuTeA0A", readme_content)
        self.assertIn("406", readme_content)
        self.assertIn("28.1", readme_content)
        self.assertIn("WHiSZd7Ln2E", readme_content)
        self.assertIn("https://youtu.be/WHiSZd7Ln2E", readme_content)
        self.assertIn("chốt đến hết ngày **`2026-10-02`**", readme_content)


if __name__ == "__main__":
    unittest.main()
