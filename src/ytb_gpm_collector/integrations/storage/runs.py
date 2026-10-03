"""Quản lý thư mục lưu trữ cho từng đợt chạy (runs/<run_id>/) và sinh báo cáo (Task 3.3).

Cấu trúc mỗi lần chạy:
runs/<run_id>/
├── README.md                 # Báo cáo trực quan cho người dùng đọc
├── manifest.json             # Bản kê toàn bộ file và checksum SHA-256 cho AI/Hệ thống
├── quality_report.json       # Báo cáo đánh giá chất lượng số liệu, đối chiếu và cảnh báo
├── data/
│   ├── channel.json          # Chỉ số tổng quan toàn kênh
│   ├── videos.csv            # Bảng số liệu chi tiết từng video (UTF-8 BOM cho Excel)
│   ├── videos.jsonl          # Object JSON từng video cho AI
│   ├── traffic_sources.csv   # Nguồn lưu lượng truy cập
│   └── daily_metrics.csv     # Chuỗi dữ liệu số liệu theo ngày
├── raw/                      # Toàn bộ tệp XLSX/CSV/ZIP gốc từ YouTube Studio
└── evidence/                 # Ảnh chụp màn hình đối chiếu
"""

import hashlib
import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from ytb_gpm_collector.domain.models import (
    QualityIssue,
    QualityReportSummary,
    QualityReconciliation,
    QualityChecks,
    QualityReport,
    ManifestFileInfo,
    RunManifest,
    NormalizedVideoRecord,
    NormalizedChannelOverview,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. HÀM TIỆN ÍCH CHUỖI & ĐỊNH DẠNG (FORMATTING UTILITIES)
# ==============================================================================

def slugify(text: str) -> str:
    """Chuyển đổi chuỗi tiếng Việt/ký tự đặc biệt thành slug an toàn cho thư mục."""
    if not text:
        return "channel"
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


def compute_file_sha256(file_path: Path) -> str:
    """Tính mã băm SHA-256 của tệp tin để đảm bảo tính toàn vẹn."""
    if not file_path.exists() or not file_path.is_file():
        return ""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.warning(f"Lỗi khi tính sha256 cho {file_path}: {e}")
        return ""


def format_seconds_to_display(seconds: Optional[Union[float, int]]) -> str:
    """Định dạng giây thành chuỗi dễ đọc MM:SS hoặc HH:MM:SS."""
    if seconds is None:
        return "-"
    try:
        s = int(round(float(seconds)))
        m, sec = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"
    except (ValueError, TypeError):
        return "-"


def format_number(val: Optional[Union[int, float]], decimal_places: int = 0) -> str:
    """Định dạng số có dấu phẩy ngăn cách hàng nghìn."""
    if val is None:
        return "-"
    try:
        f_val = float(val)
        if decimal_places == 0:
            return f"{int(round(f_val)):,}"
        return f"{f_val:,.{decimal_places}f}"
    except (ValueError, TypeError):
        return "-"


# ==============================================================================
# 2. HÀM TẢI DỮ LIỆU ĐÃ CHUẨN HÓA TỪ THƯ MỤC RUN
# ==============================================================================

def load_normalized_videos_from_dir(run_dir: Path) -> List[NormalizedVideoRecord]:
    """Tải danh sách NormalizedVideoRecord từ thư mục data/."""
    videos_jsonl = run_dir / "data" / "videos.jsonl"
    records: List[NormalizedVideoRecord] = []

    if videos_jsonl.exists():
        try:
            with open(videos_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        records.append(NormalizedVideoRecord(**data))
                    except Exception as le:
                        logger.warning(f"Bỏ qua dòng lỗi trong {videos_jsonl}: {le}")
            return records
        except Exception as e:
            logger.warning(f"Không thể đọc {videos_jsonl}: {e}")

    # Dự phòng đọc từ videos.csv
    videos_csv = run_dir / "data" / "videos.csv"
    if videos_csv.exists():
        import pandas as pd
        try:
            df = pd.read_csv(videos_csv, dtype=str)
            for _, row in df.iterrows():
                r_dict = row.to_dict()
                clean_dict = {}
                for k, v in r_dict.items():
                    if pd.isna(v) or v == "":
                        clean_dict[k] = None
                    elif k in ["views", "impressions", "subscribers"]:
                        try:
                            clean_dict[k] = int(float(v))
                        except Exception:
                            clean_dict[k] = None
                    elif k in [
                        "duration_seconds",
                        "watch_time_hours",
                        "average_view_duration_seconds",
                        "ctr_percent",
                        "estimated_revenue",
                    ]:
                        try:
                            clean_dict[k] = float(v)
                        except Exception:
                            clean_dict[k] = None
                    else:
                        clean_dict[k] = str(v)
                records.append(NormalizedVideoRecord(**clean_dict))
        except Exception as e:
            logger.warning(f"Không thể đọc {videos_csv}: {e}")

    return records


def load_channel_overview_from_dir(run_dir: Path) -> Optional[NormalizedChannelOverview]:
    """Tải thông tin channel.json nếu tồn tại."""
    ch_file = run_dir / "data" / "channel.json"
    if ch_file.exists():
        try:
            with open(ch_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return NormalizedChannelOverview(**data)
        except Exception as e:
            logger.warning(f"Không thể đọc {ch_file}: {e}")
    return None


# ==============================================================================
# 3. SINH BÁO CÁO CHẤT LƯỢNG (QUALITY REPORT GENERATION)
# ==============================================================================

def generate_quality_report(
    run_dir: Union[Path, str],
    channel_id: Optional[str] = None,
    manifest_data: Optional[Dict[str, Any]] = None,
) -> QualityReport:
    """
    Sinh báo cáo kiểm định chất lượng dữ liệu chi tiết cho đợt chạy (quality_report.json).
    
    Quy tắc kiểm định:
    1. Kiểm tra từng video: ID hợp lệ, tiêu đề, số âm, tỷ lệ CTR (0 - 100%), AVD <= thời lượng video.
    2. Không tự suy diễn/bịa số: ghi nhận null và phân loại chính xác (ok, zero, not_available, failed).
    3. Đối chiếu dòng Tổng (Total) của kênh với tổng các video chi tiết (reconciliation).
    4. Kiểm tra tính toàn vẹn của các file thô (raw/) và sự hiện diện của ảnh bằng chứng (evidence/).
    5. Tính điểm hoàn thiện dữ liệu (completeness_score_percent).
    """
    run_path = Path(run_dir).resolve()
    data_dir = run_path / "data"
    raw_dir = run_path / "raw"
    evidence_dir = run_path / "evidence"

    # 1. Đọc manifest.json hiện có nếu chưa truyền
    if manifest_data is None:
        manifest_file = run_path / "manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception:
                manifest_data = {}
        else:
            manifest_data = {}

    run_id = manifest_data.get("run_id") or run_path.name
    ch_id = channel_id or manifest_data.get("channel_id") or "unknown_channel"
    period_start = manifest_data.get("period_start") or ""
    period_end = manifest_data.get("period_end") or ""

    # 2. Đọc channel.json và video records
    channel_overview = load_channel_overview_from_dir(run_path)
    if channel_overview:
        if not ch_id or ch_id == "unknown_channel":
            ch_id = channel_overview.channel_id
        if not period_start:
            period_start = channel_overview.period_start
        if not period_end:
            period_end = channel_overview.period_end

    video_records = load_normalized_videos_from_dir(run_path)

    issues: List[QualityIssue] = []
    status_counts: Dict[str, int] = {
        "ok": 0,
        "zero": 0,
        "not_available": 0,
        "not_exportable": 0,
        "failed": 0,
        "not_collected": 0,
    }

    # 3. Kiểm tra file thô (raw/)
    raw_files = [p for p in raw_dir.iterdir() if p.is_file()] if raw_dir.exists() else []
    raw_files_intact = True
    if not raw_files:
        issues.append(QualityIssue(
            code="NO_RAW_FILES",
            level="warning",
            message="Không tìm thấy tệp tin gốc nào trong thư mục raw/.",
            source_file="raw/",
        ))
    else:
        for rf in raw_files:
            if rf.stat().st_size == 0:
                raw_files_intact = False
                issues.append(QualityIssue(
                    code="EMPTY_RAW_FILE",
                    level="error",
                    message=f"Tệp tin gốc '{rf.name}' bị rỗng (0 bytes).",
                    source_file=f"raw/{rf.name}",
                ))

    # 4. Kiểm tra ảnh bằng chứng (evidence/)
    evidence_files = [p for p in evidence_dir.iterdir() if p.is_file()] if evidence_dir.exists() else []
    evidence_images_present = len(evidence_files) > 0
    if not evidence_images_present:
        issues.append(QualityIssue(
            code="NO_EVIDENCE_FILES",
            level="info",
            message="Chưa có ảnh chụp màn hình đối chiếu trong thư mục evidence/.",
            source_file="evidence/",
        ))

    # 5. Kiểm tra chi tiết từng video
    valid_videos = 0
    warning_videos = 0
    failed_videos = 0
    total_fields = 0
    populated_fields = 0

    key_fields = ["video_id", "video_title", "views", "watch_time_hours", "impressions", "ctr_percent", "average_view_duration_seconds"]

    for v in video_records:
        st = v.status or "ok"
        status_counts[st] = status_counts.get(st, 0) + 1

        v_has_error = False
        v_has_warning = False

        # Đo lường độ hoàn thiện
        for fld in key_fields:
            total_fields += 1
            if getattr(v, fld, None) is not None:
                populated_fields += 1

        # Kiểm tra video_id
        if not v.video_id or v.video_id.startswith("unknown_row"):
            v_has_error = True
            issues.append(QualityIssue(
                code="MISSING_VIDEO_ID",
                level="error",
                video_id=v.video_id,
                video_title=v.video_title,
                field="video_id",
                message=f"Dòng video không có ID định danh hợp lệ ({v.video_id}).",
                source_file=v.source_file,
            ))

        # Kiểm tra tiêu đề
        if not v.video_title:
            v_has_warning = True
            issues.append(QualityIssue(
                code="MISSING_TITLE",
                level="warning",
                video_id=v.video_id,
                field="video_title",
                message=f"Video '{v.video_id}' thiếu tiêu đề hiển thị.",
                source_file=v.source_file,
            ))

        # Kiểm tra lượt xem
        if v.views is None:
            if st == "ok":
                v_has_warning = True
                issues.append(QualityIssue(
                    code="MISSING_VIEWS",
                    level="warning",
                    video_id=v.video_id,
                    video_title=v.video_title,
                    field="views",
                    message=f"Video '{v.video_id}' có trạng thái ok nhưng thiếu chỉ số lượt xem (views).",
                    source_file=v.source_file,
                ))
        elif v.views < 0:
            v_has_error = True
            issues.append(QualityIssue(
                code="NEGATIVE_VIEWS",
                level="error",
                video_id=v.video_id,
                video_title=v.video_title,
                field="views",
                message=f"Lượt xem có giá trị âm bất thường: {v.views}.",
                source_file=v.source_file,
            ))
        elif v.views == 0 and (v.impressions or 0) == 0:
            issues.append(QualityIssue(
                code="ZERO_VIEWS",
                level="info",
                video_id=v.video_id,
                video_title=v.video_title,
                field="views",
                message=f"Video '{v.video_id}' không có lượt xem và không có lượt hiển thị trong khoảng thời gian này.",
                source_file=v.source_file,
            ))

        # Kiểm tra thời gian xem
        if v.watch_time_hours is not None and v.watch_time_hours < 0:
            v_has_error = True
            issues.append(QualityIssue(
                code="NEGATIVE_WATCH_TIME",
                level="error",
                video_id=v.video_id,
                video_title=v.video_title,
                field="watch_time_hours",
                message=f"Thời gian xem có giá trị âm: {v.watch_time_hours}.",
                source_file=v.source_file,
            ))

        # Kiểm tra CTR (%)
        if v.ctr_percent is not None:
            if v.ctr_percent < 0 or v.ctr_percent > 100:
                v_has_error = True
                issues.append(QualityIssue(
                    code="INVALID_CTR",
                    level="error",
                    video_id=v.video_id,
                    video_title=v.video_title,
                    field="ctr_percent",
                    message=f"Tỷ lệ nhấp CTR bất thường ({v.ctr_percent}%). Phải nằm trong khoảng 0% - 100%.",
                    source_file=v.source_file,
                ))
        elif (v.impressions or 0) >= 50:
            v_has_warning = True
            issues.append(QualityIssue(
                code="MISSING_CTR",
                level="warning",
                video_id=v.video_id,
                video_title=v.video_title,
                field="ctr_percent",
                message=f"Video có {v.impressions} lượt hiển thị nhưng không có tỷ lệ nhấp CTR.",
                source_file=v.source_file,
            ))

        # Kiểm tra thời lượng xem trung bình (AVD)
        if v.average_view_duration_seconds is not None and v.duration_seconds is not None:
            if v.average_view_duration_seconds > (v.duration_seconds * 1.05):
                v_has_warning = True
                issues.append(QualityIssue(
                    code="AVD_EXCEEDS_DURATION",
                    level="warning",
                    video_id=v.video_id,
                    video_title=v.video_title,
                    field="average_view_duration_seconds",
                    message=(
                        f"Thời lượng xem TB ({v.average_view_duration_seconds:.0f}s) vượt quá "
                        f"tổng thời lượng video ({v.duration_seconds:.0f}s)."
                    ),
                    source_file=v.source_file,
                ))
        elif v.average_view_duration_seconds is None and (v.views or 0) > 0:
            issues.append(QualityIssue(
                code="MISSING_AVD",
                level="info",
                video_id=v.video_id,
                video_title=v.video_title,
                field="average_view_duration_seconds",
                message="YouTube Studio không xuất cột Thời lượng xem trung bình (AVD) trong bảng dữ liệu này.",
                source_file=v.source_file,
            ))

        # Đánh giá phân loại video
        if v_has_error:
            failed_videos += 1
        elif v_has_warning:
            warning_videos += 1
        else:
            valid_videos += 1

    # Đo độ phủ của các báo cáo bổ sung thay vì chỉ đếm trường bảng video.
    depth = manifest_data.get("collection_depth", "standard")
    daily_path = data_dir / "daily_metrics.csv"
    traffic_path = data_dir / "traffic_sources.csv"
    channel_daily_path = data_dir / "daily_channel_metrics.csv"
    daily_ids = set()
    daily_dates = set()
    daily_views: Dict[str, int] = {}
    if daily_path.exists():
        with daily_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("video_id"):
                    daily_ids.add(row["video_id"])
                    if row.get("views", "").strip():
                        daily_views[row["video_id"]] = daily_views.get(row["video_id"], 0) + int(float(row["views"]))
                if row.get("date"):
                    daily_dates.add(row["date"])
    video_ids = {v.video_id for v in video_records}
    covered_ids = {v.video_id for v in video_records if v.video_id in daily_ids and v.views is not None and daily_views.get(v.video_id) == v.views}
    traffic_rows = 0
    channel_traffic_rows = 0
    traffic_video_ids = set()
    if traffic_path.exists():
        with traffic_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                traffic_rows += 1
                if row.get("video_id"):
                    traffic_video_ids.add(row["video_id"])
                else:
                    channel_traffic_rows += 1
    channel_days = 0
    if channel_daily_path.exists():
        with channel_daily_path.open(encoding="utf-8-sig", newline="") as stream:
            channel_days = sum(1 for _ in csv.DictReader(stream))

    if depth in ("standard", "full"):
        total_fields += 1
        populated_fields += int(channel_traffic_rows > 0)
        if channel_traffic_rows == 0:
            issues.append(QualityIssue(code="MISSING_TRAFFIC_SOURCES", level="warning", message="Chưa có dòng dữ liệu nguồn truy cập."))
        if video_ids:
            total_fields += len(video_ids)
            populated_fields += len(video_ids & traffic_video_ids)
            if video_ids - traffic_video_ids:
                issues.append(QualityIssue(code="INCOMPLETE_VIDEO_TRAFFIC", level="warning", message=f"Nguồn truy cập mới có cho {len(video_ids & traffic_video_ids)}/{len(video_ids)} video."))
        if video_ids:
            total_fields += len(video_ids)
            populated_fields += len(covered_ids)
            if covered_ids != video_ids:
                issues.append(QualityIssue(code="INCOMPLETE_VIDEO_DAILY", level="warning", message=f"Chuỗi ngày khớp tổng lượt xem của {len(covered_ids)}/{len(video_ids)} video."))
    if daily_dates and period_end and max(daily_dates) != period_end:
        issues.append(QualityIssue(code="PERIOD_DAILY_MISMATCH", level="warning", message=f"Dữ liệu ngày kết thúc {max(daily_dates)}, khác period_end {period_end}."))

    # Tính tỷ lệ hoàn thiện
    completeness_score = (
        round((populated_fields / total_fields) * 100.0, 1)
        if total_fields > 0
        else (100.0 if not video_records else 0.0)
    )

    # 6. Đối chiếu số liệu dòng Tổng (Reconciliation)
    sum_views = sum((v.views or 0) for v in video_records)
    ch_views = channel_overview.total_views if channel_overview else None
    reconciled = True
    diff_val = None
    diff_pct = None
    notes = "Chưa có dữ liệu tổng quan kênh (channel.json) để đối chiếu."

    if ch_views is not None:
        diff_val = ch_views - sum_views
        diff_pct = round((diff_val / ch_views) * 100.0, 2) if ch_views > 0 else 0.0
        if diff_val == 0:
            reconciled = True
            notes = (
                f"Đối chiếu khớp chính xác 100%: Tổng lượt xem các video ({sum_views:,}) "
                f"khớp hoàn toàn với dòng Tổng kênh ({ch_views:,})."
            )
        elif diff_val > 0:
            reconciled = True
            notes = (
                f"Số liệu khớp hợp lý: Dòng Tổng kênh ({ch_views:,}) cao hơn tổng video ({sum_views:,}) "
                f"là {diff_val:,} lượt xem ({diff_pct}% chênh lệch do video riêng tư, đã xóa hoặc video cũ ngoài phạm vi trích xuất)."
            )
        else:
            reconciled = False
            notes = (
                f"Cảnh báo: Tổng lượt xem video chi tiết ({sum_views:,}) vượt quá dòng Tổng kênh ({ch_views:,}). "
                f"Chênh lệch: {abs(diff_val):,} lượt xem."
            )
            issues.append(QualityIssue(
                code="VIEW_RECONCILIATION_MISMATCH",
                level="warning",
                message=notes,
                source_file="data/videos.jsonl vs data/channel.json",
            ))

    recon = QualityReconciliation(
        reconciled=reconciled,
        total_video_views=sum_views,
        channel_summary_views=ch_views,
        views_difference=diff_val,
        difference_percent=diff_pct,
        notes=notes,
    )

    # 7. Khuyến nghị xử lý (Suggestions)
    suggestions: List[str] = []
    if failed_videos > 0:
        suggestions.append(f"Có {failed_videos} video bị lỗi dữ liệu định dạng. Cần kiểm tra lại cấu trúc file xuất.")
    if not evidence_images_present:
        suggestions.append("Nên chụp ảnh biểu đồ tổng quan (evidence/analytics_overview.png) để lưu bằng chứng đối chiếu trực quan.")
    if any(i.code == "MISSING_AVD" for i in issues):
        suggestions.append("Trong YouTube Studio, bạn có thể bấm dấu '+' trên bảng nâng cao để thêm cột 'Thời lượng xem trung bình' trước khi xuất.")
    if any(i.code == "MISSING_TRAFFIC_SOURCES" for i in issues):
        suggestions.append("Cần xuất bảng nguồn lưu lượng truy cập riêng trong Studio.")
    if any(i.code == "INCOMPLETE_VIDEO_TRAFFIC" for i in issues):
        suggestions.append("Cần xuất bảng nguồn truy cập riêng cho các video còn thiếu.")
    if any(i.code == "INCOMPLETE_VIDEO_DAILY" for i in issues):
        suggestions.append("Cần xuất chuỗi ngày cho các video chưa khớp tổng lượt xem trong kỳ.")
    if len(video_records) == 0:
        suggestions.append("Không có video nào được trích xuất. Kiểm tra xem kênh có video công khai trong khoảng thời gian đã chọn hay không.")

    # 8. Xác định trạng thái tổng thể
    total_errors = sum(1 for i in issues if i.level == "error")
    total_warnings = sum(1 for i in issues if i.level == "warning")

    if total_errors > 0 or not raw_files_intact:
        overall_status = "failed"
    elif total_warnings > 0 or not reconciled or completeness_score < 100.0:
        overall_status = "warnings"
    else:
        overall_status = "passed"

    summary_obj = QualityReportSummary(
        total_videos_checked=len(video_records),
        valid_videos_count=valid_videos,
        warning_videos_count=warning_videos,
        failed_videos_count=failed_videos,
        total_warnings=total_warnings,
        total_errors=total_errors,
        completeness_score_percent=completeness_score,
    )

    checks_obj = QualityChecks(
        channel_id_verified=bool(ch_id and ch_id != "unknown_channel"),
        period_consistency=bool(period_start and period_end) and not any(i.code == "PERIOD_DAILY_MISMATCH" for i in issues),
        summary_reconciliation=recon,
        raw_files_intact=raw_files_intact,
        evidence_images_present=evidence_images_present,
    )

    report = QualityReport(
        run_id=run_id,
        generated_at=datetime.now().isoformat(),
        status=overall_status,
        channel_id=ch_id,
        period_start=period_start,
        period_end=period_end,
        summary=summary_obj,
        status_breakdown=status_counts,
        checks=checks_obj,
        issues=issues,
        suggestions=suggestions,
        coverage={"video_count": len(video_ids), "video_daily_count": len(covered_ids), "video_daily_dates": len(daily_dates), "channel_daily_count": channel_days, "traffic_sources_count": traffic_rows, "channel_traffic_sources_count": channel_traffic_rows, "video_traffic_count": len(video_ids & traffic_video_ids)},
    )

    return report


# ==============================================================================
# 4. SINH BẢN KÊ GÓI DỮ LIỆU (MANIFEST GENERATION)
# ==============================================================================

def generate_manifest(
    run_dir: Union[Path, str],
    channel_id: Optional[str] = None,
    channel_name: Optional[str] = None,
    period: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    period_kind: Optional[str] = None,
    profile_id: Optional[str] = None,
    profile_name: Optional[str] = None,
    status: Optional[str] = None,
    quality_report: Optional[QualityReport] = None,
) -> RunManifest:
    """
    Sinh manifest.json theo chuẩn thiết kế kiến trúc:
    Bao gồm ID lần chạy, cấu hình, thời gian, phiên bản schema, trạng thái,
    danh mục toàn bộ tệp tin kèm mã băm SHA-256 và tóm tắt chất lượng.
    """
    run_path = Path(run_dir).resolve()

    # 1. Đọc manifest cũ nếu có để giữ các thuộc tính phiên trước
    manifest_file = run_path / "manifest.json"
    old_data: Dict[str, Any] = {}
    if manifest_file.exists():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            pass

    # 2. Đồng bộ các thuộc tính định danh
    r_id = old_data.get("run_id") or run_path.name
    c_id = channel_id or old_data.get("channel_id") or "unknown_channel"
    c_name = channel_name or old_data.get("channel_name")
    p_id = profile_id or old_data.get("profile_id")
    p_name = profile_name or old_data.get("profile_name")
    p_preset = period or old_data.get("period", "28_days")
    p_start = period_start or old_data.get("period_start", "")
    p_end = period_end or old_data.get("period_end", "")
    p_kind = period_kind or old_data.get("period_kind", "fixed_calendar_range")
    c_at = old_data.get("created_at") or datetime.now().isoformat()
    f_at = datetime.now().isoformat()

    # Lấy thông tin từ channel.json nếu thiếu
    ch_overview = load_channel_overview_from_dir(run_path)
    if ch_overview:
        if not c_id or c_id == "unknown_channel":
            c_id = ch_overview.channel_id
        if not c_name and ch_overview.channel_name:
            c_name = ch_overview.channel_name
        if not p_start:
            p_start = ch_overview.period_start
        if not p_end:
            p_end = ch_overview.period_end
        if not p_kind:
            p_kind = ch_overview.period_kind

    # 3. Quét tất cả các tệp tin trong run_dir (trừ manifest.json để tránh đệ quy SHA)
    files_list: List[ManifestFileInfo] = []
    total_size = 0

    for file_path in sorted(run_path.rglob("*")):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(run_path).as_posix()
        if rel_path == "manifest.json" or rel_path.startswith("."):
            continue

        f_size = file_path.stat().st_size
        total_size += f_size
        sha = compute_file_sha256(file_path)

        # Phân loại vai trò tệp tin
        if rel_path.startswith("data/"):
            cat = "data"
        elif rel_path.startswith("raw/"):
            cat = "raw"
        elif rel_path.startswith("evidence/"):
            cat = "evidence"
        elif rel_path in ["README.md", "quality_report.json"]:
            cat = "report"
        else:
            cat = "other"

        files_list.append(
            ManifestFileInfo(
                path=rel_path,
                size_bytes=f_size,
                sha256=sha,
                category=cat,
            )
        )

    # 4. Đếm số lượng các mục dữ liệu
    video_records = load_normalized_videos_from_dir(run_path)
    video_count = len(video_records)

    daily_metrics_file = run_path / "data" / "daily_metrics.csv"
    daily_count = 0
    if daily_metrics_file.exists():
        try:
            with open(daily_metrics_file, "r", encoding="utf-8") as f:
                daily_count = max(0, sum(1 for _ in f) - 1)
        except Exception:
            pass

    traffic_file = run_path / "data" / "traffic_sources.csv"
    traffic_count = 0
    if traffic_file.exists():
        try:
            with open(traffic_file, "r", encoding="utf-8") as f:
                traffic_count = max(0, sum(1 for _ in f) - 1)
        except Exception:
            pass

    raw_files_count = len([f for f in files_list if f.category == "raw"])
    evidence_files_count = len([f for f in files_list if f.category == "evidence"])

    summary_dict = {
        "video_count": video_count,
        "daily_metrics_count": daily_count,
        "traffic_sources_count": traffic_count,
        "raw_files_count": raw_files_count,
        "evidence_files_count": evidence_files_count,
        "total_files_tracked": len(files_list),
        "total_size_bytes": total_size,
    }

    # 5. Tóm tắt chất lượng
    quality_summary = None
    if quality_report:
        quality_summary = {
            "status": quality_report.status,
            "completeness_score_percent": quality_report.summary.completeness_score_percent,
            "total_warnings": quality_report.summary.total_warnings,
            "total_errors": quality_report.summary.total_errors,
            "reconciled": (
                quality_report.checks.summary_reconciliation.reconciled
                if quality_report.checks.summary_reconciliation
                else True
            ),
        }

    # 6. Xác định trạng thái đợt chạy
    if status:
        final_status = status
    elif quality_report:
        if quality_report.status == "failed" or video_count == 0:
            final_status = "failed"
        elif quality_report.status == "warnings":
            final_status = "partial"
        else:
            final_status = "success"
    else:
        final_status = old_data.get("status", "success")

    manifest = RunManifest(
        schema_version="1.0",
        run_id=r_id,
        channel_id=c_id,
        channel_name=c_name,
        profile_id=p_id,
        profile_name=p_name,
        period=p_preset,
        period_start=p_start,
        period_end=p_end,
        period_kind=p_kind,
        collection_depth=old_data.get("collection_depth", "standard"),
        extra_exports=old_data.get("extra_exports", {}),
        created_at=c_at,
        finished_at=f_at,
        status=final_status,
        summary=summary_dict,
        files=files_list,
        quality_summary=quality_summary,
    )

    return manifest


# ==============================================================================
# 5. TỰ ĐỘNG SINH BÁO CÁO README.md CHO NGƯỜI DÙNG
# ==============================================================================

def generate_readme(
    run_dir: Union[Path, str],
    manifest: Optional[RunManifest] = None,
    quality_report: Optional[QualityReport] = None,
    channel_overview: Optional[NormalizedChannelOverview] = None,
    video_records: Optional[List[NormalizedVideoRecord]] = None,
) -> str:
    """
    Tự động sinh tài liệu README.md tóm tắt kết quả đợt chạy:
    - Báo cáo dễ đọc cho người dùng: kênh, phạm vi thời gian, số video.
    - Bảng "Đã lấy / Thiếu / Cần đăng nhập lại" theo quy chuẩn kiến trúc.
    - Liên kết tương đối đến tất cả các tệp tin trong gói kết quả.
    - Ghi rõ ngày chốt dữ liệu Studio (period_end).
    - Top video nổi bật và bảng đánh giá chất lượng.
    """
    run_path = Path(run_dir).resolve()

    # Nạp dữ liệu nếu chưa được cung cấp
    if channel_overview is None:
        channel_overview = load_channel_overview_from_dir(run_path)

    if video_records is None:
        video_records = load_normalized_videos_from_dir(run_path)

    if quality_report is None:
        quality_file = run_path / "quality_report.json"
        if quality_file.exists():
            try:
                with open(quality_file, "r", encoding="utf-8") as f:
                    quality_report = QualityReport(**json.load(f))
            except Exception:
                quality_report = generate_quality_report(run_path)
        else:
            quality_report = generate_quality_report(run_path)

    if manifest is None:
        manifest_file = run_path / "manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = RunManifest(**json.load(f))
            except Exception:
                manifest = generate_manifest(run_path, quality_report=quality_report)
        else:
            manifest = generate_manifest(run_path, quality_report=quality_report)

    # 1. Các thông tin định danh
    channel_name = manifest.channel_name or (channel_overview.channel_name if channel_overview else None) or "Kênh YouTube"
    channel_id = manifest.channel_id or (channel_overview.channel_id if channel_overview else None) or "N/A"
    run_id = manifest.run_id
    period_start = manifest.period_start or "N/A"
    period_end = manifest.period_end or "N/A"
    period_preset = manifest.period or "28_days"

    period_display = period_preset.replace("_days", " ngày qua").replace("days", " ngày qua").replace("28d", "28 ngày qua")

    # Huy hiệu trạng thái
    st_val = manifest.status
    if st_val == "success":
        status_badge = "🟢 **Hoàn tất (Thành công)**"
    elif st_val == "partial":
        status_badge = "🟡 **Hoàn tất (Có cảnh báo nhẹ)**"
    elif st_val == "failed":
        status_badge = "🔴 **Thất bại / Cần kiểm tra lại**"
    else:
        status_badge = f"⚪ **{st_val.upper()}**"

    # 2. Số liệu kênh
    total_views = format_number(channel_overview.total_views if channel_overview else None)
    total_watch = format_number(channel_overview.total_watch_time_hours if channel_overview else None, 1)
    total_impr = format_number(channel_overview.total_impressions if channel_overview else None)
    avg_ctr = format_number(channel_overview.average_ctr_percent if channel_overview else None, 2)
    total_subs = (
        f"{channel_overview.total_subscribers:+d}"
        if (channel_overview and channel_overview.total_subscribers is not None)
        else "-"
    )
    video_count_display = len(video_records)

    # 3. Phân tích bảng tình trạng dữ liệu: Đã lấy / Thiếu / Cần đăng nhập lại
    # Bảng video
    has_videos = len(video_records) > 0
    status_videos = "✅ Đã lấy đủ" if has_videos else "❌ Thiếu"
    detail_videos = f"{len(video_records)} video đã chuẩn hóa"

    # Dữ liệu theo ngày
    daily_file = run_path / "data" / "daily_metrics.csv"
    has_daily = daily_file.exists() and daily_file.stat().st_size > 50
    daily_count = manifest.summary.get("daily_metrics_count", 0)
    status_daily = "✅ Đã lấy" if has_daily else "⚪ Không có"
    coverage = quality_report.coverage if quality_report else {}
    detail_daily = (f"{daily_count} dòng / {coverage.get('video_daily_count', 0)}/{coverage.get('video_count', 0)} video khớp tổng" if has_daily else "Không có file daily")

    # Nguồn lưu lượng
    traffic_file = run_path / "data" / "traffic_sources.csv"
    traffic_count = manifest.summary.get("traffic_sources_count", 0)
    has_traffic = traffic_file.exists() and traffic_count > 0
    status_traffic = "✅ Đã lấy" if has_traffic else "⚪ Chưa trích xuất"
    detail_traffic = f"{traffic_count} dòng nguồn traffic" if has_traffic else "Chưa xuất bảng nguồn"

    # Tổng quan kênh
    ch_file = run_path / "data" / "channel.json"
    status_overview = "✅ Đã lấy" if ch_file.exists() else "❌ Thiếu"
    detail_overview = "Đã tính chỉ số toàn kênh" if ch_file.exists() else "Thiếu file tổng quan"

    # Tệp tin thô raw/
    raw_files = [p for p in (run_path / "raw").iterdir() if p.is_file()] if (run_path / "raw").exists() else []
    status_raw = "✅ Đã lưu" if len(raw_files) > 0 else "❌ Thiếu"
    detail_raw = f"{len(raw_files)} tệp tin gốc Studio"

    # Ảnh bằng chứng evidence/
    evidence_files = [p for p in (run_path / "evidence").iterdir() if p.is_file()] if (run_path / "evidence").exists() else []
    status_evidence = "✅ Đã lưu" if len(evidence_files) > 0 else "⚪ Chưa có"
    detail_evidence = f"{len(evidence_files)} ảnh chụp màn hình"

    # Trạng thái đăng nhập
    if has_videos:
        status_auth = "✅ Hợp lệ"
        detail_auth = "Phiên hoạt động tốt (Không cần đăng nhập lại)"
    else:
        status_auth = "⚠️ Cần kiểm tra"
        detail_auth = "Không lấy được dữ liệu, vui lòng kiểm tra đăng nhập trên GPM"

    # 4. Top Video Xem Nhiều Nhất
    sorted_videos = sorted(video_records, key=lambda x: (x.views or 0), reverse=True)
    top_videos = sorted_videos[:10]

    video_table_rows = []
    for idx, v in enumerate(top_videos, 1):
        v_title = (v.video_title or "Không có tiêu đề").replace("|", "-")
        if len(v_title) > 55:
            v_title = v_title[:52] + "..."
        # Tạo liên kết đến YouTube nếu ID hợp lệ
        v_link = f"[{v.video_id}](https://youtu.be/{v.video_id})" if re.match(r"^[A-Za-z0-9_-]{11}$", v.video_id) else f"`{v.video_id}`"
        v_views = format_number(v.views)
        v_watch = format_number(v.watch_time_hours, 1)
        v_ctr = f"{v.ctr_percent:.2f}%" if v.ctr_percent is not None else "-"
        v_avd = format_seconds_to_display(v.average_view_duration_seconds)
        v_status = "✅ OK" if v.status == "ok" else f"⚠️ {v.status}"

        video_table_rows.append(
            f"| {idx} | {v_link} | {v_title} | {v_views} | {v_watch} | {v_ctr} | {v_avd} | {v_status} |"
        )

    if not video_table_rows:
        video_table_rows.append("| - | - | Không có dữ liệu video | - | - | - | - | - |")

    # 5. Phân tích đối chiếu chất lượng
    q_summary = quality_report.summary
    q_checks = quality_report.checks
    recon_notes = q_checks.summary_reconciliation.notes if q_checks.summary_reconciliation else "Không có đối chiếu"

    # Bảng danh sách cảnh báo nếu có
    issues_content = ""
    notable_issues = [i for i in quality_report.issues if i.level in ["warning", "error"]]
    if notable_issues:
        issues_rows = []
        for iss in notable_issues[:15]:
            lvl_icon = "❌ Lỗi" if iss.level == "error" else "⚠️ Cảnh báo"
            v_id_str = f"`{iss.video_id}`" if iss.video_id else "-"
            msg_clean = iss.message.replace("|", "-")
            issues_rows.append(f"| {lvl_icon} | `{iss.code}` | {v_id_str} | {msg_clean} |")
        issues_content = (
            "### ⚠️ Danh Sách Cảnh Báo & Lỗi Phát Hiện\n\n"
            "| Mức độ | Mã kiểm tra | Video liên quan | Nội dung chi tiết |\n"
            "| :---: | :--- | :---: | :--- |\n"
            + "\n".join(issues_rows)
            + "\n\n"
        )
    else:
        issues_content = "> ✨ **Không có cảnh báo hoặc lỗi nghiêm trọng:** Dữ liệu chuẩn xác, đầy đủ và khớp đối chiếu 100%.\n\n"

    # Danh sách khuyến nghị
    suggestions_content = ""
    if quality_report.suggestions:
        sug_items = "\n".join(f"- {s}" for s in quality_report.suggestions)
        suggestions_content = f"### 💡 Khuyến Nghị Xử Lý Cho AI & Người Dùng\n\n{sug_items}\n\n"

    # 6. Soạn thảo toàn bộ Markdown
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    markdown = f"""# 📊 Báo Cáo Thu Thập Dữ Liệu YouTube Studio

> **Trạng thái đợt chạy:** {status_badge}  
> **Thời điểm sinh báo cáo:** `{now_str}`  
> **Gói dữ liệu (Run ID):** `{run_id}`

---

## 1. Thông Tin Đợt Chạy & Nhận Diện Kênh

| Thuộc tính | Giá trị |
| :--- | :--- |
| **Kênh YouTube** | **{channel_name}** |
| **Channel ID** | `{channel_id}` |
| **Mã đợt chạy** | `{run_id}` |
| **Khoảng thời gian phân tích** | **{period_start}** đến **{period_end}** (`{period_display}`) |
| **Loại khoảng thời gian** | `{manifest.period_kind}` |
| **Thời điểm bắt đầu** | `{manifest.created_at}` |
| **Trạng thái tổng quát** | {status_badge} |

---

## 2. Chỉ Số Tổng Quan Toàn Kênh (Studio Overview)

Số liệu tổng thể toàn kênh trích xuất từ YouTube Studio trong khoảng thời gian từ **{period_start}** đến **{period_end}**:

| Chỉ số tổng quan | Giá trị | Đơn vị | Ghi chú |
| :--- | :---: | :---: | :--- |
| **Tổng lượt xem (Views)** | **{total_views}** | lượt | Toàn bộ kênh trong kỳ |
| **Thời gian xem (Watch Time)** | **{total_watch}** | giờ | Tổng thời lượng khán giả xem |
| **Lượt hiển thị (Impressions)** | **{total_impr}** | lượt | Số lần thumbnail hiển thị |
| **Tỷ lệ nhấp TB (Average CTR)** | **{avg_ctr}%** | % | Trung bình toàn kênh |
| **Người đăng ký ròng (Subscribers)** | **{total_subs}** | người | Biến động đăng ký mới |
| **Số lượng video trích xuất** | **{video_count_display}** | video | Bảng chi tiết Studio |

---

## 3. Tình Trạng Dữ Liệu: Đã Lấy / Thiếu / Cần Đăng Nhập Lại

Kiểm tra tính sẵn sàng và đầy đủ của từng thành phần dữ liệu theo đặc tả kỹ thuật:

| Thành phần dữ liệu | Trạng thái | Số lượng / Chi tiết | Tệp tin liên kết tương đối |
| :--- | :---: | :--- | :--- |
| **Bảng chi tiết video** | {status_videos} | {detail_videos} | [`data/videos.csv`](data/videos.csv) • [`data/videos.jsonl`](data/videos.jsonl) |
| **Số liệu theo ngày** | {status_daily} | {detail_daily} | [`data/daily_metrics.csv`](data/daily_metrics.csv) |
| **Nguồn lưu lượng** | {status_traffic} | {detail_traffic} | [`data/traffic_sources.csv`](data/traffic_sources.csv) |
| **Tổng quan toàn kênh** | {status_overview} | {detail_overview} | [`data/channel.json`](data/channel.json) |
| **Tệp tin thô từ Studio** | {status_raw} | {detail_raw} | [`raw/`](raw/) |
| **Ảnh chụp bằng chứng** | {status_evidence} | {detail_evidence} | [`evidence/`](evidence/) |
| **Trạng thái đăng nhập Studio** | {status_auth} | {detail_auth} | - |

> 📌 **Lưu ý về mốc dữ liệu:** Dữ liệu Studio được chốt đến hết ngày **`{period_end}`**. Mọi chỉ số đều giữ nguyên đơn vị gốc từ YouTube, không suy diễn hoặc tự sinh số liệu giả khi bị thiếu.

---

## 4. Top Video Xem Nhiều Nhất Trong Kỳ

Danh sách video có lượt xem cao nhất được trích xuất từ báo cáo (sắp xếp giảm dần):

| # | ID Video | Tiêu đề | Lượt xem | Giờ xem | CTR (%) | AVD | Trạng thái |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
{chr(10).join(video_table_rows)}

*(Hiển thị top 10 video nổi bật. Xem danh sách đầy đủ {len(video_records)} video tại [`data/videos.csv`](data/videos.csv) hoặc [`data/videos.jsonl`](data/videos.jsonl))*

---

## 5. Đánh Giá Chất Lượng Dữ Liệu & Đối Chiếu (Quality Check)

- **Điểm hoàn thiện dữ liệu (Completeness Score):** **`{q_summary.completeness_score_percent}%`**
- **Thống kê video:** `{q_summary.valid_videos_count}` video hợp lệ • `{q_summary.warning_videos_count}` cảnh báo • `{q_summary.failed_videos_count}` lỗi
- **Kết quả đối chiếu tổng dòng (Reconciliation):**  
  > ℹ️ {recon_notes}

{issues_content}{suggestions_content}---

## 6. Danh Mục Tệp Tin & Hướng Dẫn Sử Dụng Cho AI / Người Dùng

| Tệp tin liên kết tương đối | Đối tượng chính | Mô tả chức năng & định dạng |
| :--- | :---: | :--- |
| [`data/videos.csv`](data/videos.csv) | Người dùng (Excel) | Bảng số liệu chi tiết từng video, hỗ trợ mở trực tiếp bằng Microsoft Excel với bảng mã UTF-8 BOM tiếng Việt. |
| [`data/videos.jsonl`](data/videos.jsonl) | AI & Script | Mỗi dòng là một JSON object chuẩn của một video, giữ nguyên kiểu số thực/nguyên và `null` an toàn. |
| [`data/channel.json`](data/channel.json) | AI & Người dùng | Chỉ số toàn kênh, khoảng ngày phân tích và tệp nguồn gốc. |
| [`data/daily_metrics.csv`](data/daily_metrics.csv) | Phân tích xu hướng | Chuỗi lượt xem từng video theo ngày; giờ xem chỉ có khi Studio xuất cột đó. |
| [`data/daily_channel_metrics.csv`](data/daily_channel_metrics.csv) | Phân tích xu hướng kênh | Chuỗi tổng lượt xem toàn kênh theo ngày, nếu Studio cung cấp. |
| [`data/traffic_sources.csv`](data/traffic_sources.csv) | Phân tích nguồn | Bảng chi tiết tỷ lệ đóng góp của từng nguồn lưu lượng (Tìm kiếm, Đề xuất...). |
| [`quality_report.json`](quality_report.json) | AI đối chiếu | Báo cáo chi tiết kiểm định chất lượng: kiểm tra null, đối chiếu tổng dòng, cảnh báo bất thường. |
| [`manifest.json`](manifest.json) | Hệ thống quản lý | Bản kê toàn bộ tệp tin, kích thước và mã băm SHA-256 để kiểm tra tính toàn vẹn. |
| [`raw/`](raw/) | Lưu trữ gốc | Toàn bộ tệp XLSX/CSV/ZIP tải trực tiếp từ YouTube Studio không qua chỉnh sửa. |
| [`evidence/`](evidence/) | Bằng chứng đối chiếu | Ảnh chụp màn hình biểu đồ và bảng Studio để đối chiếu xác minh khi cần thiết. |

---
*Báo cáo được sinh tự động bởi YouTube Studio Data Collector v1.0.0.*
"""
    return markdown.strip() + "\n"


# ==============================================================================
# 6. LỚP QUẢN LÝ THƯ MỤC CHẠY (RUNDIRECTORY) & HÀM THỰC THI CHÍNH
# ==============================================================================

class RunDirectory:
    """Đại diện cho thư mục một đợt thu thập dữ liệu (runs/<run_id>/)."""

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

    def save_manifest(self, manifest_data: Union[Dict[str, Any], RunManifest]) -> Path:
        """Ghi file manifest.json vào thư mục đợt chạy."""
        manifest_path = self.run_dir / "manifest.json"
        data = manifest_data.model_dump() if isinstance(manifest_data, RunManifest) else manifest_data
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return manifest_path

    def save_quality_report(self, report_data: Union[Dict[str, Any], QualityReport]) -> Path:
        """Ghi file quality_report.json vào thư mục đợt chạy."""
        report_path = self.run_dir / "quality_report.json"
        data = report_data.model_dump() if isinstance(report_data, QualityReport) else report_data
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return report_path

    def save_readme(self, readme_content: str) -> Path:
        """Ghi file README.md vào thư mục đợt chạy."""
        readme_path = self.run_dir / "README.md"
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)
        return readme_path

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

    def build_quality_report(self) -> QualityReport:
        """Tự động kiểm định và ghi quality_report.json."""
        report = generate_quality_report(self.run_dir)
        self.save_quality_report(report)
        return report

    def build_manifest(self, quality_report: Optional[QualityReport] = None) -> RunManifest:
        """Tự động quét tệp tin, tính SHA-256 và ghi manifest.json."""
        manifest = generate_manifest(self.run_dir, quality_report=quality_report)
        self.save_manifest(manifest)
        return manifest

    def build_readme(
        self,
        manifest: Optional[RunManifest] = None,
        quality_report: Optional[QualityReport] = None,
    ) -> str:
        """Tự động sinh và ghi README.md trực quan."""
        content = generate_readme(
            run_dir=self.run_dir,
            manifest=manifest,
            quality_report=quality_report,
        )
        self.save_readme(content)
        return content

    def build_all_reports(self) -> Dict[str, Path]:
        """
        Quy trình chuẩn: Sinh trọn bộ 3 tệp báo cáo:
        1. quality_report.json
        2. manifest.json
        3. README.md
        """
        logger.info(f"Bắt đầu sinh gói báo cáo cho run: {self.run_id}")
        # Bước 1: Sinh quality_report
        q_report = self.build_quality_report()

        # Bước 2: Sinh manifest.json (kèm quality summary và sha256 các file)
        m_report = self.build_manifest(quality_report=q_report)

        # Bước 3: Sinh README.md
        readme_str = self.build_readme(manifest=m_report, quality_report=q_report)

        # Cập nhật lại manifest để thêm README.md và quality_report.json vào danh sách file
        m_report = self.build_manifest(quality_report=q_report)

        res = {
            "quality_report": self.run_dir / "quality_report.json",
            "manifest": self.run_dir / "manifest.json",
            "readme": self.run_dir / "README.md",
        }
        logger.info(f"Đã hoàn thành sinh báo cáo tại: {self.run_dir}")
        return res


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


def build_run_reports(
    run_dir: Union[Path, str],
    channel_id: Optional[str] = None,
    channel_name: Optional[str] = None,
) -> Dict[str, Path]:
    """Hàm độc lập để sinh nhanh toàn bộ báo cáo (quality_report, manifest, README) cho một thư mục run."""
    run_path = Path(run_dir).resolve()
    run_storage = RunDirectory(run_id=run_path.name, base_dir=run_path.parent)
    return run_storage.build_all_reports()
