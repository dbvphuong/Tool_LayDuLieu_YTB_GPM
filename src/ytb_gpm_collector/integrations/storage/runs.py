"""Quản lý thư mục lưu trữ cho từng đợt chạy (runs/<run_id>/).

Cấu trúc mỗi lần chạy:
runs/<run_id>/
├── README.md
├── manifest.json
├── quality_report.json
├── data/
├── raw/
└── evidence/
"""

import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Chuyển đổi chuỗi tiếng Việt/ký tự đặc biệt thành slug an toàn cho thư mục."""
    if not text:
        return "channel"
    # Thay thế các ký tự tiếng Việt có dấu
    text = text.lower().strip()
    replacements = {
        "à": "a", "á": "a", "ả": "a", "ã": "a", "ạ": "a",
        "ă": "a", "ằ": "a", "ắ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a",
        "â": "a", "ầ": "a", "ấ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
        "đ": "d",
        "è": "e", "é": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e",
        "ê": "e", "ề": "e", "ế": "e", "ể": "e", "ễ": "e", "ệ": "e",
        "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
        "ò": "o", "ó": "o", "ỏ": "o", "õ": "o", "ọ": "o",
        "ô": "o", "ồ": "o", "ố": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
        "ơ": "o", "ờ": "o", "ớ": "o", "ở": "o", "ỡ": "o", "ợ": "o",
        "ù": "u", "ú": "u", "ủ": "u", "ũ": "u", "ụ": "u",
        "ư": "u", "ừ": "u", "ứ": "u", "ử": "u", "ữ": "u", "ự": "u",
        "ỳ": "y", "ý": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"[^a-z0-9\s_-]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:40] or "channel"


class RunDirectory:
    """Đại diện cho thư mục một đợt thu thập dữ liệu."""

    def __init__(
        self,
        run_id: str,
        base_dir: Optional[Path] = None,
    ):
        self.run_id = run_id
        self.base_dir = Path(base_dir or "runs").resolve()
        self.run_dir = self.base_dir / run_id

        # Các thư mục con theo thiết kế kiến trúc
        self.raw_dir = self.run_dir / "raw"
        self.evidence_dir = self.run_dir / "evidence"
        self.data_dir = self.run_dir / "data"

    def init_folders(self) -> "RunDirectory":
        """Khởi tạo tất cả các thư mục con cần thiết."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self

    def save_manifest(self, manifest_data: Dict[str, Any]) -> Path:
        """Ghi file manifest.json vào thư mục đợt chạy."""
        manifest_path = self.run_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)
        return manifest_path

    def save_quality_report(self, report_data: Dict[str, Any]) -> Path:
        """Ghi file quality_report.json vào thư mục đợt chạy."""
        report_path = self.run_dir / "quality_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        return report_path

    def list_raw_files(self) -> List[Path]:
        """Liệt kê danh sách các file gốc tải về trong raw/."""
        if not self.raw_dir.exists():
            return []
        return sorted([p for p in self.raw_dir.iterdir() if p.is_file()])

    def list_evidence_files(self) -> List[Path]:
        """Liệt kê danh sách các ảnh chụp trong evidence/."""
        if not self.evidence_dir.exists():
            return []
        return sorted([p for p in self.evidence_dir.iterdir() if p.is_file()])


def create_run_directory(
    channel_name: str,
    channel_id: Optional[str] = None,
    period_preset: str = "28d",
    base_dir: Optional[Path] = None,
) -> RunDirectory:
    """
    Tạo cấu trúc thư mục đợt chạy mới theo chuẩn:
    runs/<YYYY-MM-DD_HHMMSS>_<channel_slug>_<period>/
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    clean_name = slugify(channel_name)
    # Rút gọn định dạng period (ví dụ: 28_days -> 28d)
    short_period = period_preset.replace("_days", "d").replace("days", "d")
    run_id = f"{timestamp}_{clean_name}_{short_period}"

    run_storage = RunDirectory(run_id=run_id, base_dir=base_dir)
    run_storage.init_folders()

    # Khởi tạo sơ bộ manifest.json
    initial_manifest = {
        "run_id": run_id,
        "channel_id": channel_id or "",
        "channel_name": channel_name,
        "period": period_preset,
        "created_at": datetime.now().isoformat(),
        "status": "initialized",
        "schema_version": "1.0",
    }
    run_storage.save_manifest(initial_manifest)

    logger.info(f"Đã khởi tạo thư mục đợt chạy mới: {run_storage.run_dir}")
    return run_storage
