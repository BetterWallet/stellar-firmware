"""
Camera frame capture loop.

Supports either:
- USB webcam via OpenCV/V4L2, with ffmpeg fallback on Pi builds where pip
  OpenCV cannot open V4L2 devices
- Raspberry Pi ribbon camera via Picamera2/libcamera

Captures only when camera_state["enabled"] is set. Capture writes the newest
frame into a single-slot buffer for preview and QR decoding. A separate decode
worker always processes the newest available frame and drops stale ones.
"""
import asyncio
import logging
import subprocess
import time

import numpy as np

from config import (
    CAMERA_BACKEND,
    CAMERA_DEVICE_INDEX,
    CAMERA_FPS,
    CAMERA_HEIGHT,
    CAMERA_SCAN_ROTATION,
    CAMERA_WIDTH,
    RIBBON_CAMERA_HEIGHT,
    RIBBON_CAMERA_WIDTH,
    SCAN_AGGRESSIVE_AFTER_MISSES,
    SCAN_DECODE_MAX_SIZE,
    SCAN_DECODER_MODE,
    SCAN_FRAME_SKIP,
    SCAN_LOG_INTERVAL,
    SCAN_PREVIEW_ENABLED,
    SCAN_PREVIEW_FPS,
    SCAN_REGION_RATIO,
)
from camera.scanner import ScanResult, scan_frame

log = logging.getLogger(__name__)


def _usb_device_path() -> str:
    return f"/dev/video{CAMERA_DEVICE_INDEX}"


def _camera_dimensions() -> tuple[int, int]:
    if CAMERA_BACKEND.lower() == "ribbon":
        return RIBBON_CAMERA_WIDTH, RIBBON_CAMERA_HEIGHT
    return CAMERA_WIDTH, CAMERA_HEIGHT


def _open_usb_camera():
    import cv2
    capture_width, capture_height = _camera_dimensions()

    cap = cv2.VideoCapture(CAMERA_DEVICE_INDEX, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, capture_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, capture_height)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    if cap.isOpened():
        return ("usb-opencv", cap)

    # Fallback for Pi environments where the pip OpenCV wheel lacks working V4L2
    # capture support. ffmpeg reads from the V4L2 device directly and streams
    # raw RGB frames back over stdout.
    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-fflags", "nobuffer",
        "-f", "v4l2",
        "-input_format", "yuyv422",
        "-framerate", str(CAMERA_FPS),
        "-video_size", f"{capture_width}x{capture_height}",
        "-i", _usb_device_path(),
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "pipe:1",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=capture_width * capture_height * 3 * 2,
    )
    if proc.stdout is None:
        raise RuntimeError(f"Cannot stream frames from {_usb_device_path()}")
    return ("usb-ffmpeg", proc)


def _open_ribbon_camera():
    from picamera2 import Picamera2
    capture_width, capture_height = _camera_dimensions()

    cam = Picamera2()
    config = cam.create_preview_configuration(
        main={"size": (capture_width, capture_height), "format": "RGB888"}
    )
    cam.configure(config)
    cam.start()
    return ("ribbon", cam)


def _open_camera():
    backend = CAMERA_BACKEND.lower()
    if backend == "usb":
        return _open_usb_camera()
    if backend == "ribbon":
        return _open_ribbon_camera()
    raise RuntimeError(f"Unsupported CAMERA_BACKEND={CAMERA_BACKEND!r}")


def _read_frame(cap):
    """Read one frame; returns RGB numpy array or None on failure."""
    source, handle = cap
    capture_width, capture_height = _camera_dimensions()

    if source == "usb-opencv":
        import cv2

        ok, frame = handle.read()
        if not ok:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    if source == "usb-ffmpeg":
        frame_bytes = capture_width * capture_height * 3
        raw = handle.stdout.read(frame_bytes)
        if len(raw) != frame_bytes:
            return None
        return np.frombuffer(raw, dtype=np.uint8).reshape((capture_height, capture_width, 3))

    if source == "ribbon":
        return handle.capture_array()

    return None


def _close_camera(cap) -> None:
    source, handle = cap
    if source == "usb-opencv":
        handle.release()
    elif source == "usb-ffmpeg":
        handle.terminate()
        try:
            handle.wait(timeout=2)
        except Exception:
            handle.kill()
    elif source == "ribbon":
        handle.stop()
        handle.close()


async def camera_loop(scan_queue: asyncio.Queue, camera_state: dict) -> None:
    try:
        cap = _open_camera()
    except Exception as exc:
        log.warning("camera unavailable (%s) — camera_loop is a no-op", exc)
        return

    loop = asyncio.get_event_loop()
    frame_interval = 0.001
    preview_interval = 1.0 / max(1, SCAN_PREVIEW_FPS)
    capture_width, capture_height = _camera_dimensions()

    if CAMERA_BACKEND.lower() == "usb":
        camera_desc = _usb_device_path()
    else:
        camera_desc = "picamera2 ribbon camera"

    source_name = cap[0]
    stats = camera_state.setdefault("stats", {})
    preview_deadline = 0.0
    decode_seq = 0

    log.info(
        "camera_loop ready — %s via %s %dx%d @ %dfps (waiting for scan start)",
        camera_desc,
        source_name,
        capture_width,
        capture_height,
        CAMERA_FPS,
    )
    if CAMERA_BACKEND.lower() == "usb":
        log.warning("USB camera backend is best-effort only; ribbon camera is recommended for reliable animated QR scanning")

    def _reset_scan_stats() -> None:
        stats.clear()
        stats.update({
            "captured_frames": 0,
            "decoded_frames": 0,
            "dropped_frames": 0,
            "frame_read_failures": 0,
            "qr_hits": 0,
            "qr_misses": 0,
            "ur_fragments": 0,
            "ur_parts_accepted": 0,
            "ur_parts_rejected": 0,
            "last_progress": 0.0,
            "scanner_strategy": "-",
            "scan_started_at": time.monotonic(),
            "last_log_at": 0.0,
            "first_fragment_at": None,
        })

    def _maybe_log_stats(force: bool = False) -> None:
        now = time.monotonic()
        last_log_at = stats.get("last_log_at", 0.0)
        if not force and now - last_log_at < SCAN_LOG_INTERVAL:
            return
        stats["last_log_at"] = now
        elapsed = now - stats.get("scan_started_at", now)
        first_fragment = stats.get("first_fragment_at")
        time_to_first = "-" if first_fragment is None else f"{first_fragment - stats['scan_started_at']:.2f}s"
        log.info(
            "scan stats %.1fs captured=%s decoded=%s dropped=%s read_fail=%s qr_hits=%s qr_misses=%s ur_fragments=%s accepted=%s rejected=%s progress=%.0f%% strategy=%s first_fragment=%s",
            elapsed,
            stats.get("captured_frames", 0),
            stats.get("decoded_frames", 0),
            stats.get("dropped_frames", 0),
            stats.get("frame_read_failures", 0),
            stats.get("qr_hits", 0),
            stats.get("qr_misses", 0),
            stats.get("ur_fragments", 0),
            stats.get("ur_parts_accepted", 0),
            stats.get("ur_parts_rejected", 0),
            stats.get("last_progress", 0.0) * 100.0,
            stats.get("scanner_strategy", "-"),
            time_to_first,
        )

    async def _capture_worker() -> None:
        nonlocal preview_deadline, decode_seq
        frame_counter = 0
        while True:
            await camera_state["enabled"].wait()
            if stats.get("scan_started_at") is None:
                _reset_scan_stats()

            frame = await loop.run_in_executor(None, _read_frame, cap)
            now = time.monotonic()
            if frame is None:
                stats["frame_read_failures"] = stats.get("frame_read_failures", 0) + 1
                await asyncio.sleep(frame_interval)
                continue

            stats["captured_frames"] = stats.get("captured_frames", 0) + 1
            frame_counter += 1

            if SCAN_PREVIEW_ENABLED and now >= preview_deadline:
                camera_state["frame"] = frame
                camera_state["preview_seq"] = camera_state.get("preview_seq", 0) + 1
                preview_deadline = now + preview_interval

            if frame_counter % max(1, SCAN_FRAME_SKIP) != 0:
                stats["dropped_frames"] = stats.get("dropped_frames", 0) + 1
                await asyncio.sleep(frame_interval)
                continue

            if camera_state.get("scan_frame") is not None:
                stats["dropped_frames"] = stats.get("dropped_frames", 0) + 1

            decode_seq += 1
            camera_state["scan_frame"] = frame
            camera_state["scan_seq"] = decode_seq
            await asyncio.sleep(frame_interval)

    async def _decode_worker() -> None:
        last_decoded_seq = 0
        consecutive_misses = 0
        while True:
            await camera_state["enabled"].wait()

            seq = camera_state.get("scan_seq", 0)
            frame = camera_state.get("scan_frame")
            if frame is None or seq == last_decoded_seq:
                await asyncio.sleep(frame_interval)
                continue

            last_decoded_seq = seq
            camera_state["scan_frame"] = None
            aggressive = consecutive_misses >= SCAN_AGGRESSIVE_AFTER_MISSES
            result: ScanResult = await loop.run_in_executor(
                None,
                lambda: scan_frame(
                    frame,
                    rotation=CAMERA_SCAN_ROTATION,
                    roi_ratio=SCAN_REGION_RATIO,
                    decoder_mode=SCAN_DECODER_MODE,
                    aggressive=aggressive,
                    decode_max_size=SCAN_DECODE_MAX_SIZE,
                ),
            )
            stats["decoded_frames"] = stats.get("decoded_frames", 0) + 1
            stats["scanner_strategy"] = result.strategy

            if result.fragments:
                stats["qr_hits"] = stats.get("qr_hits", 0) + 1
                stats["ur_fragments"] = stats.get("ur_fragments", 0) + len(result.fragments)
                if stats.get("first_fragment_at") is None:
                    stats["first_fragment_at"] = time.monotonic()
                consecutive_misses = 0
                for fragment in result.fragments:
                    if scan_queue.full():
                        try:
                            scan_queue.get_nowait()
                            stats["dropped_frames"] = stats.get("dropped_frames", 0) + 1
                        except asyncio.QueueEmpty:
                            pass
                    await scan_queue.put(fragment)
            else:
                if result.qr_seen:
                    stats["qr_hits"] = stats.get("qr_hits", 0) + 1
                else:
                    stats["qr_misses"] = stats.get("qr_misses", 0) + 1
                consecutive_misses += 1

            _maybe_log_stats()

    async def _session_monitor() -> None:
        nonlocal preview_deadline
        last_enabled = False
        while True:
            enabled = camera_state["enabled"].is_set()
            if enabled and not last_enabled:
                preview_deadline = 0.0
                camera_state["frame"] = None
                camera_state["scan_frame"] = None
                _reset_scan_stats()
            elif not enabled and last_enabled:
                camera_state["frame"] = None
                camera_state["scan_frame"] = None
                _maybe_log_stats(force=True)
            last_enabled = enabled
            await asyncio.sleep(0.05)

    try:
        await asyncio.gather(_session_monitor(), _capture_worker(), _decode_worker())
    finally:
        _maybe_log_stats(force=True)
        _close_camera(cap)
