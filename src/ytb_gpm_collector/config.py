"""Configuration loader and paths for YouTube Studio GPM Collector."""

import os
import json
from pathlib import Path
from typing import Optional


def get_default_setting_dat_path() -> Path:
    """Đường dẫn mặc định tới file setting.dat của GPMLoginGlobal."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        p = Path(appdata) / "GPMLoginGlobal" / "setting.dat"
        if p.exists():
            return p
    return Path(r"C:\Users\Admin\AppData\Roaming\GPMLoginGlobal\setting.dat")


def read_gpm_api_port_from_setting(setting_path: Optional[Path] = None) -> int:
    """
    Đọc cổng API từ setting.dat của GPM.
    Nếu không tìm thấy hoặc lỗi, trả về cổng mặc định 19996.
    """
    path = setting_path or get_default_setting_dat_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                port = data.get("api", {}).get("port")
                if port and isinstance(port, int) and 1 <= port <= 65535:
                    return port
        except Exception:
            pass
    return 19996


def get_gpm_database_path(setting_path: Optional[Path] = None) -> Optional[Path]:
    """Lấy đường dẫn tới file database.db của GPM."""
    path = setting_path or get_default_setting_dat_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                storage_path = data.get("local_storage_path")
                if storage_path:
                    db_file = Path(storage_path) / "database.db"
                    if db_file.exists():
                        return db_file
        except Exception:
            pass

    fallback = Path(r"D:\GPMLogin\Profile_Chrome_GPM\database.db")
    if fallback.exists():
        return fallback
    return None


class AppConfig:
    """Cấu hình toàn cục cho ứng dụng."""

    def __init__(self, api_port: Optional[int] = None):
        self.api_port = api_port or read_gpm_api_port_from_setting()
        self.api_base_url = f"http://127.0.0.1:{self.api_port}"
        self.db_path = get_gpm_database_path()
        self.default_concurrency = 2
        self.runs_dir = Path("runs")
        self.timeout_seconds = 30.0
