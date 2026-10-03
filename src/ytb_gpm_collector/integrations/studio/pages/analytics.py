"""YouTube Studio Analytics and Channel Navigation Page Object."""

import logging
import re
import time
import zipfile
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from ytb_gpm_collector.domain.models import ChannelIdentity, StudioExportResult
from ytb_gpm_collector.domain.errors import (
    StudioAuthenticationError,
    StudioNavigationError,
    ReportExportError,
)
from ytb_gpm_collector.integrations.storage.runs import RunDirectory

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

    # =========================================================================
    # Task 2.3: Bộ chọn khoảng thời gian, Chế độ nâng cao & Xuất báo cáo Studio
    # =========================================================================

    def select_date_range(self, preset: str = "28_days", timeout_seconds: float = 10.0) -> bool:
        """
        Chọn khoảng thời gian phân tích số liệu trên YouTube Studio tiếng Việt.
        
        Các preset hỗ trợ:
        - '28_days' / '28d': 28 ngày qua (mặc định)
        - '7_days' / '7d': 7 ngày qua
        - '90_days' / '90d': 90 ngày qua
        - '365_days' / '365d': 365 ngày qua
        - 'all_time' / 'lifetime': Toàn thời gian
        
        Args:
            preset: Mã khoảng thời gian cần chọn.
            timeout_seconds: Thời gian chờ tối đa.
        """
        preset_map = {
            "28_days": "28 ngày qua",
            "28d": "28 ngày qua",
            "7_days": "7 ngày qua",
            "7d": "7 ngày qua",
            "90_days": "90 ngày qua",
            "90d": "90 ngày qua",
            "365_days": "365 ngày qua",
            "365d": "365 ngày qua",
            "all_time": "Toàn thời gian",
            "lifetime": "Toàn thời gian",
        }
        target_label = preset_map.get(preset, "28 ngày qua")
        logger.info(f"Đang thiết lập khoảng thời gian: '{target_label}' (preset: {preset})...")

        try:
            # 1. Kiểm tra xem khoảng thời gian hiện tại đã đúng chưa
            trigger = self.page.query_selector(
                '#picker-trigger, yta-time-picker #picker-trigger, ytcp-text-dropdown-trigger'
            )
            if trigger:
                current_text = trigger.inner_text() or ""
                if target_label.lower() in current_text.lower():
                    logger.info(f"Khoảng thời gian hiện tại đã là '{target_label}'. Không cần đổi.")
                    return True

                # 2. Mở dropdown bộ chọn ngày
                trigger.click()
                time.sleep(1.0)

                # 3. Chọn item tương ứng trong menu
                item_selector = (
                    f'tp-yt-paper-item:has-text("{target_label}"), '
                    f'[role="menuitem"]:has-text("{target_label}")'
                )
                self.page.wait_for_selector(item_selector, timeout=int(timeout_seconds * 1000))
                self.page.click(item_selector)
                logger.info(f"Đã chọn khoảng thời gian: '{target_label}'. Đang chờ trang cập nhật...")

                # Đóng bất kỳ overlay menu còn sót lại
                try:
                    self.page.keyboard.press("Escape")
                except Exception:
                    pass

                # Chờ biểu đồ và dữ liệu tải lại
                time.sleep(2.0)
                return True

        except Exception as e:
            logger.warning(f"Không thể chọn khoảng thời gian '{target_label}' qua UI: {e}")

        return False

    def open_advanced_mode(self, timeout_seconds: float = 20.0) -> bool:
        """
        Mở 'Chế độ xem nâng cao' (Advanced Mode) trong YouTube Studio Analytics.
        
        Bao gồm cơ chế click nút UI và phương án dự phòng điều hướng URL trực tiếp.
        """
        logger.info("Đang mở 'Chế độ xem nâng cao' (Advanced Mode)...")

        # Kiểm tra nếu đã ở trong Chế độ nâng cao
        if "/explore" in self.page.url:
            export_btn = self.page.query_selector('#export-button, [aria-label*="Xuất"], [aria-label*="Export"]')
            if export_btn:
                logger.info("Đã ở sẵn trong giao diện Chế độ xem nâng cao.")
                return True

        # Đóng bất kỳ overlay popup nào còn sót lại
        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.3)
        except Exception:
            pass

        # Phương án 1: Click nút "Chế độ nâng cao" trên giao diện
        try:
            adv_selectors = [
                '#advanced-analytics',
                'button[aria-label*="nâng cao"]',
                'button:has-text("Chế độ nâng cao")',
                'a:has-text("Chế độ nâng cao")',
                'ytcp-button:has-text("Chế độ nâng cao")',
                '[aria-label*="Advanced"]',
                'a[href*="/explore"]',
            ]
            for sel in adv_selectors:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click(timeout=3000)
                    break
            else:
                self.page.click('#advanced-analytics, [aria-label*="nâng cao"]', timeout=3000)

            # Chờ nút Xuất hoặc trang Explore xuất hiện
            self.page.wait_for_selector(
                '#export-button, [aria-label*="Xuất"], [aria-label*="Export"], yta-explore-page',
                timeout=10000,
            )
            time.sleep(1.5)
            logger.info("Mở Chế độ xem nâng cao thành công qua click nút UI.")
            return True

        except Exception as e:
            logger.warning(f"Click nút Chế độ nâng cao thất bại ({e}). Thử điều hướng URL explore trực tiếp...")

        # Phương án 2 (Dự phòng vững chắc): Điều hướng trực tiếp URL explore
        try:
            target_id = self.channel_id
            if not target_id:
                identity = self.navigate_to_studio()
                target_id = identity.channel_id

            direct_explore_url = (
                f"https://studio.youtube.com/channel/{target_id}/analytics/tab-overview/period-default/explore"
                f"?entity_type=CHANNEL&entity_id={target_id}&time_period=4_weeks"
                f"&explore_type=TABLE_AND_CHART&metric=EXTERNAL_VIEWS&granularity=DAY"
                f"&t_metrics=EXTERNAL_VIEWS&t_metrics=EXTERNAL_WATCH_TIME"
                f"&t_metrics=SUBSCRIBERS_NET_CHANGE&t_metrics=TOTAL_ESTIMATED_EARNINGS"
                f"&t_metrics=VIDEO_THUMBNAIL_IMPRESSIONS&t_metrics=VIDEO_THUMBNAIL_IMPRESSIONS_VTR"
                f"&dimension=VIDEO&o_column=EXTERNAL_VIEWS&o_direction=ANALYTICS_ORDER_DIRECTION_DESC"
            )
            self.page.goto(direct_explore_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            self.page.wait_for_selector(
                '#export-button, [aria-label*="Xuất"], [aria-label*="Export"], yta-explore-page',
                timeout=int(timeout_seconds * 1000),
            )
            time.sleep(1.5)
            logger.info("Mở Chế độ xem nâng cao thành công qua URL explore.")
            return True

        except Exception as e:
            raise ReportExportError(
                f"Không thể mở Chế độ xem nâng cao trong YouTube Studio sau cả 2 phương án: {e}"
            ) from e

    def export_report(
        self,
        destination_dir: Path,
        timeout_seconds: float = 30.0,
        extract_zip: bool = True,
    ) -> Path:
        """
        Thao tác bấm nút Xuất báo cáo (Export) và bắt sự kiện tải file nguyên vẹn vào destination_dir.
        
        Args:
            destination_dir: Thư mục lưu file gốc (ví dụ: runs/<run_id>/raw/).
            timeout_seconds: Thời gian chờ tải file tối đa.
            extract_zip: Nếu file tải về là .zip, tự động giải nén các file .csv kèm theo để sẵn sàng cho Phase 3.
            
        Returns:
            Path: Đường dẫn tới file tải về nguyên vẹn trong destination_dir.
            
        Raises:
            ReportExportError: Nếu không tìm thấy nút xuất hoặc tải file thất bại.
        """
        dest_path = Path(destination_dir)
        dest_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Đang chuẩn bị xuất báo cáo vào: {dest_path}...")

        # 1. Tìm và click nút Xuất
        export_btn_selector = '#export-button, [aria-label*="Xuất"], [aria-label*="Export"]'
        try:
            self.page.wait_for_selector(export_btn_selector, timeout=10000)
            self.page.click(export_btn_selector)
            time.sleep(1.0)
        except Exception as e:
            raise ReportExportError(f"Không thể tìm thấy hoặc click nút Xuất báo cáo: {e}") from e

        # 2. Lựa chọn định dạng xuất (.csv hoặc Excel)
        option_selector = (
            'tp-yt-paper-item:has-text(".csv"), '
            '[role="menuitem"]:has-text(".csv"), '
            'tp-yt-paper-item:has-text("Excel"), '
            '[role="menuitem"]:has-text("Excel")'
        )

        try:
            self.page.wait_for_selector(option_selector, timeout=5000)
        except Exception as e:
            raise ReportExportError(f"Menu tùy chọn xuất không xuất hiện sau khi click nút Xuất: {e}") from e

        # 3. Lắng nghe sự kiện download và click vào tùy chọn xuất
        logger.info("Đang kích hoạt tải file và bắt sự kiện download...")
        try:
            with self.page.expect_download(timeout=int(timeout_seconds * 1000)) as download_info:
                self.page.click(option_selector)

            download = download_info.value
            suggested_name = download.suggested_filename
            saved_file = dest_path / suggested_name

            # Lưu nguyên vẹn file tải về
            download.save_as(str(saved_file))
            file_size = saved_file.stat().st_size
            logger.info(
                f"Đã bắt và lưu nguyên vẹn file xuất: '{saved_file.name}' "
                f"({file_size:,} bytes) tại {saved_file}"
            )

            # 4. Nếu là file zip, giải nén các file CSV bên trong
            if extract_zip and saved_file.suffix.lower() == ".zip":
                try:
                    with zipfile.ZipFile(saved_file, "r") as zf:
                        zf.extractall(dest_path)
                    logger.info(f"Đã giải nén các file báo cáo CSV vào {dest_path} cho Phase 3.")
                except Exception as ze:
                    logger.warning(f"Lưu ý: Không thể giải nén zip ({ze}), nhưng file gốc .zip vẫn an toàn.")

            return saved_file

        except Exception as e:
            raise ReportExportError(f"Lỗi trong quá trình bắt sự kiện tải file báo cáo: {e}") from e

    def export_channel_analytics(
        self,
        run_storage: RunDirectory,
        date_preset: str = "28_days",
    ) -> StudioExportResult:
        """
        Quy trình trọn vẹn của Task 2.3:
        1. Điều hướng tới trang Số liệu phân tích (Analytics).
        2. Chọn khoảng thời gian (mặc định 28 ngày qua).
        3. Chụp ảnh biểu đồ tổng quan đối chiếu lưu vào runs/<run_id>/evidence/.
        4. Mở Chế độ xem nâng cao (Advanced Mode).
        5. Chụp ảnh bảng Chế độ nâng cao làm bằng chứng đối chiếu.
        6. Bấm nút Xuất và lưu nguyên vẹn file vào runs/<run_id>/raw/.
        7. Cập nhật manifest.json và trả về StudioExportResult.
        """
        logger.info(
            f"=== Bắt đầu quy trình xuất báo cáo cho kênh '{self.channel_name}' (Run ID: {run_storage.run_id}) ==="
        )

        # 1. Đảm bảo đã ở trong trang Analytics
        if "/analytics" not in self.page.url:
            self.navigate_to_analytics()

        # 2. Chọn khoảng thời gian
        self.select_date_range(preset=date_preset)

        # 3. Chụp ảnh biểu đồ tổng quan đối chiếu
        overview_evidence_path = run_storage.evidence_dir / "analytics_overview.png"
        self.capture_screenshot(overview_evidence_path)
        logger.info(f"Đã chụp ảnh biểu đồ tổng quan: {overview_evidence_path}")

        # 4. Mở Chế độ xem nâng cao
        self.open_advanced_mode()

        # 5. Chụp ảnh Chế độ xem nâng cao
        adv_evidence_path = run_storage.evidence_dir / "advanced_table.png"
        self.capture_screenshot(adv_evidence_path)
        logger.info(f"Đã chụp ảnh Chế độ xem nâng cao: {adv_evidence_path}")

        # 6. Bắt sự kiện tải file và lưu nguyên vẹn vào raw/
        raw_file = self.export_report(destination_dir=run_storage.raw_dir)

        # 7. Cập nhật manifest.json
        manifest_data = {
            "run_id": run_storage.run_id,
            "channel_id": self.channel_id or "",
            "channel_name": self.channel_name or "",
            "period": date_preset,
            "raw_file": str(raw_file.relative_to(run_storage.run_dir)),
            "evidence_overview": str(overview_evidence_path.relative_to(run_storage.run_dir)),
            "evidence_advanced": str(adv_evidence_path.relative_to(run_storage.run_dir)),
            "exported_at": datetime.now().isoformat(),
            "status": "exported",
            "schema_version": "1.0",
        }
        run_storage.save_manifest(manifest_data)

        export_res = StudioExportResult(
            success=True,
            channel_id=self.channel_id or "",
            channel_name=self.channel_name or "",
            date_preset=date_preset,
            raw_file_path=str(raw_file),
            evidence_image_path=str(overview_evidence_path),
            file_size_bytes=raw_file.stat().st_size,
            exported_at=manifest_data["exported_at"],
            message=f"Đã xuất báo cáo và chụp ảnh bằng chứng thành công vào {run_storage.run_dir}",
        )

        logger.info(f"=== Hoàn tất xuất báo cáo thành công [OK]: {export_res.message} ===")
        return export_res
