"""YouTube Studio Analytics and Channel Navigation Page Object."""

import logging
import re
import time
from typing import Optional, List, Tuple
from pathlib import Path
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from ytb_gpm_collector.domain.models import ChannelIdentity
from ytb_gpm_collector.domain.errors import (
    StudioAuthenticationError,
    StudioNavigationError,
)

logger = logging.getLogger(__name__)


class StudioAnalyticsPage:
    """
    Page Object điều khiển và nhận diện thông tin trên YouTube Studio.
    
    Chức năng chính (Task 2.2):
    1. Truy cập https://studio.youtube.com.
    2. Kiểm tra trạng thái đăng nhập; ném StudioAuthenticationError nếu chưa đăng nhập.
    3. Nhận diện và trích xuất Channel ID và Channel Name.
    4. Điều hướng tới trang "Số liệu phân tích" (Analytics).
    """

    def __init__(self, page: Page, timeout_seconds: float = 30.0):
        self.page = page
        self.timeout_ms = int(timeout_seconds * 1000)
        self.timeout_seconds = timeout_seconds
        self.identity: Optional[ChannelIdentity] = None

    @property
    def channel_id(self) -> Optional[str]:
        return self.identity.channel_id if self.identity else None

    @property
    def channel_name(self) -> Optional[str]:
        return self.identity.channel_name if self.identity else None

    def navigate_to_studio(self, retries: int = 2) -> ChannelIdentity:
        """
        Truy cập trang chủ YouTube Studio, kiểm tra đăng nhập và trích xuất thông tin kênh.
        
        Returns:
            ChannelIdentity: Đối tượng chứa channel_id, channel_name, url.
        Raises:
            StudioAuthenticationError: Nếu tài khoản chưa đăng nhập YouTube/Google.
            StudioNavigationError: Nếu trang không thể tải hoặc không nhận diện được kênh.
        """
        studio_base_url = "https://studio.youtube.com"
        logger.info(f"Đang truy cập YouTube Studio: {studio_base_url}...")

        last_error = None
        for attempt in range(1, retries + 1):
            try:
                # Điều hướng tới studio.youtube.com
                self.page.goto(
                    studio_base_url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )

                # Chờ trang xử lý redirect
                self._check_authentication_status()
                
                # Trích xuất thông tin kênh
                identity = self._extract_channel_identity()
                self.identity = identity
                logger.info(
                    f"Nhận diện kênh thành công: Tên='{identity.channel_name}', ID='{identity.channel_id}'"
                )
                return identity

            except (StudioAuthenticationError, StudioNavigationError):
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"Lỗi khi truy cập Studio lần {attempt}/{retries}: {e}")
                if attempt < retries:
                    time.sleep(2.0)

        raise StudioNavigationError(
            f"Không thể truy cập YouTube Studio sau {retries} lần thử: {last_error}"
        ) from last_error

    def _check_authentication_status(self):
        """
        Kiểm tra xem trình duyệt có bị chuyển hướng tới trang đăng nhập Google hay không.
        """
        # Cho phép trang chuyển hướng 1-2 giây nếu có redirect
        time.sleep(1.5)
        current_url = self.page.url.lower()

        # Kiểm tra các dấu hiệu của trang đăng nhập
        login_indicators = [
            "accounts.google.com/signin",
            "accounts.google.com/servicelogin",
            "accounts.google.com/v3/signin",
        ]
        if any(ind in current_url for ind in login_indicators):
            logger.error(f"Phát hiện trang đăng nhập Google: {self.page.url}")
            raise StudioAuthenticationError(
                "Profile GPM chưa đăng nhập tài khoản Google/YouTube Studio. "
                "Vui lòng mở Profile trên GPM và đăng nhập tài khoản trước khi thu thập."
            )

        # Kiểm tra element đăng nhập nếu trang không đổi URL
        try:
            sign_in_button = self.page.query_selector(
                'input[type="email"], #identifierId, a[href*="ServiceLogin"]'
            )
            if sign_in_button:
                raise StudioAuthenticationError(
                    "Phát hiện ô đăng nhập tài khoản. Profile chưa được đăng nhập sẵn."
                )
        except Exception:
            pass

    def _extract_channel_identity(self, max_wait_seconds: float = 15.0) -> ChannelIdentity:
        """
        Trích xuất Channel ID và Channel Name từ trang YouTube Studio.
        """
        start_time = time.time()
        channel_id = None
        channel_name = None

        while time.time() - start_time < max_wait_seconds:
            # 1. Trích xuất Channel ID
            # Cách 1: ytcfg trong ngữ cảnh JS của YouTube Studio (chính xác tuyệt đối 100%)
            try:
                js_channel_id = self.page.evaluate(
                    "() => window.ytcfg?.get?.('CHANNEL_ID') || window.yt?.config_?.CHANNEL_ID || null"
                )
                if js_channel_id and js_channel_id.startswith("UC"):
                    channel_id = js_channel_id
            except Exception:
                pass

            # Cách 2: Regex trên URL hiện tại
            if not channel_id:
                url_match = re.search(r"/channel/(UC[a-zA-Z0-9_-]+)", self.page.url)
                if url_match:
                    channel_id = url_match.group(1)

            # Cách 3: Thẻ meta hoặc link canonical
            if not channel_id:
                try:
                    meta_id = self.page.evaluate(
                        "() => document.querySelector('meta[itemprop=\"channelId\"]')?.content || null"
                    )
                    if meta_id and meta_id.startswith("UC"):
                        channel_id = meta_id
                except Exception:
                    pass

            # 2. Trích xuất Channel Name
            try:
                extracted_name = self.page.evaluate("""() => {
                    const selectors = [
                        '#channel-title',
                        'ytcp-entity-header #name',
                        '#entity-name',
                        'ytcp-navigation-drawer #channel-title',
                        '#channel-name',
                        'ytcp-header #channel-title'
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.innerText && el.innerText.trim()) {
                            return el.innerText.trim();
                        }
                    }
                    return window.ytcfg?.get?.('CHANNEL_TITLE') || window.yt?.config_?.CHANNEL_TITLE || null;
                }""")
                if extracted_name:
                    channel_name = extracted_name
            except Exception:
                pass

            # Nếu cả 2 đều đã lấy được thì dừng vòng chờ
            if channel_id and channel_name:
                break

            time.sleep(1.0)

        # Fallback nếu tên kênh chưa lấy được qua DOM
        if channel_id and not channel_name:
            # Thử lấy từ tiêu đề trang (Title)
            page_title = self.page.title()
            if " - YouTube Studio" in page_title:
                clean_title = page_title.split(" - YouTube Studio")[0].strip()
                # Nếu tiêu đề không phải là tiêu đề chung ("Trang tổng quan của kênh", "Dashboard"...)
                if clean_title and clean_title not in (
                    "Trang tổng quan của kênh",
                    "Channel dashboard",
                    "Số liệu phân tích về kênh",
                    "Channel analytics",
                ):
                    channel_name = clean_title
            if not channel_name:
                channel_name = f"Kênh ({channel_id})"

        if not channel_id:
            raise StudioNavigationError(
                f"Không thể trích xuất Channel ID từ YouTube Studio tại URL: {self.page.url}."
            )

        return ChannelIdentity(
            channel_id=channel_id,
            channel_name=channel_name or f"Kênh ({channel_id})",
            url=self.page.url,
            is_authenticated=True,
        )

    def navigate_to_analytics(self, channel_id: Optional[str] = None) -> bool:
        """
        Điều hướng tới trang "Số liệu phân tích" (Analytics) của kênh.
        
        Args:
            channel_id: ID của kênh (nếu không truyền sẽ dùng channel_id đã nhận diện).
            
        Returns:
            bool: True nếu điều hướng thành công và trang Analytics đã tải xong.
        """
        target_id = channel_id or self.channel_id
        if not target_id:
            # Nếu chưa có channel_id, tiến hành nhận diện trước
            identity = self.navigate_to_studio()
            target_id = identity.channel_id

        analytics_url = f"https://studio.youtube.com/channel/{target_id}/analytics"
        logger.info(f"Đang điều hướng tới trang Analytics: {analytics_url}...")

        try:
            # 1. Điều hướng trực tiếp bằng URL kênh
            self.page.goto(
                analytics_url,
                wait_until="domcontentloaded",
                timeout=self.timeout_ms,
            )

            # 2. Chờ xác nhận trang Analytics đã tải xong
            self._wait_for_analytics_loaded()
            logger.info("Đã tải xong trang Số liệu phân tích (Analytics) của kênh.")
            return True

        except Exception as e:
            logger.warning(
                f"Điều hướng trực tiếp URL Analytics gặp lỗi ({e}). Thử click menu Sidebar..."
            )
            # Thử phương án dự phòng: Click vào menu Analytics trong Sidebar
            return self._click_analytics_menu_item()

    def _wait_for_analytics_loaded(self, timeout_seconds: float = 15.0):
        """Chờ các thành phần cốt lõi của trang Analytics xuất hiện."""
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            # Kiểm tra URL
            if "/analytics" in self.page.url:
                # Kiểm tra tabs phân tích xuất hiện
                tabs_count = self.page.evaluate(
                    "() => document.querySelectorAll('tp-yt-paper-tab, ytcp-tab, [role=\"tab\"]').length"
                )
                if tabs_count and tabs_count > 0:
                    return

            time.sleep(0.8)

        # Nếu hết thời gian mà URL vẫn chứa analytics thì coi như đã vào được
        if "/analytics" in self.page.url:
            return

        raise StudioNavigationError(
            f"Trang Số liệu phân tích (Analytics) không tải được trong {timeout_seconds} giây. URL hiện tại: {self.page.url}"
        )

    def _click_analytics_menu_item(self) -> bool:
        """Phương án dự phòng: Click vào nút 'Số liệu phân tích' trên menu bên trái."""
        try:
            selectors = [
                'a[test-id="analytics"]',
                'a#menu-item-analytics',
                'a[href*="/analytics"]',
                'tp-yt-paper-item:has-text("Số liệu phân tích")',
                'tp-yt-paper-item:has-text("Analytics")',
            ]
            for sel in selectors:
                item = self.page.query_selector(sel)
                if item:
                    item.click()
                    self._wait_for_analytics_loaded()
                    return True
        except Exception as e:
            logger.error(f"Lỗi khi click menu Analytics: {e}")

        raise StudioNavigationError(
            f"Không thể chuyển tới trang Số liệu phân tích. URL: {self.page.url}"
        )

    def get_analytics_tabs(self) -> List[str]:
        """Lấy danh sách các tab phân tích đang hiển thị (ví dụ: Tổng quan, Nội dung, Đối tượng người xem...)."""
        try:
            tabs = self.page.evaluate("""() => {
                const elements = document.querySelectorAll('tp-yt-paper-tab, ytcp-tab, [role="tab"]');
                return Array.from(elements)
                    .map(el => el.innerText ? el.innerText.trim() : '')
                    .filter(txt => txt.length > 0);
            }""")
            return tabs or []
        except Exception:
            return []

    def is_advanced_mode_available(self) -> bool:
        """Kiểm tra nút/link 'Chế độ xem nâng cao' (Advanced Mode) có sẵn không."""
        try:
            found = self.page.evaluate("""() => {
                const advLink = document.querySelector('a[href*="analytics/tab-advanced_group"]') 
                             || document.querySelector('[aria-label*="nâng cao"]')
                             || document.querySelector('[aria-label*="Advanced"]')
                             || document.querySelector('#advanced-mode-button');
                return !!advLink;
            }""")
            return bool(found)
        except Exception:
            return False

    def capture_screenshot(self, destination_path: Path) -> Path:
        """Chụp ảnh màn hình lưu làm bằng chứng kiểm thử/đối chiếu."""
        destination_path = Path(destination_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(destination_path), full_page=False)
        return destination_path
