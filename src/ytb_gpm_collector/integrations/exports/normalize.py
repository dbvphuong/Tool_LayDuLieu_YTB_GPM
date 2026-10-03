"""Module Chuẩn hóa dữ liệu sau khi đọc từ file gốc YouTube Studio (Task 3.2).

Nhiệm vụ:
1. Chuyển đổi về cấu trúc số chuẩn, xử lý dữ liệu trống (zero, not_available, failed).
2. Không suy diễn hay bịa số: nếu YouTube không có số thì ghi rõ null và lý do (status_reason).
3. Xác định chính xác khoảng thời gian (period_start, period_end, period_kind).
4. Xuất các file sạch và chuẩn hóa vào thư mục data/:
   - videos.csv (mỗi dòng một video, dễ mở xem bằng Excel, mã hóa utf-8-sig)
   - videos.jsonl (mỗi dòng một JSON object chuẩn cho AI đọc, mã hóa utf-8)
   - traffic_sources.csv (nguồn lưu lượng truy cập)
   - daily_metrics.csv (số liệu chi tiết theo ngày)
   - channel.json (chỉ số tổng quan toàn kênh kèm nguồn và khoảng ngày)
"""

import csv
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from ytb_gpm_collector.domain.models import (
    ParsedVideoRow,
    ParsedSummaryRow,
    ParsedDailyMetricRow,
    ParsedTableData,
    StudioRawBundle,
    NormalizedVideoRecord,
    NormalizedTrafficSourceRecord,
    NormalizedChannelOverview,
    NormalizationResult,
)
from ytb_gpm_collector.integrations.exports.readers import (
    read_export_bundle, read_csv_file, read_daily_metrics_file,
    identify_columns, parse_integer, parse_numeric, parse_duration_to_seconds,
    normalize_vietnamese_text, is_summary_row_indicator,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. HÀM XÁC ĐỊNH KHOẢNG THỜI GIAN (PERIOD RESOLUTION)
# ==============================================================================

def extract_period_dates(
    bundle: StudioRawBundle,
    manifest_data: Optional[Dict[str, Any]] = None,
    default_period_days: int = 28,
) -> Tuple[str, str, str]:
    """
    Xác định chính xác ngày bắt đầu (period_start), ngày kết thúc (period_end)
    và loại khoảng thời gian (period_kind).
    
    Thứ tự ưu tiên:
    1. Chuỗi ngày dạng YYYY-MM-DD_YYYY-MM-DD trong tên file nén hoặc file raw.
       (Ví dụ: 'Nội dung 2026-09-04_2026-10-02 Misteri dello Spaziotempo.zip')
    2. Min và Max date từ dữ liệu theo ngày (daily_totals_data hoặc daily_chart_data).
    3. Cấu hình trong manifest.json (nếu có custom_date_from, custom_date_to).
    4. Dự phòng dựa trên ngày hiện tại lùi lại N ngày.
    """
    date_regex = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})")

    # Dữ liệu ngày thực tế quyết định mốc cuối; tên ZIP có thể ghi mốc trên loại trừ.
    daily_dates = [d.date for d in bundle.daily_totals_data + bundle.daily_chart_data if d.date]
    actual_range = (min(daily_dates), max(daily_dates)) if daily_dates else None

    # Cách 1: Tìm trong discovered_files hoặc tên source_path
    candidate_names = [Path(bundle.source_path).name] + bundle.discovered_files
    for name in candidate_names:
        match = date_regex.search(name)
        if match:
            start_d, end_d = match.group(1), match.group(2)
            logger.info(f"Đã phát hiện khoảng thời gian từ tên file '{name}': {start_d} đến {end_d}")
            if actual_range and actual_range[0] == start_d and actual_range[1] != end_d:
                logger.warning("Tên file kết thúc %s nhưng dữ liệu ngày kết thúc %s", end_d, actual_range[1])
                end_d = actual_range[1]
            return start_d, end_d, "fixed_calendar_range"

    # Cách 2: Tìm min/max từ dữ liệu daily
    daily_dates = []
    if bundle.daily_totals_data:
        daily_dates.extend([d.date for d in bundle.daily_totals_data if d.date])
    if bundle.daily_chart_data:
        daily_dates.extend([d.date for d in bundle.daily_chart_data if d.date])

    if daily_dates:
        sorted_dates = sorted(set(daily_dates))
        start_d, end_d = sorted_dates[0], sorted_dates[-1]
        logger.info(f"Đã xác định khoảng thời gian từ dữ liệu theo ngày: {start_d} đến {end_d}")
        return start_d, end_d, "fixed_calendar_range"

    # Cách 3: Kiểm tra manifest_data
    if manifest_data:
        if manifest_data.get("period_start") and manifest_data.get("period_end"):
            return manifest_data["period_start"], manifest_data["period_end"], manifest_data.get("period", "28_days")
        period_str = str(manifest_data.get("period", ""))
        match = date_regex.search(period_str)
        if match:
            return match.group(1), match.group(2), "fixed_calendar_range"

    # Cách 4: Fallback
    today = datetime.now()
    end_d = today.strftime("%Y-%m-%d")
    # Lùi lại 28 ngày
    start_d = (today - timedelta(days=default_period_days)).strftime("%Y-%m-%d")
    return start_d, end_d, f"{default_period_days}_days"


# ==============================================================================
# 2. HÀM XÁC ĐỊNH TRẠNG THÁI SỐ LIỆU (STATUS & REASON)
# ==============================================================================

def evaluate_video_status(video_row: ParsedVideoRow) -> Tuple[str, Optional[str]]:
    """
    Xác định trạng thái số liệu của một video:
    - 'ok': Có số liệu lượt xem hoặc hiển thị hợp lệ (> 0).
    - 'zero': Video có 0 lượt xem và 0 lượt hiển thị (video mới đăng hoặc không có tiếp cận).
    - 'not_available': Video không có bất kỳ số liệu nào từ Studio (toàn bộ chỉ số đều null).
    - 'failed': Dòng dữ liệu bị lỗi cú pháp hoặc thiếu định danh video.
    """
    vid = video_row.video_id
    if not vid or vid.startswith("unknown_row_"):
        return "failed", "missing_or_invalid_video_id"

    views = video_row.views
    imp = video_row.impressions
    watch_time = video_row.watch_time_hours

    # Nếu tất cả các chỉ số chính đều là None
    if views is None and imp is None and watch_time is None:
        return "not_available", "metrics_not_reported_by_youtube"

    # Nếu lượt xem là 0 và hiển thị là 0 (hoặc None)
    if views == 0 and (imp == 0 or imp is None):
        return "zero", "zero_views_and_impressions"

    # Trường hợp bình thường có số liệu
    return "ok", None


# ==============================================================================
# 3. CHUẨN HÓA DANH SÁCH BẢN GHI (RECORD NORMALIZATION)
# ==============================================================================

def normalize_video_records(
    table_data: ParsedTableData,
    channel_id: str,
    period_start: str,
    period_end: str,
    period_kind: str = "fixed_calendar_range",
    source_file_rel: str = "raw/table.csv",
) -> List[NormalizedVideoRecord]:
    """
    Chuyển đổi các dòng ParsedVideoRow sang danh sách NormalizedVideoRecord chuẩn.
    
    Tuân thủ nguyên tắc:
    - Không tự suy diễn hay bịa số (ví dụ AVD nếu Studio không xuất thì giữ None).
    - Ép kiểu chuẩn: views (int), impressions (int), subscribers (int), watch_time_hours (float)...
    - Gắn cờ status và status_reason cho từng dòng.
    """
    normalized_list: List[NormalizedVideoRecord] = []

    for v_row in table_data.video_rows:
        status, reason = evaluate_video_status(v_row)

        record = NormalizedVideoRecord(
            channel_id=channel_id,
            video_id=v_row.video_id,
            video_title=v_row.video_title,
            publish_date=v_row.publish_date,
            duration_seconds=v_row.duration_seconds,
            period_start=period_start,
            period_end=period_end,
            period_kind=period_kind,
            views=v_row.views,
            watch_time_hours=v_row.watch_time_hours,
            average_view_duration_seconds=v_row.average_view_duration_seconds,
            impressions=v_row.impressions,
            ctr_percent=v_row.ctr_percent,
            subscribers=v_row.subscribers,
            estimated_revenue=v_row.estimated_revenue,
            status=status,
            status_reason=reason,
            source_file=source_file_rel,
        )
        normalized_list.append(record)

    return normalized_list


def create_channel_overview(
    table_data: Optional[ParsedTableData],
    channel_id: str,
    channel_name: Optional[str],
    period_start: str,
    period_end: str,
    period_kind: str,
    source_file_rel: str,
) -> NormalizedChannelOverview:
    """Tạo bản ghi tổng quan toàn kênh cho data/channel.json."""
    summary = table_data.summary_row if table_data else None

    return NormalizedChannelOverview(
        channel_id=channel_id,
        channel_name=channel_name,
        period_start=period_start,
        period_end=period_end,
        period_kind=period_kind,
        total_views=summary.views if summary else None,
        total_watch_time_hours=summary.watch_time_hours if summary else None,
        total_impressions=summary.impressions if summary else None,
        average_ctr_percent=summary.ctr_percent if summary else None,
        total_subscribers=summary.subscribers if summary else None,
        video_count=len(table_data.video_rows) if table_data else 0,
        source_file=source_file_rel,
        normalized_at=datetime.now().isoformat(),
    )


# ==============================================================================
# 4. GHI DỮ LIỆU CHUẨN VÀO THƯ MỤC DATA/ (EXPORTERS)
# ==============================================================================

def write_videos_csv(records: List[NormalizedVideoRecord], output_path: Path) -> Path:
    """
    Ghi danh sách video ra file CSV chuẩn hóa (videos.csv):
    - Mã hóa 'utf-8-sig' có BOM để mở xem tiếng Việt hoàn hảo trên Excel.
    - Dữ liệu trống ghi thành chuỗi rỗng "".
    """
    fieldnames = [
        "channel_id",
        "video_id",
        "video_title",
        "publish_date",
        "duration_seconds",
        "period_start",
        "period_end",
        "period_kind",
        "views",
        "watch_time_hours",
        "average_view_duration_seconds",
        "impressions",
        "ctr_percent",
        "subscribers",
        "estimated_revenue",
        "status",
        "status_reason",
        "source_file",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            row_dict = rec.model_dump()
            clean_row = {
                k: ("" if row_dict.get(k) is None else row_dict.get(k))
                for k in fieldnames
            }
            writer.writerow(clean_row)

    logger.info(f"Đã ghi {len(records)} dòng vào {output_path}")
    return output_path


def write_videos_jsonl(records: List[NormalizedVideoRecord], output_path: Path) -> Path:
    """
    Ghi danh sách video ra file JSONL (videos.jsonl):
    - Mỗi dòng là một JSON object độc lập, không thụt đầu dòng.
    - Giá trị thiếu được giữ nguyên là null cho AI parser đọc.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.model_dump(), ensure_ascii=False) + "\n")

    logger.info(f"Đã ghi {len(records)} dòng JSONL vào {output_path}")
    return output_path


def write_traffic_sources_csv(
    records: List[NormalizedTrafficSourceRecord],
    output_path: Path,
) -> Path:
    """
    Ghi dữ liệu nguồn lưu lượng ra traffic_sources.csv:
    - Nếu có dữ liệu, ghi đầy đủ.
    - Nếu chưa có dữ liệu nguồn cho đợt chạy này, ghi header chuẩn để đảm bảo tính nhất quán của gói dữ liệu.
    """
    fieldnames = [
        "channel_id",
        "video_id",
        "traffic_source",
        "views",
        "watch_time_hours",
        "average_view_duration_seconds",
        "impressions",
        "ctr_percent",
        "period_start",
        "period_end",
        "status",
        "source_file",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            row_dict = rec.model_dump()
            clean_row = {
                k: ("" if row_dict.get(k) is None else row_dict.get(k))
                for k in fieldnames
            }
            writer.writerow(clean_row)

    logger.info(f"Đã ghi file nguồn lưu lượng vào {output_path}")
    return output_path


def write_daily_metrics_csv(
    daily_rows: List[ParsedDailyMetricRow],
    channel_id: str,
    source_file_rel: str,
    output_path: Path,
    source_file_by_video: Optional[Dict[str, str]] = None,
) -> Path:
    """Ghi dữ liệu số liệu theo ngày (daily_metrics.csv)."""
    fieldnames = [
        "date",
        "channel_id",
        "video_id",
        "video_title",
        "views",
        "watch_time_hours",
        "duration_seconds",
        "source_file",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in daily_rows:
            clean_row = {
                "date": row.date,
                "channel_id": channel_id,
                "video_id": "" if row.video_id is None else row.video_id,
                "video_title": "" if row.video_title is None else row.video_title,
                "views": "" if row.views is None else row.views,
                "watch_time_hours": "" if row.watch_time_hours is None else row.watch_time_hours,
                "duration_seconds": "" if row.duration_seconds is None else row.duration_seconds,
                "source_file": (source_file_by_video or {}).get(row.video_id or "", source_file_rel),
            }
            writer.writerow(clean_row)

    logger.info(f"Đã ghi {len(daily_rows)} dòng số liệu ngày vào {output_path}")
    return output_path


def read_traffic_source_records(raw_dir: Path, channel_id: str, period_start: str, period_end: str) -> List[NormalizedTrafficSourceRecord]:
    """Đọc bảng nguồn truy cập riêng; không nhầm bảng video với bảng nguồn."""
    records: List[NormalizedTrafficSourceRecord] = []
    folders = [(raw_dir / "traffic_sources", None)]
    video_root = raw_dir / "video_traffic"
    if video_root.exists():
        folders.extend((folder, folder.name) for folder in sorted(video_root.iterdir()) if folder.is_dir())
    for source_dir, video_id in folders:
        if not source_dir.exists():
            continue
        for path in source_dir.glob("*.csv"):
            if "bảng" not in normalize_vietnamese_text(path.name) and "table" not in path.name.lower():
                continue
            df = read_csv_file(path)
            mapping, _ = identify_columns(list(df.columns))
            reverse = {canonical: raw for raw, canonical in mapping.items()}
            source_col = reverse.get("traffic_source")
            if not source_col:
                continue
            for _, row in df.iterrows():
                label = row.get(source_col)
                if label is None or is_summary_row_indicator(label) or str(label).strip().lower() in ("", "nan"):
                    continue
                records.append(NormalizedTrafficSourceRecord(
                    channel_id=channel_id,
                    video_id=video_id,
                    traffic_source=str(label).strip(),
                    views=parse_integer(row.get(reverse.get("views"))),
                    watch_time_hours=parse_numeric(row.get(reverse.get("watch_time_hours"))),
                    average_view_duration_seconds=parse_duration_to_seconds(row.get(reverse.get("average_view_duration_seconds"))),
                    impressions=parse_integer(row.get(reverse.get("impressions"))),
                    ctr_percent=parse_numeric(row.get(reverse.get("ctr_percent"))),
                    period_start=period_start,
                    period_end=period_end,
                    source_file=f"{source_dir.relative_to(raw_dir.parent).as_posix()}/{path.name}",
                ))
    return records


def write_channel_json(overview: NormalizedChannelOverview, output_path: Path) -> Path:
    """Ghi file tổng quan chỉ số kênh (channel.json)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(overview.model_dump(), f, ensure_ascii=False, indent=2)

    logger.info(f"Đã ghi tổng quan kênh vào {output_path}")
    return output_path


# ==============================================================================
# 5. QUY TRÌNH CHUẨN HÓA TRỌN GÓI CHO MỘT RUN (PIPELINE)
# ==============================================================================

def normalize_run_directory(run_dir_path: Union[str, Path]) -> NormalizationResult:
    """
    Quy trình chuẩn hóa hoàn chỉnh cho một thư mục đợt chạy (runs/<run_id>/):
    1. Đọc manifest.json (nếu có) để lấy channel_id, channel_name, period.
    2. Đọc gói dữ liệu thô trong raw/ qua read_export_bundle().
    3. Xác định ngày bắt đầu và kết thúc (period_start, period_end).
    4. Chuẩn hóa video records, channel overview, daily metrics.
    5. Xuất các file sạch vào thư mục data/:
       - data/videos.csv
       - data/videos.jsonl
       - data/traffic_sources.csv
       - data/daily_metrics.csv
       - data/channel.json
    6. Cập nhật trạng thái 'normalized' vào manifest.json.
    7. Trả về NormalizationResult.
    """
    run_dir = Path(run_dir_path).resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"Thư mục đợt chạy không tồn tại: {run_dir}")

    raw_dir = run_dir / "raw"
    data_dir = run_dir / "data"
    manifest_file = run_dir / "manifest.json"

    logger.info(f"=== Bắt đầu chuẩn hóa dữ liệu cho đợt chạy: {run_dir.name} ===")

    # 1. Đọc manifest.json nếu có
    manifest_data: Dict[str, Any] = {}
    if manifest_file.exists():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as me:
            logger.warning(f"Không thể đọc manifest.json: {me}")

    channel_id = manifest_data.get("channel_id") or "unknown_channel"
    channel_name = manifest_data.get("channel_name")

    # 2. Đọc gói dữ liệu thô trong raw/
    if not raw_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục raw/ trong: {run_dir}")

    bundle = read_export_bundle(raw_dir)

    # 3. Xác định khoảng thời gian
    period_start, period_end, period_kind = extract_period_dates(bundle, manifest_data)

    # Xác định đường dẫn tương đối của file nguồn
    source_file_rel = "raw/table.csv"
    if bundle.table_data and bundle.table_data.source_file:
        source_file_rel = f"raw/{bundle.table_data.source_file}"
    elif manifest_data.get("raw_file"):
        source_file_rel = str(manifest_data["raw_file"])

    generated_files: List[str] = []

    # 4. Chuẩn hóa danh sách video
    video_records: List[NormalizedVideoRecord] = []
    if bundle.table_data:
        video_records = normalize_video_records(
            table_data=bundle.table_data,
            channel_id=channel_id,
            period_start=period_start,
            period_end=period_end,
            period_kind=period_kind,
            source_file_rel=source_file_rel,
        )

    # Ghi videos.csv
    videos_csv_path = data_dir / "videos.csv"
    write_videos_csv(video_records, videos_csv_path)
    generated_files.append(str(videos_csv_path.relative_to(run_dir)))

    # Ghi videos.jsonl
    videos_jsonl_path = data_dir / "videos.jsonl"
    write_videos_jsonl(video_records, videos_jsonl_path)
    generated_files.append(str(videos_jsonl_path.relative_to(run_dir)))

    # Bảng nguồn truy cập là một báo cáo riêng, không nằm trong ZIP bảng video.
    traffic_sources_path = data_dir / "traffic_sources.csv"
    traffic_records = read_traffic_source_records(raw_dir, channel_id, period_start, period_end)
    write_traffic_sources_csv(traffic_records, traffic_sources_path)
    generated_files.append(str(traffic_sources_path.relative_to(run_dir)))

    # Giữ riêng chuỗi video và chuỗi tổng kênh. Bổ sung video thiếu từ các ZIP riêng.
    daily_by_key = {(row.video_id, row.date): row for row in bundle.daily_chart_data if row.video_id}
    daily_sources: Dict[str, str] = {}
    video_daily_dir = raw_dir / "video_daily"
    if video_daily_dir.exists():
        for folder in sorted(video_daily_dir.iterdir()):
            if not folder.is_dir():
                continue
            try:
                extra = read_export_bundle(folder)
                items = extra.daily_totals_data or extra.daily_chart_data
                if not items:
                    for csv_path in folder.glob("*.csv"):
                        candidate = read_daily_metrics_file(csv_path)
                        if candidate:
                            items = candidate
                            break
                for row in items:
                    video_id = row.video_id or folder.name
                    if video_id != folder.name:
                        continue
                    daily_by_key.setdefault((video_id, row.date), row.model_copy(update={"video_id": video_id}))
                    source_name = next((name for name in extra.discovered_files if name.lower().endswith(".zip")), None)
                    daily_sources[video_id] = f"raw/video_daily/{video_id}/{source_name}" if source_name else f"raw/video_daily/{video_id}"
            except Exception as exc:
                logger.warning("Không đọc được dữ liệu ngày của %s: %s", folder.name, exc)
    daily_items = sorted(daily_by_key.values(), key=lambda row: (row.date, row.video_id or ""))
    if daily_items:
        chart_name = next((name for name in bundle.discovered_files if "biểu đồ" in normalize_vietnamese_text(name)), None)
        daily_csv_path = data_dir / "daily_metrics.csv"
        write_daily_metrics_csv(
            daily_rows=daily_items,
            channel_id=channel_id,
            source_file_rel=f"raw/{chart_name}" if chart_name else source_file_rel,
            output_path=daily_csv_path,
            source_file_by_video=daily_sources,
        )
        generated_files.append(str(daily_csv_path.relative_to(run_dir)))

    if bundle.daily_totals_data:
        daily_channel_path = data_dir / "daily_channel_metrics.csv"
        write_daily_metrics_csv(
            daily_rows=bundle.daily_totals_data,
            channel_id=channel_id,
            source_file_rel="raw/Tổng số.csv",
            output_path=daily_channel_path,
        )
        generated_files.append(str(daily_channel_path.relative_to(run_dir)))

    # Ghi channel.json
    overview = create_channel_overview(
        table_data=bundle.table_data,
        channel_id=channel_id,
        channel_name=channel_name,
        period_start=period_start,
        period_end=period_end,
        period_kind=period_kind,
        source_file_rel=source_file_rel,
    )
    channel_json_path = data_dir / "channel.json"
    write_channel_json(overview, channel_json_path)
    generated_files.append(str(channel_json_path.relative_to(run_dir)))

    # 5. Cập nhật manifest.json và tự động sinh toàn bộ báo cáo (Task 3.3)
    if manifest_data:
        manifest_data["status"] = "normalized"
        manifest_data["period_start"] = period_start
        manifest_data["period_end"] = period_end
        manifest_data["video_count"] = len(video_records)
        manifest_data["normalized_files"] = generated_files
        manifest_data["normalized_at"] = datetime.now().isoformat()
        try:
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Đã cập nhật manifest.json sơ bộ tại {manifest_file}")
        except Exception as me:
            logger.warning(f"Không thể cập nhật manifest.json: {me}")

    # Sinh README.md, manifest.json đầy đủ và quality_report.json
    try:
        from ytb_gpm_collector.integrations.storage.runs import build_run_reports
        build_run_reports(run_dir)
        logger.info(f"Đã tự động sinh README.md, manifest.json và quality_report.json cho {run_dir}")
    except Exception as re_err:
        logger.warning(f"Lỗi khi tự động sinh báo cáo cho {run_dir}: {re_err}")


    res = NormalizationResult(
        success=True,
        run_id=run_dir.name,
        channel_id=channel_id,
        period_start=period_start,
        period_end=period_end,
        videos_count=len(video_records),
        daily_metrics_count=len(daily_items),
        traffic_sources_count=len(traffic_records),
        generated_files=generated_files,
        message=f"Đã chuẩn hóa thành công {len(video_records)} video vào thư mục data/",
    )

    logger.info(f"=== Hoàn tất chuẩn hóa: {res.message} ===")
    return res


# Semantic alias
normalize_run_bundle = normalize_run_directory

