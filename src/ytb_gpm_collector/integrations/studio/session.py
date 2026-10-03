"""Playwright CDP Session management for GPM Chromium instance."""

import logging
import re
import time
from typing import Optional, List, Union
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, Error as PlaywrightError

from ytb_gpm_collector.domain.models import GpmStartResult
from ytb_gpm_collector.domain.errors import CdpConnectionError

logger = logging.getLogger(__name__)


class StudioSession:
    """
    Quản lý kết nối Playwright CDP với trình duyệt Chromium của GPM-Login.
    
    Tuân thủ nguyên tắc:
    - Kết nối vào Chrome GPM bằng `playwright.chromium.connect_over_cdp(cdp_url)`.
    - Không khởi tạo trình duyệt mới, dùng chính context đang chạy của GPM profile để giữ nguyên cookie, proxy, fingerprint.
    - Hỗ trợ context manager (`with StudioSession(...) as session:`).
    """

    def __init__(
        self,
        cdp_endpoint: Union[str, GpmStartResult],
        timeout_seconds: float = 30.0,
    ):
        """
        Khởi tạo StudioSession.
        
        Args:
            cdp_endpoint: Chuỗi địa chỉ CDP (ví dụ "127.0.0.1:53962", "http://127.0.0.1:53962", "ws://...")
                          hoặc đối tượng GpmStartResult từ GpmClient.start_profile.
            timeout_seconds: Thời gian chờ tối đa cho các tác vụ Playwright (mặc định 30s).
        """
        self.endpoint_url = self._normalize_endpoint(cdp_endpoint)
        self.timeout_ms = int(timeout_seconds * 1000)
        
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._is_connected: bool = False

    @staticmethod
    def _normalize_endpoint(cdp_endpoint: Union[str, GpmStartResult]) -> str:
        """Chuẩn hóa endpoint CDP thành định dạng URL hợp lệ (http:// hoặc ws://)."""
        raw_url = ""
        if isinstance(cdp_endpoint, GpmStartResult):
            raw_url = (
                cdp_endpoint.remote_debugging_address
                or cdp_endpoint.websocket_debugging_url
                or ""
            )
            if not raw_url:
                raise CdpConnectionError(
                    f"GpmStartResult không chứa địa chỉ remote_debugging_address hoặc websocket_debugging_url."
                )
        elif isinstance(cdp_endpoint, str):
            raw_url = cdp_endpoint.strip()
        else:
            raise ValueError(f"Tham số cdp_endpoint không hợp lệ: {type(cdp_endpoint)}")

        if not raw_url:
            raise CdpConnectionError("Địa chỉ CDP endpoint rỗng.")

        if raw_url.startswith("http://") or raw_url.startswith("https://") or raw_url.startswith("ws://") or raw_url.startswith("wss://"):
            return raw_url
        
        # Nếu dạng host:port (ví dụ: 127.0.0.1:53962), gắn thêm tiền tố http://
        return f"http://{raw_url}"

    @property
    def is_connected(self) -> bool:
        """Kiểm tra xem phiên CDP có đang kết nối và còn hiệu lực không."""
        return (
            self._is_connected
            and self.browser is not None
            and self.browser.is_connected()
        )

    def connect(self, retries: int = 3, retry_delay: float = 1.0) -> "StudioSession":
        """
        Kết nối Playwright vào Chrome GPM qua CDP.
        Tự động lấy BrowserContext mặc định đang chạy của GPM (chứa proxy, fingerprint, cookies).
        
        Args:
            retries: Số lần thử lại nếu trình duyệt GPM vừa bật chưa kịp mở cổng CDP.
            retry_delay: Thời gian nghỉ giữa các lần thử lại (giây).
        """
        if self.is_connected:
            logger.debug("StudioSession đã được kết nối trước đó.")
            return self

        last_error = None
        for attempt in range(1, retries + 1):
            try:
                logger.info(
                    f"Đang kết nối Playwright CDP tới {self.endpoint_url} (lần {attempt}/{retries})..."
                )
                if not self.playwright:
                    self.playwright = sync_playwright().start()

                self.browser = self.playwright.chromium.connect_over_cdp(
                    endpoint_url=self.endpoint_url,
                    timeout=self.timeout_ms,
                )

                # Sử dụng BrowserContext mặc định của GPM đang chạy
                # Tuyệt đối không tạo context mới vì sẽ mất proxy/session của GPM
                if self.browser.contexts:
                    self.context = self.browser.contexts[0]
                    logger.info(
                        f"Đã gắn vào context mặc định của GPM (Số context: {len(self.browser.contexts)}, số tabs: {len(self.context.pages)})."
                    )
                else:
                    logger.warning(
                        "Không tìm thấy context có sẵn trong Chromium, tạo context mới trong trình duyệt GPM."
                    )
                    self.context = self.browser.new_context()

                # Cấu hình timeout mặc định cho context
                self.context.set_default_navigation_timeout(self.timeout_ms)
                self.context.set_default_timeout(self.timeout_ms)

                self._is_connected = True
                logger.info(f"Kết nối Playwright CDP thành công tới {self.endpoint_url}.")
                return self

            except PlaywrightError as e:
                last_error = e
                logger.warning(f"Thử kết nối CDP lần {attempt} thất bại: {e}")
                if attempt < retries:
                    time.sleep(retry_delay)
            except Exception as e:
                last_error = e
                logger.warning(f"Lỗi ngoài dự kiến khi kết nối CDP lần {attempt}: {e}")
                if attempt < retries:
                    time.sleep(retry_delay)

        self.disconnect()
        raise CdpConnectionError(
            f"Không thể kết nối Playwright CDP tới {self.endpoint_url} sau {retries} lần thử. Lỗi: {last_error}"
        ) from last_error

    def get_page(self, bring_to_front: bool = True) -> Page:
        """
        Lấy tab trình duyệt đang mở trong context.
        Nếu context chưa có tab nào, mở một tab mới.
        
        Args:
            bring_to_front: Tự động kích hoạt đưa tab lên trước màn hình.
        """
        if not self.is_connected or not self.context:
            raise CdpConnectionError("Phiên StudioSession chưa được kết nối hoặc đã bị đóng.")

        if self.context.pages:
            page = self.context.pages[0]
        else:
            page = self.context.new_page()

        page.set_default_navigation_timeout(self.timeout_ms)
        page.set_default_timeout(self.timeout_ms)

        if bring_to_front:
            try:
                page.bring_to_front()
            except Exception as e:
                logger.debug(f"Không thể bring_to_front: {e}")

        return page

    def get_or_create_page(self) -> Page:
        """
        Tìm tab đang ở YouTube Studio hoặc tab trống (about:blank).
        Nếu không có, trả về tab đầu tiên hoặc mở tab mới.
        """
        if not self.is_connected or not self.context:
            raise CdpConnectionError("Phiên StudioSession chưa được kết nối hoặc đã bị đóng.")

        # 1. Tìm tab đã mở YouTube Studio
        studio_page = self.find_page_by_url("studio.youtube.com")
        if studio_page:
            return studio_page

        # 2. Tìm tab trống about:blank để tái sử dụng
        for p in self.context.pages:
            if p.url in ("about:blank", "chrome://newtab/", ""):
                try:
                    p.bring_to_front()
                except Exception:
                    pass
                return p

        # 3. Sử dụng tab hiện có hoặc tạo tab mới
        return self.get_page(bring_to_front=True)

    def find_page_by_url(self, url_keyword: str) -> Optional[Page]:
        """Tìm tab có URL chứa từ khóa và kích hoạt hiển thị."""
        if not self.context:
            return None

        for p in self.context.pages:
            try:
                if url_keyword.lower() in p.url.lower():
                    p.bring_to_front()
                    return p
            except Exception:
                continue
        return None

    def new_page(self) -> Page:
        """Mở một tab mới trong context của GPM."""
        if not self.is_connected or not self.context:
            raise CdpConnectionError("Phiên StudioSession chưa được kết nối hoặc đã bị đóng.")

        page = self.context.new_page()
        page.set_default_navigation_timeout(self.timeout_ms)
        page.set_default_timeout(self.timeout_ms)
        return page

    def disconnect(self):
        """
        Ngắt kết nối Playwright CDP một cách an toàn.
        Lưu ý: Chỉ ngắt kết nối automation, KHÔNG đóng tiến trình Chrome GPM
        (vòng đời của Chrome GPM do GpmClient.close_profile quản lý).
        """
        self._is_connected = False

        if self.browser:
            try:
                # browser.close() khi kết nối qua CDP sẽ ngắt kết nối CDP client
                self.browser.close()
            except Exception as e:
                logger.debug(f"Đã đóng hoặc ngắt kết nối CDP browser: {e}")
            self.browser = None

        self.context = None

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                logger.debug(f"Đã dừng playwright driver: {e}")
            self.playwright = None

    def close(self):
        """Bí danh cho disconnect()."""
        self.disconnect()

    def __enter__(self) -> "StudioSession":
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
