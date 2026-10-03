"""GPM-Login Local API client."""

import logging
import sqlite3
import json
import socket
import re
from typing import List, Optional, Dict, Any
from pathlib import Path
import httpx

from ytb_gpm_collector.config import read_gpm_api_port_from_setting, get_gpm_database_path
from ytb_gpm_collector.domain.models import GpmProfile, GpmStartResult
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
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((host, self.port))
                return True
        except Exception:
            return False

    def check_connection(self) -> bool:
        """Kiểm tra xem GPM Local API có đang phản hồi không."""
        if not self.is_api_port_listening():
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

    def get_profiles(self) -> List[GpmProfile]:
        """
        Lấy danh sách tất cả profile từ GPM.
        Ưu tiên gọi qua Local API (v1 / v3).
        Nếu API chưa khởi động hoặc chưa mở port, tự động đọc trực tiếp từ database.db của GPM.
        """
        if self.is_api_port_listening():
            try:
                profiles = self._get_profiles_from_api()
                if profiles:
                    return profiles
            except Exception as e:
                logger.warning(f"Lỗi gọi API ({e}), chuyển sang đọc database cục bộ.")

        # Đọc trực tiếp từ SQLite database của GPM
        if self.db_path and self.db_path.exists():
            return self._get_profiles_from_db()

        raise GpmConnectionError(
            f"Không thể kết nối tới GPM API tại {self.base_url} và không tìm thấy database tại {self.db_path}."
        )

    def _get_profiles_from_api(self) -> List[GpmProfile]:
        """Gọi API GPM để lấy danh sách profile."""
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
                            if p_id:
                                results.append(
                                    GpmProfile(
                                        id=str(p_id),
                                        name=str(p_name),
                                        raw_proxy=raw_proxy or None,
                                        browser_type=item.get("browser_type", "Chrome"),
                                        browser_version=item.get("browser_version"),
                                        group_id=item.get("group_id"),
                                    )
                                )
                        if results:
                            return results
                except Exception as e:
                    logger.debug(f"Lỗi khi thử endpoint {ep}: {e}")
                    continue
        return []

    def _get_profiles_from_db(self) -> List[GpmProfile]:
        """Đọc trực tiếp danh sách profile từ file SQLite database của GPM."""
        results = []
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(profiles);")
            columns = [c[1] for c in cursor.fetchall()]

            cursor.execute("SELECT * FROM profiles ORDER BY name ASC;")
            rows = cursor.fetchall()
            for r in rows:
                item = dict(zip(columns, r))
                p_id = item.get("id")
                p_name = item.get("name", "Unknown")

                # Trích xuất proxy từ dynamic_data, extra_data hoặc raw_proxy
                raw_proxy = item.get("raw_proxy")
                dyn_str = item.get("dynamic_data") or item.get("extra_data")
                if not raw_proxy and dyn_str:
                    try:
                        parsed = json.loads(dyn_str)
                        raw_proxy = parsed.get("proxy", {}).get("raw_proxy")
                    except Exception:
                        pass

                results.append(
                    GpmProfile(
                        id=str(p_id),
                        name=str(p_name),
                        raw_proxy=raw_proxy or None,
                        browser_type=item.get("browser_type", "Chrome"),
                        browser_version=item.get("browser_version"),
                        group_id=item.get("group_id"),
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

                            # Nếu chưa có remote_debugging_address nhưng có ws_url, trích xuất host:port
                            if not remote_addr and ws_url:
                                parts = ws_url.replace("ws://", "").split("/")
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
