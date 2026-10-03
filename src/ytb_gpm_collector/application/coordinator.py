"""Worker Thread Pool & Concurrency Queue Manager (Task 4.6).

Điều phối thu thập dữ liệu đa luồng (Multi-threading Concurrency Coordinator):
1. Quản lý hàng đợi luân phiên: chạy tối đa N luồng cùng lúc (N từ 1 đến 10).
2. Khi bất kỳ profile nào hoàn thành (hoặc gặp lỗi), lập tức đóng profile đó an toàn
   và bốc ngay profile tiếp theo trong hàng đợi vào đúng worker slot vừa trống.
3. Bắn tín hiệu Signal cập nhật giao diện mượt mà:
   - Tiến trình tổng thể % (X/Y profile hoàn thành).
   - Trạng thái từng luồng (worker slots): Profile, Kênh, Bước thực hiện, Trạng thái, Thời gian chạy.
   - Ghi log thời gian thực chi tiết (INFO, SUCCESS, WARNING, ERROR) theo từng luồng.
4. Hỗ trợ dừng an toàn (Cancellation): dọn hàng đợi và đóng các trình duyệt đang chạy.
5. Hỗ trợ hàm worker tùy biến (injectable worker_fn) để kiểm thử tự động độc lập.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ytb_gpm_collector.domain.models import GpmProfile, RunHistoryRecord, ChannelCache
from ytb_gpm_collector.integrations.gpm.client import GpmClient
from ytb_gpm_collector.integrations.storage.history import LocalStorage, HistoryStorage
from ytb_gpm_collector.integrations.storage.runs import create_run_directory, build_run_reports
from ytb_gpm_collector.integrations.exports.normalize import normalize_run_directory

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. PROFILE WORKER THREAD
# ==============================================================================

class ProfileWorker(QThread):
    """
    Worker Thread chạy độc lập trên một luồng hệ điều hành riêng,
    xử lý trọn gói quy trình thu thập cho 1 Profile GPM:
    GPM API -> CDP -> Studio -> Export -> Normalize -> Report -> Close Profile.
    """

    # Signals cập nhật về Coordinator & UI
    # (worker_idx, profile_name, channel_name, step, status, elapsed)
    status_updated = Signal(int, str, str, str, str, str)
    # (level, message)
    log_emitted = Signal(str, str)
    # (worker_idx, profile_id, success, message)
    worker_finished = Signal(int, str, bool, str)

    def __init__(
        self,
        worker_idx: int,
        profile: GpmProfile,
        config: Dict[str, Any],
        gpm_client: GpmClient,
        history_storage: HistoryStorage,
        runs_dir: Optional[Path] = None,
        timeout_seconds: float = 60.0,
        worker_fn: Optional[Callable] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.worker_idx = worker_idx
        self.profile = profile
        self.config = config
        self.gpm_client = gpm_client
        self.history_storage = history_storage
        self.runs_dir = Path(runs_dir or "runs").resolve()
        self.timeout_seconds = timeout_seconds
        self.worker_fn = worker_fn
        self._is_aborted = False

    def abort(self) -> None:
        """Đánh dấu dừng luồng khẩn cấp."""
        self._is_aborted = True

    def _format_elapsed(self, start_time: float) -> str:
        """Định dạng thời gian trôi qua dạng MM:SS."""
        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)
        return f"{mins:02d}:{secs:02d}"

    def run(self) -> None:
        """Thực thi toàn bộ quy trình thu thập dữ liệu."""
        start_time = time.time()
        p_name = self.profile.name
        w_id = self.worker_idx + 1

        # Nếu có worker_fn truyền vào (dùng cho test tự động)
        if self.worker_fn is not None:
            try:
                self.worker_fn(self)
                return
            except Exception as ex:
                logger.error("Lỗi trong custom worker_fn: %s", ex)
                self.worker_finished.emit(self.worker_idx, self.profile.id, False, str(ex))
                return

        # Quy trình chuẩn với GPM và Playwright
        channel_name = self.profile.channel_name or "Đang nhận diện..."
        channel_id = self.profile.channel_id or ""
        started_at = datetime.now().isoformat()
        period_preset = self.config.get("analytics_period", "28_days")
        video_count = 0
        run_storage = None
        start_res = None

        try:
            # -----------------------------------------------------------------
            # Bước 1: Khởi động Profile GPM
            # -----------------------------------------------------------------
            if self._is_aborted:
                raise InterruptedError("Tác vụ bị hủy bởi người dùng")

            self.status_updated.emit(
                self.worker_idx, p_name, channel_name,
                "Đang khởi động trình duyệt GPM...", "Đang chạy",
                self._format_elapsed(start_time),
            )
            proxy_info = self.profile.raw_proxy or "Trực tiếp (Không proxy)"
            self.log_emitted.emit("INFO", f"[Luồng {w_id}] Đang mở Profile '{p_name}' (Proxy: {proxy_info})...")

            start_res = self.gpm_client.start_profile(self.profile.id, window_scale=0.85)
            if not start_res.success:
                raise RuntimeError(start_res.message or "GPM API không khởi động được profile")

            self.log_emitted.emit("INFO", f"[Luồng {w_id}] Profile '{p_name}' đã mở. Cổng CDP: {start_res.remote_debugging_address}")

            if self._is_aborted:
                raise InterruptedError("Tác vụ bị hủy bởi người dùng")

            # -----------------------------------------------------------------
            # Bước 2 & 3: Kết nối Playwright CDP và Truy cập YouTube Studio
            # -----------------------------------------------------------------
            from ytb_gpm_collector.integrations.studio.session import StudioSession
            from ytb_gpm_collector.integrations.studio.pages.analytics import StudioAnalyticsPage

            self.status_updated.emit(
                self.worker_idx, p_name, channel_name,
                "Kết nối Playwright CDP & Studio...", "Đang chạy",
                self._format_elapsed(start_time),
            )

            with StudioSession(start_res, timeout_seconds=self.timeout_seconds) as session:
                page = session.get_or_create_page()
                analytics_page = StudioAnalyticsPage(page, timeout_seconds=self.timeout_seconds)

                # Nhận diện kênh
                self.log_emitted.emit("INFO", f"[Luồng {w_id}] Đang truy cập YouTube Studio của '{p_name}'...")
                identity = analytics_page.navigate_to_studio()
                channel_name = identity.channel_name
                channel_id = identity.channel_id

                self.status_updated.emit(
                    self.worker_idx, p_name, channel_name,
                    f"Nhận diện kênh: {channel_name}", "Đang chạy",
                    self._format_elapsed(start_time),
                )
                self.log_emitted.emit("SUCCESS", f"[Luồng {w_id}] Nhận diện kênh thành công: '{channel_name}' (ID: {channel_id})")

                # Lưu cache kênh vào SQLite
                self.history_storage.save_channel_cache(
                    ChannelCache(
                        profile_id=self.profile.id,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        is_authenticated=True,
                        last_collected_at=datetime.now().isoformat(),
                    )
                )

                if self._is_aborted:
                    raise InterruptedError("Tác vụ bị hủy bởi người dùng")

                # -------------------------------------------------------------
                # Bước 4: Tạo thư mục Run & Xuất báo cáo Studio
                # -------------------------------------------------------------
                self.status_updated.emit(
                    self.worker_idx, p_name, channel_name,
                    "Xuất báo cáo YouTube Studio...", "Đang chạy",
                    self._format_elapsed(start_time),
                )

                run_storage = create_run_directory(
                    channel_name=channel_name,
                    channel_id=channel_id,
                    period_preset=period_preset,
                    base_dir=self.runs_dir,
                )
                self.log_emitted.emit("INFO", f"[Luồng {w_id}] Khởi tạo thư mục kết quả: {run_storage.run_dir.name}")

                # Xuất báo cáo Analytics
                export_res = analytics_page.export_channel_analytics(
                    run_storage=run_storage,
                    date_preset=period_preset,
                    collection_depth=self.config.get("collection_depth", "standard"),
                )
                self.log_emitted.emit("INFO", f"[Luồng {w_id}] Tải file gốc từ Studio thành công.")

            # -----------------------------------------------------------------
            # Bước 5: Chuẩn hóa dữ liệu & Sinh báo cáo AI
            # -----------------------------------------------------------------
            if self._is_aborted:
                raise InterruptedError("Tác vụ bị hủy bởi người dùng")

            self.status_updated.emit(
                self.worker_idx, p_name, channel_name,
                "Chuẩn hóa dữ liệu & Sinh báo cáo AI...", "Đang chạy",
                self._format_elapsed(start_time),
            )

            if run_storage:
                norm_res = normalize_run_directory(run_storage.run_dir)
                video_count = norm_res.videos_count
                build_run_reports(run_storage.run_dir)

            self.log_emitted.emit("SUCCESS", f"[Luồng {w_id}] Chuẩn hóa hoàn tất {video_count} video. Đã sinh README.md & quality_report.json.")

            # -----------------------------------------------------------------
            # Bước 6: Lưu lịch sử chạy vào SQLite
            # -----------------------------------------------------------------
            if run_storage:
                self.history_storage.save_run_record(
                    RunHistoryRecord(
                        run_id=run_storage.run_id,
                        profile_id=self.profile.id,
                        profile_name=p_name,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        period=period_preset,
                        video_count=video_count,
                        status="success",
                        output_dir=str(run_storage.run_dir),
                        started_at=started_at,
                        finished_at=datetime.now().isoformat(),
                    )
                )

            # Cập nhật hoàn tất
            elapsed = self._format_elapsed(start_time)
            self.status_updated.emit(
                self.worker_idx, p_name, channel_name,
                f"Hoàn tất ({video_count} video)", "✅ Xong", elapsed,
            )
            self.log_emitted.emit("SUCCESS", f"[SUCCESS] [Luồng {w_id}] Profile '{p_name}' hoàn tất thành công. Đã đóng profile an toàn.")
            self.worker_finished.emit(self.worker_idx, self.profile.id, True, "Thành công")

        except Exception as ex:
            error_msg = str(ex)
            elapsed = self._format_elapsed(start_time)
            logger.error("Lỗi luồng %d profile %s: %s", w_id, p_name, error_msg)

            self.status_updated.emit(
                self.worker_idx, p_name, channel_name,
                f"Lỗi: {error_msg[:35]}", "❌ Lỗi", elapsed,
            )
            self.log_emitted.emit("ERROR", f"[Luồng {w_id}] Lỗi xử lý Profile '{p_name}': {error_msg}")

            # Lưu lịch sử thất bại nếu đã tạo run_storage
            if run_storage:
                try:
                    self.history_storage.save_run_record(
                        RunHistoryRecord(
                            run_id=run_storage.run_id,
                            profile_id=self.profile.id,
                            profile_name=p_name,
                            channel_id=channel_id or None,
                            channel_name=channel_name or None,
                            period=period_preset,
                            video_count=video_count,
                            status="failed",
                            output_dir=str(run_storage.run_dir),
                            started_at=started_at,
                            finished_at=datetime.now().isoformat(),
                            error_message=error_msg,
                        )
                    )
                except Exception:
                    pass

            self.worker_finished.emit(self.worker_idx, self.profile.id, False, error_msg)

        finally:
            # Luôn luôn đóng Profile GPM sau khi xong hoặc lỗi
            try:
                self.gpm_client.close_profile(self.profile.id)
            except Exception as ce:
                logger.debug("Lỗi khi đóng profile GPM: %s", ce)


# ==============================================================================
# 2. HÀNG ĐỢI ĐA LUỒNG & BỘ ĐIỀU PHỐI (CONCURRENCY COORDINATOR)
# ==============================================================================

class CollectionCoordinator(QObject):
    """
    Bộ điều phối hàng đợi và luồng xử lý thu thập dữ liệu (Task 4.6).
    
    Cơ chế hoạt động:
    - Nhận danh sách M profile cần cào và số luồng song song N.
    - Tạo N worker slots.
    - Luân phiên bốc profile từ hàng đợi để chạy tối đa N profile đồng thời.
    - Profile nào xong lập tức đóng profile và bốc tiếp profile mới vào slot trống.
    - Cập nhật tiến trình tổng % và phát tín hiệu an toàn luồng lên UI.
    """

    # Signals phát ra cho UI
    # (completed_count, total_count, status_text)
    overall_progress = Signal(int, int, str)
    # (worker_idx, profile_name, channel_name, step, status, elapsed)
    worker_status = Signal(int, str, str, str, str, str)
    # (level, message)
    log_message = Signal(str, str)
    # (total, concurrency)
    campaign_started = Signal(int, int)
    # (total, success_count, failed_count)
    campaign_finished = Signal(int, int, int)

    def __init__(
        self,
        gpm_client: Optional[GpmClient] = None,
        history_storage: Optional[HistoryStorage] = None,
        runs_dir: Optional[Path] = None,
        timeout_seconds: float = 60.0,
        worker_fn: Optional[Callable] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.gpm_client = gpm_client or GpmClient()
        self.history_storage = history_storage or HistoryStorage()
        self.runs_dir = Path(runs_dir or "runs").resolve()
        self.timeout_seconds = timeout_seconds
        self.worker_fn = worker_fn  # Injectable cho unit test

        # Trạng thái hàng đợi và luồng
        self.queue: List[GpmProfile] = []
        self.active_workers: Dict[int, ProfileWorker] = {}
        self.available_slots: List[int] = []

        self.concurrency: int = 2
        self.total_profiles: int = 0
        self.completed_count: int = 0
        self.success_count: int = 0
        self.failed_count: int = 0

        self.is_running: bool = False
        self.is_cancelled: bool = False
        self.config: Dict[str, Any] = {}

    @property
    def running(self) -> bool:
        """Kiểm tra xem Coordinator có đang chạy thu thập không."""
        return self.is_running

    def start(self, config: Dict[str, Any], profiles: List[GpmProfile]) -> bool:
        """
        Bắt đầu chiến dịch thu thập đa luồng.
        
        Args:
            config: Từ điển cấu hình từ CollectorPage (concurrency, period, video_limit...)
            profiles: Danh sách các GpmProfile được chọn.
        """
        if self.is_running:
            logger.warning("Chiến dịch thu thập đang chạy dở, không thể khởi động lại.")
            return False

        if not profiles:
            logger.warning("Danh sách profile cần chạy rỗng.")
            return False

        self.config = config
        self.concurrency = max(1, min(10, int(config.get("concurrency", 2))))
        self.queue = list(profiles)
        self.total_profiles = len(profiles)
        self.completed_count = 0
        self.success_count = 0
        self.failed_count = 0

        self.is_running = True
        self.is_cancelled = False
        self.active_workers.clear()
        self.available_slots = list(range(self.concurrency))

        self.campaign_started.emit(self.total_profiles, self.concurrency)
        self.log_message.emit(
            "INFO",
            f"🚀 [HỆ THỐNG] Bắt đầu chiến dịch thu thập: {self.total_profiles} Profile | {self.concurrency} Luồng song song | Kỳ: {config.get('analytics_period', '28_days')}",
        )
        self.overall_progress.emit(
            0, self.total_profiles,
            f"Đang chạy (0/{self.total_profiles} profile hoàn thành)...",
        )

        # Khởi động các worker đầu tiên cho các slot trống
        self._dispatch_next_workers()
        return True

    def stop(self) -> None:
        """Dừng chiến dịch thu thập an toàn."""
        if not self.is_running:
            return

        self.is_cancelled = True
        queued_count = len(self.queue)
        self.queue.clear()

        self.log_message.emit(
            "WARNING",
            f"⚠️ [HỆ THỐNG] Đã nhận lệnh dừng từ người dùng. Hủy bỏ {queued_count} profile trong hàng đợi. Đang đóng các luồng đang chạy...",
        )
        self.overall_progress.emit(
            self.completed_count, self.total_profiles,
            "Đang dừng các luồng thu thập an toàn...",
        )

        # Báo cho các worker đang chạy biết để dừng
        for slot_idx, worker in list(self.active_workers.items()):
            worker.abort()

        # Nếu không có worker nào đang chạy
        if not self.active_workers:
            self._finish_campaign()

    def _dispatch_next_workers(self) -> None:
        """Luân phiên bốc profile từ hàng đợi để chạy trên các slot trống."""
        if self.is_cancelled:
            return

        while self.available_slots and self.queue:
            slot_idx = self.available_slots.pop(0)
            profile = self.queue.pop(0)

            worker = ProfileWorker(
                worker_idx=slot_idx,
                profile=profile,
                config=self.config,
                gpm_client=self.gpm_client,
                history_storage=self.history_storage,
                runs_dir=self.runs_dir,
                timeout_seconds=self.timeout_seconds,
                worker_fn=self.worker_fn,
                parent=self,
            )

            # Kết nối tín hiệu an toàn từ worker về Coordinator
            worker.status_updated.connect(self._on_worker_status_updated)
            worker.log_emitted.connect(self._on_worker_log_emitted)
            worker.worker_finished.connect(self._on_worker_finished)

            self.active_workers[slot_idx] = worker
            worker.start()

    @Slot(int, str, str, str, str, str)
    def _on_worker_status_updated(
        self,
        worker_idx: int,
        profile_name: str,
        channel_name: str,
        step: str,
        status: str,
        elapsed: str,
    ) -> None:
        """Chuyển tiếp trạng thái worker lên giao diện."""
        self.worker_status.emit(worker_idx, profile_name, channel_name, step, status, elapsed)

    @Slot(str, str)
    def _on_worker_log_emitted(self, level: str, message: str) -> None:
        """Chuyển tiếp log từ worker lên giao diện."""
        self.log_message.emit(level, message)

    @Slot(int, str, bool, str)
    def _on_worker_finished(
        self,
        worker_idx: int,
        profile_id: str,
        success: bool,
        message: str,
    ) -> None:
        """Xử lý khi một worker slot hoàn tất một profile."""
        # Giải phóng slot
        if worker_idx in self.active_workers:
            worker = self.active_workers.pop(worker_idx)
            worker.quit()
            worker.wait(500)

        self.available_slots.append(worker_idx)
        self.completed_count += 1
        if success:
            self.success_count += 1
        else:
            self.failed_count += 1

        # Cập nhật tiến trình tổng
        status_text = f"Đang chạy ({self.completed_count}/{self.total_profiles} hoàn thành)..."
        self.overall_progress.emit(self.completed_count, self.total_profiles, status_text)

        # Nếu chưa bị dừng và còn profile trong hàng đợi -> bốc tiếp profile mới
        if not self.is_cancelled and self.queue:
            self._dispatch_next_workers()
        elif not self.active_workers:
            # Tất cả các worker đã hoàn thành hoặc hàng đợi đã hết
            self._finish_campaign()

    def _finish_campaign(self) -> None:
        """Kết thúc toàn bộ chiến dịch thu thập."""
        self.is_running = False

        if self.is_cancelled:
            msg = f"Đã dừng: {self.success_count} thành công, {self.failed_count} lỗi, {self.total_profiles - self.completed_count} bị hủy."
            self.log_message.emit("WARNING", f"⏹️ [HỆ THỐNG] {msg}")
            self.overall_progress.emit(self.completed_count, self.total_profiles, msg)
        else:
            msg = f"Hoàn tất 100%: {self.success_count}/{self.total_profiles} profile thành công"
            if self.failed_count > 0:
                msg += f" ({self.failed_count} profile gặp lỗi)"
            self.log_message.emit("SUCCESS", f"🎉 [HỆ THỐNG] {msg}")
            self.overall_progress.emit(self.total_profiles, self.total_profiles, msg)

        self.campaign_finished.emit(self.total_profiles, self.success_count, self.failed_count)
