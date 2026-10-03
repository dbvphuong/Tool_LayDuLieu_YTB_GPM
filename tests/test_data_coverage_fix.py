"""Checks for the reports that the main Studio video export does not contain."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ytb_gpm_collector.integrations.exports.normalize import normalize_run_directory


class DataCoverageTests(unittest.TestCase):
    def test_normalize_combines_video_daily_channel_daily_and_traffic(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            raw = run / "raw"
            raw.mkdir(parents=True)
            (run / "manifest.json").write_text(json.dumps({
                "run_id": "run", "channel_id": "UC_TEST", "channel_name": "Test",
                "period": "28_days", "collection_depth": "standard",
            }), encoding="utf-8")
            (raw / "Dữ liệu trong bảng.csv").write_text(
                "Nội dung,Tiêu đề video,Số lượt xem,Thời gian xem (giờ),Số lượt hiển thị hình thu nhỏ,Tỷ lệ nhấp vào hình thu nhỏ (%)\n"
                "Tổng,,30,3,300,10\nvideo_one,One,10,1,100,10\nvideo_two,Two,20,2,200,10\n",
                encoding="utf-8-sig",
            )
            (raw / "Dữ liệu biểu đồ.csv").write_text(
                "Ngày,Nội dung,Tiêu đề video,Số lượt xem\n2026-09-01,video_one,One,10\n",
                encoding="utf-8-sig",
            )
            (raw / "Tổng số.csv").write_text(
                "Ngày,Số lượt xem\n2026-09-01,30\n", encoding="utf-8-sig",
            )
            video_dir = raw / "video_daily" / "video_two"
            video_dir.mkdir(parents=True)
            (video_dir / "Tổng số.csv").write_text(
                "Ngày,Số lượt xem\n2026-09-01,20\n", encoding="utf-8-sig",
            )
            traffic_dir = raw / "traffic_sources"
            traffic_dir.mkdir()
            (traffic_dir / "Dữ liệu trong bảng.csv").write_text(
                "Nguồn lưu lượng truy cập,Số lượt xem\nTổng,30\nVideo đề xuất,20\nTìm kiếm trên YouTube,10\n",
                encoding="utf-8-sig",
            )
            for video_id, views in (("video_one", 10), ("video_two", 20)):
                folder = raw / "video_traffic" / video_id
                folder.mkdir(parents=True)
                (folder / "Dữ liệu trong bảng.csv").write_text(
                    f"Nguồn lưu lượng truy cập,Số lượt xem\nTổng,{views}\nVideo đề xuất,{views}\n",
                    encoding="utf-8-sig",
                )

            result = normalize_run_directory(run)
            with (run / "data" / "daily_metrics.csv").open(encoding="utf-8-sig", newline="") as stream:
                daily = list(csv.DictReader(stream))
            with (run / "data" / "daily_channel_metrics.csv").open(encoding="utf-8-sig", newline="") as stream:
                channel_daily = list(csv.DictReader(stream))
            with (run / "data" / "traffic_sources.csv").open(encoding="utf-8-sig", newline="") as stream:
                traffic = list(csv.DictReader(stream))
            quality = json.loads((run / "quality_report.json").read_text(encoding="utf-8"))

            self.assertEqual(result.daily_metrics_count, 2)
            self.assertEqual({row["video_id"] for row in daily}, {"video_one", "video_two"})
            self.assertEqual(len(channel_daily), 1)
            self.assertEqual([row["views"] for row in traffic], ["20", "10", "10", "20"])
            self.assertEqual(quality["coverage"]["video_daily_count"], 2)
            self.assertEqual(quality["coverage"]["traffic_sources_count"], 4)
            self.assertEqual(quality["coverage"]["video_traffic_count"], 2)


if __name__ == "__main__":
    unittest.main()
