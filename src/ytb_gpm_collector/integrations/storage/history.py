"""Quản lý cơ sở dữ liệu SQLite cục bộ (state/app_state.db).

Lưu trữ:
1. Trạng thái phiên làm việc trước (Profile đã chọn, số lượng video, khoảng ngày, số luồng...).
2. Cache kênh YouTube & đăng nhập của từng Profile (để mở lên là thấy ngay kênh nào).
3. Lịch sử các đợt chạy (Run History) để dễ dàng tra cứu, mở thư mục và chạy lại.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from ytb_gpm_collector.domain.models import (
    AppSessionState,
    ChannelCache,
    RunHistoryRecord,
    GpmProfile,
)


class LocalStorage:
    """Quản lý SQLite Database cục bộ lưu trữ phiên làm việc và lịch sử."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # Mặc định lưu tại state/app_state.db
            base_dir = Path("state")
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = base_dir / "app_state.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """Khởi tạo cấu trúc các bảng nếu chưa có."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Bảng lưu trạng thái phiên làm việc (Key-Value)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Bảng cache thông tin kênh YouTube cho từng Profile
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_cache (
                    profile_id TEXT PRIMARY KEY,
                    channel_id TEXT,
                    channel_name TEXT,
                    is_authenticated INTEGER DEFAULT 0,
                    last_collected_at TEXT,
                    notes TEXT,
                    updated_at TEXT NOT NULL
                );
            """)

            # 3. Bảng lịch sử các đợt chạy
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS run_history (
                    run_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    channel_id TEXT,
                    channel_name TEXT,
                    period TEXT NOT NULL,
                    video_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error_message TEXT
                );
            """)
            conn.commit()

    # =========================================================================
    # 1. Quản lý trạng thái phiên làm việc (Session State)
    # =========================================================================

    def save_setting(self, key: str, value: Any) -> None:
        """Lưu một giá trị cài đặt dạng key-value."""
        now = datetime.now().isoformat()
        val_str = json.dumps(value, ensure_ascii=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at;
            """, (key, val_str, now))
            conn.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Lấy một giá trị cài đặt theo key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = ?;", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except Exception:
                    return row["value"]
        return default

    def save_session_state(self, state: AppSessionState):
        """Lưu lại trạng thái lựa chọn gần nhất của người dùng."""
        now = datetime.now().isoformat()
        state_dict = state.model_dump()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for key, val in state_dict.items():
                val_str = json.dumps(val, ensure_ascii=False)
                cursor.execute("""
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at;
                """, (key, val_str, now))
            conn.commit()

    def load_session_state(self) -> AppSessionState:
        """Tải lại trạng thái phiên trước. Nếu chưa có, trả về mặc định."""
        defaults = AppSessionState().model_dump()
        loaded = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM app_settings;")
            for row in cursor.fetchall():
                k = row["key"]
                v_str = row["value"]
                try:
                    loaded[k] = json.loads(v_str)
                except Exception:
                    loaded[k] = v_str

        # Gộp với giá trị mặc định nếu thiếu trường
        merged = {**defaults, **loaded}
        return AppSessionState(**merged)

    # =========================================================================
    # 2. Quản lý Cache kênh YouTube & Trạng thái Đăng nhập
    # =========================================================================

    def save_channel_cache(self, cache: ChannelCache):
        """Lưu hoặc cập nhật thông tin kênh của profile."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO channel_cache (
                    profile_id, channel_id, channel_name, is_authenticated,
                    last_collected_at, notes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    channel_name = excluded.channel_name,
                    is_authenticated = excluded.is_authenticated,
                    last_collected_at = COALESCE(excluded.last_collected_at, channel_cache.last_collected_at),
                    notes = COALESCE(excluded.notes, channel_cache.notes),
                    updated_at = excluded.updated_at;
            """, (
                cache.profile_id,
                cache.channel_id,
                cache.channel_name,
                1 if cache.is_authenticated else 0,
                cache.last_collected_at,
                cache.notes,
                now,
            ))
            conn.commit()

    def get_channel_cache(self, profile_id: str) -> Optional[ChannelCache]:
        """Lấy thông tin kênh đã lưu của một profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channel_cache WHERE profile_id = ?;", (profile_id,))
            row = cursor.fetchone()
            if row:
                return ChannelCache(
                    profile_id=row["profile_id"],
                    channel_id=row["channel_id"],
                    channel_name=row["channel_name"],
                    is_authenticated=bool(row["is_authenticated"]),
                    last_collected_at=row["last_collected_at"],
                    notes=row["notes"],
                )
        return None

    def get_all_channel_caches(self) -> Dict[str, ChannelCache]:
        """Lấy toàn bộ cache kênh dưới dạng dict theo profile_id."""
        result = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channel_cache;")
            for row in cursor.fetchall():
                c = ChannelCache(
                    profile_id=row["profile_id"],
                    channel_id=row["channel_id"],
                    channel_name=row["channel_name"],
                    is_authenticated=bool(row["is_authenticated"]),
                    last_collected_at=row["last_collected_at"],
                    notes=row["notes"],
                )
                result[c.profile_id] = c
        return result

    def enrich_profiles_with_cache(self, profiles: List[GpmProfile]) -> List[GpmProfile]:
        """Gắn thêm thông tin kênh YouTube đã lưu vào danh sách GpmProfile."""
        caches = self.get_all_channel_caches()
        for p in profiles:
            if p.id in caches:
                c = caches[p.id]
                p.channel_id = c.channel_id
                p.channel_name = c.channel_name
                p.is_authenticated = c.is_authenticated
                p.last_collected_at = c.last_collected_at
        return profiles

    # =========================================================================
    # 3. Quản lý Lịch sử chạy (Run History)
    # =========================================================================

    def add_run_history(self, record: RunHistoryRecord):
        """Thêm một bản ghi lịch sử chạy mới."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO run_history (
                    run_id, profile_id, profile_name, channel_id, channel_name,
                    period, video_count, status, output_dir, started_at, finished_at, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                record.run_id,
                record.profile_id,
                record.profile_name,
                record.channel_id,
                record.channel_name,
                record.period,
                record.video_count,
                record.status,
                record.output_dir,
                record.started_at,
                record.finished_at,
                record.error_message,
            ))
            conn.commit()

    save_run_record = add_run_history

    def update_run_history(
        self,
        run_id: str,
        status: str,
        video_count: Optional[int] = None,
        finished_at: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Cập nhật trạng thái và kết quả của một đợt chạy."""
        finished = finished_at or datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE run_history
                SET status = ?,
                    video_count = COALESCE(?, video_count),
                    finished_at = ?,
                    error_message = ?
                WHERE run_id = ?;
            """, (status, video_count, finished, error_message, run_id))
            conn.commit()

    def get_run_history(self, limit: int = 50) -> List[RunHistoryRecord]:
        """Lấy danh sách các đợt chạy gần nhất."""
        records = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM run_history
                ORDER BY started_at DESC
                LIMIT ?;
            """, (limit,))
            for row in cursor.fetchall():
                records.append(
                    RunHistoryRecord(
                        run_id=row["run_id"],
                        profile_id=row["profile_id"],
                        profile_name=row["profile_name"],
                        channel_id=row["channel_id"],
                        channel_name=row["channel_name"],
                        period=row["period"],
                        video_count=row["video_count"],
                        status=row["status"],
                        output_dir=row["output_dir"],
                        started_at=row["started_at"],
                        finished_at=row["finished_at"],
                        error_message=row["error_message"],
                    )
                )
        return records

    get_recent_runs = get_run_history


# Semantic alias
HistoryStorage = LocalStorage
