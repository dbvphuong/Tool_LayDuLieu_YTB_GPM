"""GPM-Login Local API client."""

import logging
import sqlite3
import json
import socket
import re
from typing import List, Optional, Dict, Any
from pathlib import Path
import httpx

from ytb_gpm_collector.config import read_gpm_api_port_from_setting, get_gpm_database_path, is_port_open
from ytb_gpm_collector.domain.models import GpmProfile, GpmGroup, GpmStartResult
from ytb_gpm_collector.domain.errors import (
    GpmConnectionError,
    GpmProfileNotFoundError,
    GpmStartProfileError,
)

logger = logging.getLogger(__name__)


class GpmClient:
    """Client giao tiếp với GPM-Login qua Local REST API và SQLite Database dự phòng."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        port: Optional[int] = None,
        timeout: float = 30.0,
    ):
        self.port = port or read_gpm_api_port_from_setting()
        self.base_url = (base_url or f"http://127.0.0.1:{self.port}").rstrip("/")
        self.timeout = timeout
        self.db_path = get_gpm_database_path()

    def is_api_port_listening(self, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
        """Kiểm tra nhanh cổng API bằng TCP socket để tránh bị treo timeout."""
        return is_port_open(self.port, host=host, timeout=timeout)

    def check_connection(self) -> bool:
        """Kiểm tra xem GPM Local API có đang phản hồi không."""
        if not self.is_api_port_listening():
            # Thử tự động chuyển sang cổng 9495 nếu đang là cổng khác
            if self.port != 9495 and is_port_open(9495):
                self.port = 9495
                self.base_url = f"http://127.0.0.1:9495"
            else:
                return False

        test_endpoints = [
            f"{self.base_url}/api/v1/profiles?page=1&page_size=1",
            f"{self.base_url}/api/v3/profiles",
            f"{self.base_url}/profiles",
        ]
        with httpx.Client(timeout=2.0) as client:
            for url in test_endpoints:
                try:
                    resp = client.get(url)
                    if resp.status_code in (200, 400, 404):
                        return True
                except Exception:
                    continue
        return False

    def get_groups(self) -> List[GpmGroup]:
        """
        Lấy danh sách tất cả các Nhóm (Groups) profile từ GPM.
        Ưu tiên gọi qua Local API (v1 / v3).
        Nếu API chưa khởi động hoặc lỗi, đọc trực tiếp từ SQLite database.db của GPM.
        """
        if self.check_connection():
            try:
                groups = self._get_groups_from_api()
                if groups:
                    return groups
            except Exception as e:
                logger.warning(f"Lỗi gọi API get_groups ({e}), chuyển sang đọc database cục bộ.")

        # Đọc trực tiếp từ SQLite database của GPM
        if self.db_path and self.db_path.exists():
            return self._get_groups_from_db()

        return []

    def _get_groups_from_api(self) -> List[GpmGroup]:
        """Gọi API GPM để lấy danh sách nhóm."""
        endpoints = [
            f"{self.base_url}/api/v1/groups?page=1&page_size=1000",
            f"{self.base_url}/api/v3/groups",
            f"{self.base_url}/groups",
        ]
        with httpx.Client(timeout=min(5.0, self.timeout)) as client:
            for ep in endpoints:
                try:
                    resp = client.get(ep)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_list = []
                        if isinstance(data, dict):
                            if "data" in data and isinstance(data["data"], dict) and "data" in data["data"]:
                                raw_list = data["data"]["data"]
                            elif "data" in data and isinstance(data["data"], list):
                                raw_list = data["data"]
                            elif "groups" in data:
                                raw_list = data["groups"]
                        elif isinstance(data, list):
                            raw_list = data

                        results = []
                        for item in raw_list:
                            g_id = item.get("id") or item.get("group_id")
                            g_name = item.get("name") or item.get("group_name", "Unknown")
                            g_order = item.get("sort_order") or item.get("order") or 0
                            if g_id:
                                results.append(
                                    GpmGroup(
                                        id=str(g_id),
                                        name=str(g_name),
                                        sort_order=int(g_order or 0),
                                    )
                                )
                        if results:
                            # Sắp xếp theo sort_order và tên
                            results.sort(key=lambda x: (x.sort_order if x.sort_order is not None else 0, x.name))
                            return results
                except Exception as e:
                    logger.debug(f"Lỗi khi thử endpoint groups {ep}: {e}")
                    continue
        return []

    def _get_groups_from_db(self) -> List[GpmGroup]:
        """Đọc danh sách nhóm từ file SQLite database của GPM."""
        results = []
        if not self.db_path or not self.db_path.exists():
            return results
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='groups';")
            if not cursor.fetchone():
                return results

            cursor.execute("PRAGMA table_info(groups);")
            columns = [c[1] for c in cursor.fetchall()]

            order_col = '"order"' if "order" in columns else ("sort_order" if "sort_order" in columns else "name")
            cursor.execute(f"SELECT * FROM groups ORDER BY {order_col} ASC, name ASC;")
            rows = cursor.fetchall()
            for r in rows:
                item = dict(zip(columns, r))
                g_id = item.get("id")
                g_name = item.get("name", "Unknown")
                g_order = item.get("order") or item.get("sort_order") or 0
                if g_id:
                    results.append(
                        GpmGroup(
                            id=str(g_id),
                            name=str(g_name),
                            sort_order=int(g_order or 0),
                        )
                    )
        except Exception as e:
            logger.warning(f"Lỗi đọc groups từ DB: {e}")
        finally:
            conn.close()
        return results

    def get_profiles(self) -> List[GpmProfile]:
        """
        Lấy danh sách tất cả profile từ GPM.
        Ưu tiên gọi qua Local API (v1 / v3).
        Nếu API chưa khởi động hoặc chưa mở port, tự động đọc trực tiếp từ database.db của GPM.
        """
        # Tải danh sách nhóm trước để map group_id -> group_name
        group_map: Dict[str, str] = {}
        try:
            groups = self.get_groups()
            group_map = {g.id: g.name for g in groups}
        except Exception as g_err:
            logger.debug(f"Không thể tải groups để gán tên: {g_err}")

        if self.check_connection():
            try:
                profiles = self._get_profiles_from_api(group_map)
                if profiles:
                    return profiles
            except Exception as e:
                logger.warning(f"Lỗi gọi API ({e}), chuyển sang đọc database cục bộ.")

        # Đọc trực tiếp từ SQLite database của GPM
        if self.db_path and self.db_path.exists():
            return self._get_profiles_from_db(group_map)

        raise GpmConnectionError(
            f"Không thể kết nối tới GPM API tại {self.base_url} và không tìm thấy database tại {self.db_path}."
        )

    def _get_profiles_from_api(self, group_map: Optional[Dict[str, str]] = None) -> List[GpmProfile]:
        """Gọi API GPM để lấy danh sách profile."""
        group_map = group_map or {}
        endpoints = [
            f"{self.base_url}/api/v1/profiles?page=1&page_size=1000",
            f"{self.base_url}/api/v3/profiles",
            f"{self.base_url}/profiles",
        ]
        with httpx.Client(timeout=min(5.0, self.timeout)) as client:
            for ep in endpoints:
                try:
                    resp = client.get(ep)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_list = []
                        if isinstance(data, dict):
                            if "data" in data and isinstance(data["data"], dict) and "data" in data["data"]:
                                raw_list = data["data"]["data"]
                            elif "data" in data and isinstance(data["data"], list):
                                raw_list = data["data"]
                            elif "profiles" in data:
                                raw_list = data["profiles"]
                        elif isinstance(data, list):
                            raw_list = data

                        results = []
                        for item in raw_list:
                            p_id = item.get("id") or item.get("profile_id")
                            p_name = item.get("name") or item.get("profile_name", "Unknown")
                            raw_proxy = item.get("raw_proxy") or item.get("proxy", "")
                            b_info = item.get("browser", {})
                            b_type = b_info.get("name", "Chrome") if isinstance(b_info, dict) else item.get("browser_type", "Chrome")
                            b_version = b_info.get("version") if isinstance(b_info, dict) else item.get("browser_version")
                            g_id = item.get("group_id")
                            g_name = item.get("group_name") or group_map.get(str(g_id)) if g_id else None
                            p_note = item.get("note") or ""

                            if p_id:
                                results.append(
                                    GpmProfile(
                                        id=str(p_id),
                                        name=str(p_name),
                                        raw_proxy=raw_proxy or None,
                                        browser_type=b_type,
                                        browser_version=b_version,
                                        group_id=str(g_id) if g_id else None,
                                        group_name=g_name,
                                        note=str(p_note) if p_note else None,
                                    )
                                )
                        if results:
                            return results
                except Exception as e:
                    logger.debug(f"Lỗi khi thử endpoint {ep}: {e}")
                    continue
        return []

    def _get_profiles_from_db(self, group_map: Optional[Dict[str, str]] = None) -> List[GpmProfile]:
        """Đọc trực tiếp danh sách profile từ file SQLite database của GPM."""
        results = []
        group_map = group_map or {}
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(profiles);")
            columns = [c[1] for c in cursor.fetchall()]

            # Nạp group_map từ bảng groups nếu chưa có
            if not group_map:
                try:
                    cursor.execute("SELECT id, name FROM groups;")
                    for gid, gname in cursor.fetchall():
                        group_map[str(gid)] = str(gname)
                except Exception:
                    pass

            cursor.execute("SELECT * FROM profiles ORDER BY name ASC;")
            rows = cursor.fetchall()
            for r in rows:
                item = dict(zip(columns, r))
                p_id = item.get("id")
                p_name = item.get("name", "Unknown")

                # Trích xuất proxy và note từ dynamic_data, extra_data hoặc raw_proxy
                raw_proxy = item.get("raw_proxy")
                p_note = item.get("note") or ""
                dyn_str = item.get("dynamic_data") or item.get("extra_data")
                if dyn_str:
                    try:
                        parsed = json.loads(dyn_str)
                        if not raw_proxy:
                            raw_proxy = parsed.get("proxy", {}).get("raw_proxy")
                        if not p_note:
                            p_note = parsed.get("note") or ""
                    except Exception:
                        pass

                g_id = item.get("group_id")
                g_name = group_map.get(str(g_id)) if g_id else None

                results.append(
                    GpmProfile(
                        id=str(p_id),
                        name=str(p_name),
                        raw_proxy=raw_proxy or None,
                        browser_type=item.get("browser_type", "Chrome"),
                        browser_version=item.get("browser_version"),
                        group_id=str(g_id) if g_id else None,
                        group_name=g_name,
                        note=str(p_note) if p_note else None,
                    )
                )
        finally:
            conn.close()
        return results

    def find_profile(self, name_or_id: str) -> GpmProfile:
        """
        Tìm một profile theo Tên hoặc theo ID.
        Hỗ trợ tìm chính xác hoặc dạng số (ví dụ '06' -> 'Profile 6').
        """
        profiles = self.get_profiles()
        query_str = name_or_id.strip()
        query_lower = query_str.lower()

        # 1. Tìm chính xác theo ID
        for p in profiles:
            if p.id.lower() == query_lower:
                return p

        # 2. Tìm chính xác theo Tên
        for p in profiles:
            if p.name.strip().lower() == query_lower:
                return p

        # 3. Tìm theo số thứ tự profile (ví dụ '06' hoặc '6' -> 'Profile 6' hoặc 'Profile 06')
        num_match = re.search(r"\d+", query_str)
        if num_match:
            num = int(num_match.group())
            candidate_names = [f"profile {num}", f"profile {num:02d}", f"{num}", f"{num:02d}"]
            for p in profiles:
                p_lower = p.name.strip().lower()
                if p_lower in candidate_names:
                    return p

        # 4. Tìm kiếm từ khóa chứa trong tên
        for p in profiles:
            if query_lower in p.name.lower():
                return p

        raise GpmProfileNotFoundError(f"Không tìm thấy profile phù hợp với '{name_or_id}'.")

    def start_profile(
        self,
        profile_id: str,
        remote_debugging_port: Optional[int] = None,
        window_scale: float = 1.0,
        window_pos: Optional[str] = None,
        window_size: Optional[str] = None,
        addition_args: Optional[str] = None,
    ) -> GpmStartResult:
        """
        Gọi API GPM để khởi chạy Profile.
        Nhận lại địa chỉ kết nối CDP (remote_debugging_address) và websocket_debugging_url.
        """
        # Đảm bảo kết nối API đã sẵn sàng
        self.check_connection()

        params: Dict[str, Any] = {
            "window_scale": window_scale,
        }
        if remote_debugging_port:
            params["remote_debugging_port"] = remote_debugging_port
        if window_pos:
            params["window_pos"] = window_pos
        if window_size:
            params["window_size"] = window_size
        if addition_args:
            params["addition_args"] = addition_args

        endpoints = [
            f"{self.base_url}/api/v1/profiles/start/{profile_id}",
            f"{self.base_url}/api/v3/profiles/start/{profile_id}",
            f"{self.base_url}/profiles/start/{profile_id}",
        ]

        last_error = None
        with httpx.Client(timeout=self.timeout) as client:
            for ep in endpoints:
                try:
                    resp = client.get(ep, params=params)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        success = res_json.get("success", False)
                        data = res_json.get("data", {})
                        if success and isinstance(data, dict):
                            remote_addr = data.get("remote_debugging_address")
                            ws_url = data.get("websocket_debugging_url")
                            dbg_port = data.get("remote_debugging_port")

                            if not remote_addr and dbg_port:
                                remote_addr = f"127.0.0.1:{dbg_port}"
                            elif not remote_addr and ws_url:
                                parts = ws_url.replace("ws://", "").replace("localhost:", "127.0.0.1:").split("/")
                                if parts:
                                    remote_addr = parts[0]

                            return GpmStartResult(
                                success=True,
                                profile_id=profile_id,
                                remote_debugging_address=remote_addr,
                                websocket_debugging_url=ws_url,
                                driver_path=data.get("driver_path"),
                                message=res_json.get("message", "OK"),
                            )
                        else:
                            last_error = res_json.get("message") or str(res_json)
                except Exception as e:
                    last_error = str(e)
                    continue

        raise GpmStartProfileError(f"Không thể khởi động profile {profile_id}: {last_error}")

    def close_profile(self, profile_id: str) -> bool:
        """Gọi API GPM để đóng Profile."""
        self.check_connection()
        endpoints = [
            f"{self.base_url}/api/v1/profiles/stop/{profile_id}",
            f"{self.base_url}/api/v3/profiles/close/{profile_id}",
            f"{self.base_url}/profiles/stop/{profile_id}",
        ]
        with httpx.Client(timeout=self.timeout) as client:
            for ep in endpoints:
                try:
                    resp = client.get(ep)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        return res_json.get("success", True)
                except Exception:
                    continue
        return False
