"""Configuration loader and paths for YouTube Studio GPM Collector."""

import os
import json
import socket
from pathlib import Path
from typing import Optional, List, Union


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
    """Kiểm tra nhanh xem một cổng TCP có đang mở không."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            return True
    except Exception:
        return False


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
    Tự động dò tìm cổng GPM Local API đang mở:
    1. Kiểm tra cổng 9495 (cổng mặc định mới của GPMLoginGlobal v5).
    2. Đọc từ setting.dat (cổng tùy chỉnh hoặc 19996).
    3. Kiểm tra cổng 19996.
    4. Trả về cổng phát hiện được đang lắng nghe hoặc 9495.
    """
    # 1. Thử cổng 9495 trước (GPMLogin Global v5)
    if is_port_open(9495):
        return 9495

    # 2. Đọc cấu hình từ setting.dat
    path = setting_path or get_default_setting_dat_path()
    configured_port = None
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                port = data.get("api", {}).get("port")
                if port and isinstance(port, int) and 1 <= port <= 65535:
                    configured_port = port
                    if is_port_open(configured_port):
                        return configured_port
        except Exception:
            pass

    # 3. Thử cổng 19996
    if is_port_open(19996):
        return 19996

    # Nếu chưa cổng nào mở, trả về cổng cấu hình trong setting.dat hoặc 9495
    return configured_port or 9495


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

    def __init__(
        self,
        api_port: Optional[int] = None,
        runs_dir: Optional[Union[Path, str]] = None,
        default_concurrency: int = 2,
        timeout_seconds: float = 60.0,
        keep_raw_files: bool = True,
        auto_generate_reports: bool = True,
        gpm_install_dir: Optional[str] = None,
    ):
        self.api_port = api_port or read_gpm_api_port_from_setting()
        self.api_base_url = f"http://127.0.0.1:{self.api_port}"
        self.db_path = get_gpm_database_path()
        self.default_concurrency = default_concurrency
        self.runs_dir = Path(runs_dir or "runs").resolve()
        self.timeout_seconds = timeout_seconds
        self.keep_raw_files = keep_raw_files
        self.auto_generate_reports = auto_generate_reports
        self.gpm_install_dir = gpm_install_dir or (
            str(get_default_setting_dat_path().parent)
            if get_default_setting_dat_path().exists()
            else None
        )

    def to_dict(self) -> dict:
        """Chuyển thành từ điển để lưu trữ."""
        return {
            "api_port": self.api_port,
            "runs_dir": str(self.runs_dir),
            "default_concurrency": self.default_concurrency,
            "timeout_seconds": self.timeout_seconds,
            "keep_raw_files": self.keep_raw_files,
            "auto_generate_reports": self.auto_generate_reports,
            "gpm_install_dir": self.gpm_install_dir,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """Tạo đối tượng từ dict."""
        return cls(
            api_port=data.get("api_port"),
            runs_dir=data.get("runs_dir"),
            default_concurrency=data.get("default_concurrency", 2),
            timeout_seconds=data.get("timeout_seconds", 60.0),
            keep_raw_files=data.get("keep_raw_files", True),
            auto_generate_reports=data.get("auto_generate_reports", True),
            gpm_install_dir=data.get("gpm_install_dir"),
        )

    def save_to_storage(self, storage) -> None:
        """Lưu cấu hình vào LocalStorage."""
        for key, val in self.to_dict().items():
            storage.save_setting(f"config_{key}", val)

    @classmethod
    def load_from_storage(cls, storage) -> "AppConfig":
        """Nạp cấu hình từ LocalStorage nếu có, nếu không lấy mặc định."""
        defaults = cls().to_dict()
        loaded = {}
        for key in defaults.keys():
            val = storage.get_setting(f"config_{key}", None)
            if val is not None:
                loaded[key] = val
        merged = {**defaults, **loaded}
        return cls.from_dict(merged)
