"""Module Parser đọc file Excel và CSV xuất từ YouTube Studio tiếng Việt và tiếng Anh.

Nhiệm vụ trọng tâm (Task 3.1):
- Nhận diện chính xác các cột tiếng Việt:
  + Lượt xem / Số lượt xem (views)
  + Thời gian xem (giờ) (watch_time_hours)
  + Tỷ lệ nhấp của lượt hiển thị / Tỷ lệ nhấp vào hình thu nhỏ (%) (ctr_percent)
  + Số lượt hiển thị / Số lượt hiển thị hình thu nhỏ (impressions)
  + Thời lượng xem trung bình / Thời lượng xem trung bình (giây) (average_view_duration_seconds)
  + Nội dung / Mã video (video_id)
  + Tiêu đề video (video_title)
  + Thời gian xuất bản video (publish_date)
  + Thời lượng (duration_seconds)
  + Số người đăng ký (subscribers)
  + Ngày (date)
  + Doanh thu ước tính (estimated_revenue)
- Xử lý chuẩn Unicode tiếng Việt (NFC vs NFD combining accents như 'Thơ\u0300i gian').
- Tách dòng tổng hợp (Tổng / Total) khỏi các dòng dữ liệu video chi tiết.
- Đọc an toàn các định dạng .csv, .xlsx, và file nén .zip do YouTube Studio xuất ra.
"""

import io
import re
import zipfile
import logging
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import pandas as pd

from ytb_gpm_collector.domain.models import (
    ParsedVideoRow,
    ParsedSummaryRow,
    ParsedDailyMetricRow,
    ParsedTableData,
    StudioRawBundle,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. BẢNG TỪ ĐIỂN ÁNH XẠ CỘT (VIETNAMESE & ENGLISH COLUMN DICTIONARY)
# ==============================================================================

# Danh sách alias chuẩn cho từng trường dữ liệu canonical
COLUMN_ALIASES: Dict[str, List[str]] = {
    "video_id": [
        "nội dung",
        "nội dung video",
        "mã video",
        "id video",
        "video id",
        "content",
        "video",
        "content id",
    ],
    "video_title": [
        "tiêu đề video",
        "tiêu đề",
        "tên video",
        "video title",
        "title",
    ],
    "publish_date": [
        "thời gian xuất bản video",
        "thời gian xuất bản",
        "ngày xuất bản",
        "ngày đăng",
        "ngày tải lên",
        "thời điểm đăng",
        "video publish time",
        "publish time",
        "publish date",
        "published date",
    ],
    "duration_seconds": [
        "thời lượng",
        "thời lượng video",
        "độ dài",
        "độ dài video",
        "duration",
        "video duration",
    ],
    "views": [
        "số lượt xem",
        "lượt xem",
        "views",
        "view count",
    ],
    "watch_time_hours": [
        "thời gian xem (giờ)",
        "thời gian xem",
        "watch time (hours)",
        "watch time",
        "watch_time_hours",
    ],
    "average_view_duration_seconds": [
        "thời lượng xem trung bình",
        "thời lượng xem trung bình (giây)",
        "thời lượng xem trung bình (giờ)",
        "thời lượng trung bình",
        "thời lượng xem tb",
        "average view duration",
        "average view duration (seconds)",
        "avg view duration",
        "avd",
    ],
    "subscribers": [
        "số người đăng ký",
        "người đăng ký",
        "số người đăng ký mới",
        "subscribers",
        "subscribers gained",
        "subscribers net",
    ],
    "impressions": [
        "số lượt hiển thị hình thu nhỏ",
        "số lượt hiển thị",
        "lượt hiển thị hình thu nhỏ",
        "lượt hiển thị của hình thu nhỏ",
        "lượt hiển thị",
        "impressions",
        "thumbnail impressions",
    ],
    "ctr_percent": [
        "tỷ lệ nhấp vào hình thu nhỏ (%)",
        "tỷ lệ nhấp vào hình thu nhỏ",
        "tỷ lệ nhấp của lượt hiển thị (%)",
        "tỷ lệ nhấp của lượt hiển thị",
        "tỷ lệ nhấp (%)",
        "tỷ lệ nhấp",
        "tỷ lệ nhấp chuột",
        "impressions click-through rate (%)",
        "impressions click through rate (%)",
        "impressions ctr (%)",
        "impressions ctr",
        "ctr (%)",
        "ctr",
    ],
    "date": [
        "ngày",
        "thời gian",
        "date",
    ],
    "estimated_revenue": [
        "doanh thu ước tính (usd)",
        "doanh thu ước tính",
        "doanh thu",
        "doanh thu của bạn (usd)",
        "estimated revenue (usd)",
        "estimated revenue",
        "revenue",
    ],
    "traffic_source": [
        "nguồn lưu lượng truy cập",
        "loại nguồn lưu lượng truy cập",
        "nguồn truy cập",
        "loại nguồn",
        "traffic source",
        "traffic source type",
    ],
    "search_term": [
        "cụm từ tìm kiếm trên youtube",
        "cụm từ tìm kiếm",
        "từ khóa tìm kiếm",
        "search terms",
        "search term",
    ],
    "suggested_video": [
        "video đề xuất",
        "suggested video",
        "suggested videos",
    ],
}


def normalize_vietnamese_text(text: Any) -> str:
    """
    Chuẩn hóa chuỗi văn bản tiếng Việt:
    1. Chuyển Unicode sang chuẩn NFC (giải quyết triệt để vấn đề ký tự tổ hợp NFD ví dụ Thơ\u0300i -> Thời).
    2. Chuyển thành chữ thường.
    3. Xóa khoảng trắng thừa và ký tự điều khiển ẩn.
    """
    if text is None:
        return ""
    s = str(text)
    # NFC normalization
    s = unicodedata.normalize("NFC", s)
    s = s.strip().lower()
    # Gộp nhiều khoảng trắng liền nhau
    s = re.sub(r"\s+", " ", s)
    return s


def identify_columns(raw_columns: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Nhận diện và ánh xạ danh sách tên cột gốc sang tên trường dữ liệu chuẩn (canonical keys).
    
    Quy trình 3 bước:
    1. So khớp trực tiếp với danh sách alias sau khi chuẩn hóa NFC.
    2. So khớp sau khi loại bỏ các ký tự dấu ngoặc và đơn vị (ví dụ '%', '(giờ)', '(usd)').
    3. Phân tích ngữ nghĩa theo từ khóa đặc trưng (heuristic pattern matching).
    
    Returns:
        Tuple[Dict[str, str], List[str]]:
            - mapping: Dict mapping {tên_cột_gốc: canonical_field_name}
            - unmapped: Danh sách các cột gốc chưa nhận diện được
    """
    mapping: Dict[str, str] = {}
    unmapped: List[str] = []

    # Xây dựng bảng tra cứu alias nhanh (alias -> canonical_field)
    lookup: Dict[str, str] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            norm_alias = normalize_vietnamese_text(alias)
            lookup[norm_alias] = canon

    already_mapped_canon: set = set()

    for raw_col in raw_columns:
        norm_col = normalize_vietnamese_text(raw_col)
        if not norm_col:
            continue

        matched_canon: Optional[str] = None

        # Bước 1: So khớp trực tiếp chính xác
        if norm_col in lookup:
            matched_canon = lookup[norm_col]

        # Bước 2: Thử loại bỏ dấu ngoặc đơn và ký tự đặc biệt
        if not matched_canon:
            stripped = re.sub(r"[\(\)\[\]%]", "", norm_col).strip()
            stripped = re.sub(r"\s+", " ", stripped)
            if stripped in lookup:
                matched_canon = lookup[stripped]

        # Bước 3: Heuristic Keyword Fallback nếu chưa khớp
        if not matched_canon:
            # CTR: chứa 'tỷ lệ nhấp' hoặc 'ctr' hoặc 'click-through'
            if any(k in norm_col for k in ["tỷ lệ nhấp", "tỷ lệ click", "click-through", "ctr"]):
                matched_canon = "ctr_percent"
            # Thời lượng xem trung bình: chứa 'thời lượng xem' hoặc 'thời lượng trung bình' hoặc 'avd'
            elif ("thời lượng" in norm_col and "trung bình" in norm_col) or "thời lượng xem" in norm_col or norm_col == "avd":
                matched_canon = "average_view_duration_seconds"
            # Thời gian xem: chứa 'thời gian xem' hoặc 'watch time'
            elif "thời gian xem" in norm_col or "watch time" in norm_col:
                matched_canon = "watch_time_hours"
            # Lượt hiển thị: chứa 'hiển thị' hoặc 'impressions' (và không phải nhấp)
            elif ("hiển thị" in norm_col or "impressions" in norm_col) and "nhấp" not in norm_col:
                matched_canon = "impressions"
            # Lượt xem: chứa 'lượt xem' hoặc 'views' (và không phải 'thời gian xem' hay 'thời lượng xem')
            elif ("lượt xem" in norm_col or "views" in norm_col) and "thời" not in norm_col:
                matched_canon = "views"
            # Người đăng ký: chứa 'đăng ký' hoặc 'subscriber'
            elif "đăng ký" in norm_col or "subscriber" in norm_col:
                matched_canon = "subscribers"
            # Thời lượng video: chứa 'thời lượng' hoặc 'duration' (nhưng không phải xem trung bình)
            elif "thời lượng" in norm_col or "duration" in norm_col:
                matched_canon = "duration_seconds"
            # Xuất bản / Ngày đăng: chứa 'xuất bản' hoặc 'publish' hoặc 'ngày đăng'
            elif "xuất bản" in norm_col or "publish" in norm_col or "ngày đăng" in norm_col:
                matched_canon = "publish_date"
            # Tiêu đề: chứa 'tiêu đề' hoặc 'tên video' hoặc 'title'
            elif "tiêu đề" in norm_col or "tên video" in norm_col or "title" in norm_col:
                matched_canon = "video_title"
            # Nội dung / Video ID: 'nội dung' hoặc 'mã video' hoặc 'video id'
            elif "nội dung" in norm_col or "video id" in norm_col or norm_col == "video":
                matched_canon = "video_id"
            # Ngày: 'ngày' hoặc 'date'
            elif norm_col in ("ngày", "date"):
                matched_canon = "date"
            # Nguồn truy cập
            elif "nguồn" in norm_col and "lưu lượng" in norm_col or "traffic source" in norm_col:
                matched_canon = "traffic_source"
            # Doanh thu
            elif "doanh thu" in norm_col or "revenue" in norm_col:
                matched_canon = "estimated_revenue"

        if matched_canon:
            mapping[raw_col] = matched_canon
            already_mapped_canon.add(matched_canon)
        else:
            unmapped.append(raw_col)

    logger.debug(f"Đã nhận diện {len(mapping)} cột, {len(unmapped)} cột chưa ánh xạ: {unmapped}")
    return mapping, unmapped


# ==============================================================================
# 2. HÀM CHUYỂN ĐỔI GIÁ TRỊ (VALUE PARSERS)
# ==============================================================================

def parse_numeric(val: Any) -> Optional[float]:
    """
    Chuyển đổi an toàn giá trị bất kỳ sang kiểu float:
    - Loại bỏ dấu phẩy ngăn cách hàng nghìn (ví dụ: '3,795' -> 3795.0)
    - Loại bỏ dấu phần trăm '%' (ví dụ: '2.11%' -> 2.11)
    - Xử lý giá trị trống, NaN, None, '-', 'nan', 'null' -> trả về None
    - Hỗ trợ định dạng số châu Âu (dấu phẩy thập phân) nếu có dạng '12,34' và không có dấu chấm.
    """
    if val is None or pd.isna(val):
        return None

    if isinstance(val, (int, float)):
        if pd.isna(val):
            return None
        return float(val)

    s = str(val).strip()
    if not s or s.lower() in ("nan", "null", "none", "-", "—", "n/a", "na", ""):
        return None

    # Xóa dấu %
    s = s.rstrip("%").strip()

    # Xử lý dấu ngăn cách số:
    # Nếu có cả '.' và ',' ví dụ '1,234.56' -> bỏ dấu phẩy
    if "," in s and "." in s:
        if s.find(",") < s.find("."):
            # US format: 1,234.56
            s = s.replace(",", "")
        else:
            # EU format: 1.234,56
            s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        # Trường hợp chỉ có dấu phẩy: có thể là 3,795 (ngàn) hoặc 2,11 (thập phân)
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            # Khả năng cao là dấu thập phân (ví dụ: '2,11')
            s = s.replace(",", ".")
        else:
            # Ngăn cách hàng ngàn (ví dụ: '3,795' hoặc '1,000,000')
            s = s.replace(",", "")

    try:
        return float(s)
    except ValueError:
        return None


def parse_integer(val: Any) -> Optional[int]:
    """Chuyển đổi an toàn giá trị sang số nguyên int."""
    num = parse_numeric(val)
    if num is None:
        return None
    return int(round(num))


def parse_duration_to_seconds(val: Any) -> Optional[float]:
    """
    Chuyển đổi thời lượng sang giây:
    - Nếu là số: 4380 hoặc 4380.0 -> trả về 4380.0
    - Nếu là chuỗi thời gian 'HH:MM:SS' hoặc 'MM:SS':
      '01:13:00' -> 4380.0 giây
      '05:30' -> 330.0 giây
    """
    if val is None or pd.isna(val):
        return None

    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s or s.lower() in ("nan", "null", "none", "-"):
        return None

    # Thử parse dạng HH:MM:SS hoặc MM:SS
    if ":" in s:
        parts = s.split(":")
        try:
            parts = [float(p) for p in parts]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
        except ValueError:
            pass

    return parse_numeric(s)


def parse_date_string(val: Any) -> Optional[str]:
    """
    Chuẩn hóa chuỗi ngày tháng sang định dạng ISO YYYY-MM-DD:
    - 'Sep 14, 2026' -> '2026-09-14'
    - '2026-09-14' -> '2026-09-14'
    - '14/09/2026' -> '2026-09-14'
    - Nếu không phân tích được, giữ nguyên chuỗi sau khi strip sạch.
    """
    if val is None or pd.isna(val):
        return None

    s = str(val).strip()
    if not s or s.lower() in ("nan", "null", "none", "-"):
        return None

    # Thử parse với các định dạng phổ biến
    date_formats = [
        "%Y-%m-%d",
        "%b %d, %Y",       # Sep 14, 2026
        "%B %d, %Y",       # September 14, 2026
        "%d/%m/%Y",       # 14/09/2026
        "%m/%d/%Y",       # 09/14/2026
        "%Y/%m/%d",
        "%d-%m-%Y",
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Nếu không trúng định dạng, trả lại chuỗi sạch
    return s


def is_summary_row_indicator(val: Any) -> bool:
    """Kiểm tra xem giá trị ở cột đầu tiên có phải là nhãn của dòng Tổng (Tổng, Total) hay không."""
    if val is None or pd.isna(val):
        return False
    norm = normalize_vietnamese_text(val)
    return norm in ("tổng", "total", "tổng cộng", "tổng số", "toàn kênh", "channel total")


# ==============================================================================
# 3. PARSER CHO DỮ LIỆU BẢNG (TABLE DATA PARSER)
# ==============================================================================

def parse_table_dataframe(df: pd.DataFrame, source_file: str = "table.csv") -> ParsedTableData:
    """
    Phân tích một DataFrame đọc được từ file báo cáo dạng bảng (ví dụ: Dữ liệu trong bảng.csv hoặc sheet Excel).
    
    Quy trình:
    1. Nhận diện các cột và lập bản đồ mapping.
    2. Duyệt từng dòng:
       - Nếu dòng là dòng 'Tổng' / 'Total' -> chuyển thành ParsedSummaryRow.
       - Nếu dòng là dữ liệu video -> chuyển thành ParsedVideoRow với các trường đã ép kiểu chuẩn.
    3. Đóng gói vào ParsedTableData hoàn chỉnh.
    """
    if df is None or df.empty:
        return ParsedTableData(
            source_file=source_file,
            columns=[],
            column_mapping={},
            unmapped_columns=[],
            summary_row=None,
            video_rows=[],
            total_raw_rows=0,
        )

    raw_columns = list(df.columns)
    mapping, unmapped = identify_columns(raw_columns)

    # Đảo mapping để tra cứu nhanh từ canonical_field sang cột gốc
    canon_to_raw: Dict[str, str] = {}
    for r_col, c_field in mapping.items():
        if c_field not in canon_to_raw:
            canon_to_raw[c_field] = r_col

    summary_row_obj: Optional[ParsedSummaryRow] = None
    video_rows_list: List[ParsedVideoRow] = []

    for idx, row in df.iterrows():
        row_dict = row.to_dict()

        # Kiểm tra xem dòng này có phải là dòng Tổng (Total) không
        is_summary = False
        first_col_val = row_dict.get(raw_columns[0]) if raw_columns else None
        video_id_val = row_dict.get(canon_to_raw.get("video_id", ""))

        if is_summary_row_indicator(first_col_val) or is_summary_row_indicator(video_id_val):
            is_summary = True

        if is_summary:
            # Tạo ParsedSummaryRow
            label_str = str(video_id_val or first_col_val or "Tổng").strip()
            summary_row_obj = ParsedSummaryRow(
                label=label_str,
                views=parse_integer(row_dict.get(canon_to_raw.get("views"))),
                watch_time_hours=parse_numeric(row_dict.get(canon_to_raw.get("watch_time_hours"))),
                average_view_duration_seconds=parse_duration_to_seconds(
                    row_dict.get(canon_to_raw.get("average_view_duration_seconds"))
                ),
                subscribers=parse_integer(row_dict.get(canon_to_raw.get("subscribers"))),
                impressions=parse_integer(row_dict.get(canon_to_raw.get("impressions"))),
                ctr_percent=parse_numeric(row_dict.get(canon_to_raw.get("ctr_percent"))),
                estimated_revenue=parse_numeric(row_dict.get(canon_to_raw.get("estimated_revenue"))),
                raw_data={str(k): (None if pd.isna(v) else v) for k, v in row_dict.items()},
            )
        else:
            # Tạo ParsedVideoRow
            vid = str(video_id_val or "").strip()
            if not vid or vid.lower() in ("nan", "none", ""):
                # Nếu không có video_id ở cột định danh, kiểm tra xem có tiêu đề không
                title_test = str(row_dict.get(canon_to_raw.get("video_title"), "")).strip()
                if not title_test or title_test.lower() in ("nan", "none"):
                    continue  # Bỏ qua dòng hoàn toàn rỗng
                vid = f"unknown_row_{idx}"

            v_title = row_dict.get(canon_to_raw.get("video_title"))
            clean_title = None if pd.isna(v_title) else str(v_title).strip()

            v_pub = row_dict.get(canon_to_raw.get("publish_date"))
            clean_pub = parse_date_string(v_pub)

            video_row = ParsedVideoRow(
                video_id=vid,
                video_title=clean_title,
                publish_date=clean_pub,
                duration_seconds=parse_duration_to_seconds(
                    row_dict.get(canon_to_raw.get("duration_seconds"))
                ),
                views=parse_integer(row_dict.get(canon_to_raw.get("views"))),
                watch_time_hours=parse_numeric(row_dict.get(canon_to_raw.get("watch_time_hours"))),
                average_view_duration_seconds=parse_duration_to_seconds(
                    row_dict.get(canon_to_raw.get("average_view_duration_seconds"))
                ),
                subscribers=parse_integer(row_dict.get(canon_to_raw.get("subscribers"))),
                impressions=parse_integer(row_dict.get(canon_to_raw.get("impressions"))),
                ctr_percent=parse_numeric(row_dict.get(canon_to_raw.get("ctr_percent"))),
                estimated_revenue=parse_numeric(row_dict.get(canon_to_raw.get("estimated_revenue"))),
                raw_data={str(k): (None if pd.isna(v) else v) for k, v in row_dict.items()},
            )
            video_rows_list.append(video_row)

    return ParsedTableData(
        source_file=source_file,
        columns=raw_columns,
        column_mapping=mapping,
        unmapped_columns=unmapped,
        summary_row=summary_row_obj,
        video_rows=video_rows_list,
        total_raw_rows=len(df),
    )


# ==============================================================================
# 4. PARSER CHO DỮ LIỆU BIỂU ĐỒ & THEO NGÀY (DAILY & CHART DATA PARSER)
# ==============================================================================

def parse_daily_dataframe(df: pd.DataFrame) -> List[ParsedDailyMetricRow]:
    """
    Phân tích cú pháp DataFrame từ file Dữ liệu biểu đồ.csv hoặc Tổng số.csv:
    - Chuẩn hóa ngày về YYYY-MM-DD.
    - Ép kiểu video_id, views, watch_time_hours nếu có.
    """
    if df is None or df.empty:
        return []

    raw_columns = list(df.columns)
    mapping, _ = identify_columns(raw_columns)

    canon_to_raw: Dict[str, str] = {}
    for r_col, c_field in mapping.items():
        if c_field not in canon_to_raw:
            canon_to_raw[c_field] = r_col

    results: List[ParsedDailyMetricRow] = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()

        date_val = row_dict.get(canon_to_raw.get("date"))
        clean_date = parse_date_string(date_val)
        if not clean_date:
            continue

        vid_val = row_dict.get(canon_to_raw.get("video_id"))
        clean_vid = None
        if vid_val is not None and not pd.isna(vid_val):
            s = str(vid_val).strip()
            if s and s.lower() not in ("nan", "none"):
                clean_vid = s

        title_val = row_dict.get(canon_to_raw.get("video_title"))
        clean_title = None
        if title_val is not None and not pd.isna(title_val):
            s = str(title_val).strip()
            if s and s.lower() not in ("nan", "none"):
                clean_title = s

        item = ParsedDailyMetricRow(
            date=clean_date,
            video_id=clean_vid,
            video_title=clean_title,
            views=parse_integer(row_dict.get(canon_to_raw.get("views"))),
            watch_time_hours=parse_numeric(row_dict.get(canon_to_raw.get("watch_time_hours"))),
            duration_seconds=parse_duration_to_seconds(row_dict.get(canon_to_raw.get("duration_seconds"))),
            raw_data={str(k): (None if pd.isna(v) else v) for k, v in row_dict.items()},
        )
        results.append(item)

    return results


# ==============================================================================
# 5. CÁC HÀM ĐỌC FILE CẤP ĐỘ CAO (HIGH-LEVEL FILE READERS)
# ==============================================================================

def read_csv_file(
    file_path_or_buffer: Union[str, Path, io.BytesIO, io.StringIO],
    encoding: Optional[str] = None,
) -> pd.DataFrame:
    """
    Đọc file CSV an toàn với cơ chế tự động thử nhiều bảng mã (encodings):
    Ưu tiên 'utf-8-sig' (xử lý tốt cả file có hoặc không có UTF-8 BOM), sau đó 'utf-8', 'cp1252', 'latin1'.
    """
    encodings_to_try = [encoding] if encoding else ["utf-8-sig", "utf-8", "cp1252", "latin1"]

    last_error = None
    for enc in encodings_to_try:
        if not enc:
            continue
        try:
            if isinstance(file_path_or_buffer, (io.BytesIO, io.StringIO)):
                file_path_or_buffer.seek(0)
            df = pd.read_csv(file_path_or_buffer, encoding=enc)
            return df
        except UnicodeDecodeError as ue:
            last_error = ue
            continue
        except Exception as e:
            last_error = e
            break

    raise ValueError(f"Không thể đọc file CSV bằng bất kỳ bảng mã nào: {last_error}")


def read_excel_file(
    file_path_or_buffer: Union[str, Path, io.BytesIO],
    sheet_name: Union[str, int] = 0,
) -> pd.DataFrame:
    """Đọc file Excel (.xlsx / .xls) bằng pandas và engine openpyxl."""
    if isinstance(file_path_or_buffer, io.BytesIO):
        file_path_or_buffer.seek(0)
    return pd.read_excel(file_path_or_buffer, sheet_name=sheet_name, engine="openpyxl")


def read_table_file(file_path: Union[str, Path]) -> ParsedTableData:
    """
    Tự động phân biệt định dạng file (.csv hoặc .xlsx/.xls) để phân tích bảng số liệu.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file cần đọc: {path}")

    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = read_excel_file(path)
    elif suffix == ".csv":
        df = read_csv_file(path)
    else:
        raise ValueError(f"Định dạng file không được hỗ trợ ({suffix}). Chỉ hỗ trợ .csv và .xlsx.")

    return parse_table_dataframe(df, source_file=path.name)


def read_daily_metrics_file(file_path: Union[str, Path]) -> List[ParsedDailyMetricRow]:
    """Đọc và parse file số liệu theo ngày (Dữ liệu biểu đồ hoặc Tổng số)."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")

    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = read_excel_file(path)
    else:
        df = read_csv_file(path)

    return parse_daily_dataframe(df)


def read_export_zip(zip_path: Union[str, Path]) -> StudioRawBundle:
    """
    Đọc trực tiếp từ file nén .zip do YouTube Studio xuất ra mà không cần giải nén ra ổ đĩa:
    - Tìm và parse file bảng: 'Dữ liệu trong bảng.csv' hoặc file tương đương.
    - Tìm và parse file biểu đồ: 'Dữ liệu biểu đồ.csv'.
    - Tìm và parse file tổng số: 'Tổng số.csv'.
    """
    z_path = Path(zip_path)
    if not z_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file zip: {z_path}")

    bundle = StudioRawBundle(source_path=str(z_path))

    with zipfile.ZipFile(z_path, "r") as zf:
        namelist = zf.namelist()
        bundle.discovered_files = list(namelist)

        # Phân loại các file bên trong zip
        for name in namelist:
            norm_name = normalize_vietnamese_text(name)
            file_bytes = zf.read(name)
            bio = io.BytesIO(file_bytes)

            # 1. Bảng số liệu chính (Table data)
            if "trong bàng" in norm_name or "trong bảng" in norm_name or "table" in norm_name:
                df = read_csv_file(bio)
                bundle.table_data = parse_table_dataframe(df, source_file=name)

            # 2. Dữ liệu biểu đồ (Chart data)
            elif "biểu đồ" in norm_name or "biêu đô" in norm_name or "chart" in norm_name:
                df = read_csv_file(bio)
                bundle.daily_chart_data = parse_daily_dataframe(df)

            # 3. Dữ liệu tổng số (Totals)
            elif "tổng số" in norm_name or "tong so" in norm_name or "totals" in norm_name:
                df = read_csv_file(bio)
                bundle.daily_totals_data = parse_daily_dataframe(df)

    logger.info(
        f"Đã đọc file zip '{z_path.name}': "
        f"{len(bundle.table_data.video_rows) if bundle.table_data else 0} video, "
        f"{len(bundle.daily_chart_data)} dòng biểu đồ, "
        f"{len(bundle.daily_totals_data)} dòng tổng ngày."
    )
    return bundle


def read_export_bundle(path_or_dir: Union[str, Path]) -> StudioRawBundle:
    """
    Đọc toàn diện một gói xuất dữ liệu (Export Bundle):
    - Tham số có thể là:
      1. Một file .zip xuất từ Studio.
      2. Một thư mục chứa các file raw (ví dụ: runs/<run_id>/raw/).
      3. Một file CSV/XLSX đơn lẻ.
    """
    target_path = Path(path_or_dir)
    if not target_path.exists():
        raise FileNotFoundError(f"Đường dẫn không tồn tại: {target_path}")

    # Trường hợp 1: Là file zip
    if target_path.is_file() and target_path.suffix.lower() == ".zip":
        return read_export_zip(target_path)

    # Trường hợp 2: Là file đơn lẻ (.csv hoặc .xlsx)
    if target_path.is_file():
        table_data = read_table_file(target_path)
        return StudioRawBundle(
            source_path=str(target_path),
            table_data=table_data,
            discovered_files=[target_path.name],
        )

    # Trường hợp 3: Là thư mục raw/
    bundle = StudioRawBundle(source_path=str(target_path))
    files = sorted(list(target_path.glob("*")))
    bundle.discovered_files = [f.name for f in files]

    # Kiểm tra xem có file CSV đã giải nén sẵn không
    for f in files:
        if not f.is_file():
            continue
        norm_name = normalize_vietnamese_text(f.name)

        if "trong bàng" in norm_name or "trong bảng" in norm_name or "table" in norm_name:
            if not bundle.table_data:
                bundle.table_data = read_table_file(f)
        elif "biểu đồ" in norm_name or "biêu đô" in norm_name or "chart" in norm_name:
            if not bundle.daily_chart_data:
                bundle.daily_chart_data = read_daily_metrics_file(f)
        elif "tổng số" in norm_name or "tong so" in norm_name or "totals" in norm_name:
            if not bundle.daily_totals_data:
                bundle.daily_totals_data = read_daily_metrics_file(f)

    # Nếu trong thư mục chưa có CSV lẻ nhưng có file .zip, đọc từ zip
    if not bundle.table_data:
        zip_files = [f for f in files if f.suffix.lower() == ".zip"]
        if zip_files:
            return read_export_zip(zip_files[0])

    logger.info(
        f"Đã đọc thư mục bundle '{target_path.name}': "
        f"{len(bundle.table_data.video_rows) if bundle.table_data else 0} video, "
        f"{len(bundle.daily_chart_data)} dòng biểu đồ, "
        f"{len(bundle.daily_totals_data)} dòng tổng ngày."
    )
    return bundle
