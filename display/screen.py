"""
Display loop: consumes RenderEvent from render_queue and drives the SPI framebuffer.

SDL's fbcon driver does not support 16-bit (RGB565) framebuffers, so we render
into an offscreen pygame Surface and write raw RGB565 bytes directly to /dev/fb1.

Touch/mouse input are read via X11 (preferred) or evdev fallback since SDL
input is unavailable with the offscreen video driver. Status LEDs are driven
based on current screen.
"""
import asyncio
import logging
import os

from config import (
    CAMERA_PREVIEW_ROTATION,
    DISPLAY_FB,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    SCAN_PREVIEW_ENABLED,
    SHOW_TOUCH_CURSOR,
    TOUCH_INPUT_BACKEND,
)
from state.states import ButtonEvent, PINEvent

log = logging.getLogger(__name__)

_TOUCH_DEVICE = "/dev/input/touchscreen"
_TOUCH_MAX_X  = 4095
_TOUCH_MAX_Y  = 4095

# LED screen → (green, red) mapping
_LED_MAP = {
    "idle":     (True,  False),
    "scanning": (True,  False),
    "result":   (True,  False),
    "setup":    (True,  False),
    "signing":  (True,  False),
    "confirm":  (True,  True),
    "pin":      (False, False),
    "wrong_pin":(False, True),
    "error":    (False, True),
    "show_import": (True, False),
}


def _init_pygame():
    import pygame
    os.environ["SDL_VIDEODRIVER"] = "offscreen"
    pygame.init()
    screen  = pygame.Surface((DISPLAY_WIDTH, DISPLAY_HEIGHT))
    fb_surf = pygame.Surface((DISPLAY_WIDTH, DISPLAY_HEIGHT), depth=16)
    return pygame, screen, fb_surf


def _flush(fb_surf, screen, fb):
    fb_surf.blit(screen, (0, 0))
    fb.seek(0)
    fb.write(fb_surf.get_buffer().raw)
    fb.flush()


def _update_leds(screen_name: str):
    """Set green/red LEDs based on current screen state."""
    try:
        import RPi.GPIO as GPIO
        from config import GPIO_LED_GREEN, GPIO_LED_RED
        green, red = _LED_MAP.get(screen_name, (False, False))
        GPIO.output(GPIO_LED_GREEN, GPIO.HIGH if green else GPIO.LOW)
        GPIO.output(GPIO_LED_RED,   GPIO.HIGH if red   else GPIO.LOW)
    except Exception:
        pass


def _build_camera_preview_surface(pygame, frame):
    """Convert a camera frame into a portrait, aspect-fit pygame surface."""
    h, w = frame.shape[:2]
    frame_surface = pygame.image.frombuffer(frame.tobytes(), (w, h), "RGB").copy()

    if CAMERA_PREVIEW_ROTATION:
        frame_surface = pygame.transform.rotate(frame_surface, CAMERA_PREVIEW_ROTATION)

    src_w, src_h = frame_surface.get_size()
    scale = min(DISPLAY_WIDTH / src_w, DISPLAY_HEIGHT / src_h)
    dst_w = max(1, int(src_w * scale))
    dst_h = max(1, int(src_h * scale))
    frame_surface = pygame.transform.scale(frame_surface, (dst_w, dst_h))

    x = (DISPLAY_WIDTH - dst_w) // 2
    y = (DISPLAY_HEIGHT - dst_h) // 2
    return frame_surface, (x, y)


def _find_touch_device():
    """Return path to the evdev touchscreen node, or None."""
    import evdev
    if os.path.exists(_TOUCH_DEVICE):
        return _TOUCH_DEVICE
    for path in evdev.list_devices():
        try:
            name = evdev.InputDevice(path).name.lower()
            if "ads7846" in name or "xpt2046" in name or "touch" in name:
                return path
        except Exception:
            continue
    return None


def _find_mouse_device():
    """Return path to the first mouse evdev node, or None."""
    import evdev
    from evdev import ecodes
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            caps = dev.capabilities()
            if ecodes.EV_REL in caps and ecodes.EV_KEY in caps:
                if ecodes.BTN_LEFT in caps[ecodes.EV_KEY]:
                    return path
        except Exception:
            continue
    return None


def _scale_axis(value: int, src_max: int, dst_max: int) -> int:
    if src_max <= 0 or dst_max <= 0:
        return 0
    return max(0, min(dst_max, int(value * dst_max / src_max)))


def _handle_click(pos: tuple[int, int], state: dict, event_queue: asyncio.Queue):
    """Handle a click/touch at screen position. Returns a coroutine to put event, or None."""
    ev = state["event"]
    if ev is None:
        return None

    s = ev.screen

    if s in ("pin", "wrong_pin"):
        from display import screens
        digit = screens.pin.hit_test(pos)
        if digit == "DEL":
            if state["pin_digits"]:
                state["pin_digits"].pop()
        elif digit == "OK":
            if state["pin_digits"]:
                pin_str = "".join(state["pin_digits"])
                state["pin_digits"] = []
                return event_queue.put(PINEvent(pin_str))
        elif digit is not None:
            state["pin_digits"].append(digit)

    elif s == "setup":
        return event_queue.put(ButtonEvent.CONFIRM)

    elif s == "confirm":
        # Left half → confirm, right half → reject
        if pos[0] < DISPLAY_WIDTH // 2:
            return event_queue.put(ButtonEvent.CONFIRM)
        else:
            return event_queue.put(ButtonEvent.REJECT)

    elif s == "idle":
        # Any click → start scanning
        return event_queue.put(ButtonEvent.CONFIRM)

    elif s == "scanning":
        # Any click during scanning → cancel
        return event_queue.put(ButtonEvent.REJECT)

    elif s in ("result", "error"):
        # Any click → advance
        return event_queue.put(ButtonEvent.CONFIRM)

    return None


async def display_loop(render_queue: asyncio.Queue, event_queue: asyncio.Queue, camera_state: dict) -> None:
    try:
        _pygame, screen, fb_surf = _init_pygame()
        fb = open(DISPLAY_FB, "rb+")
    except Exception as exc:
        log.warning("display init failed (%s) — display_loop is a no-op", exc)
        while True:
            await render_queue.get()
            return

    import pygame
    from display import screens
    from display.widgets import render_error, render_text_centered

    # Shared mutable state between render, touch, and mouse coroutines.
    # All run on the same asyncio thread, so no lock is needed.
    state = {
        "event":      None,
        "pin_digits": [],
        "qr_index":   0,
        "qr_frames":  [],
        "cursor":     (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2),
        "cursor_visible": False,
        "preview_seq": -1,
        "preview_surface": None,
        "preview_pos": (0, 0),
    }

    log.info("display_loop started — framebuffer=%s (RGB565 direct write)", DISPLAY_FB)

    async def _render_loop():
        from config import QR_DISPLAY_FPS
        while True:
            try:
                while True:
                    ev = render_queue.get_nowait()
                    state["event"] = ev
                    if ev.screen == "result":
                        state["qr_frames"] = ev.data.get("qr_frames", [])
                        state["qr_index"]  = 0
                    if ev.screen in ("pin", "locked"):
                        state["pin_digits"] = []
            except asyncio.QueueEmpty:
                pass

            ev = state["event"]
            if ev is None:
                await asyncio.sleep(0.016)
                continue

            screen.fill((0, 0, 0))
            s = ev.screen

            if s in ("pin", "wrong_pin"):
                screens.pin.render(screen, state["pin_digits"], wrong=(s == "wrong_pin"))
            elif s == "setup":
                screens.setup.render(screen, ev.data.get("words", []))
            elif s == "idle":
                screens.idle.render(screen, ev.data.get("address", ""))
            elif s == "scanning":
                frame = camera_state.get("frame")
                preview_seq = camera_state.get("preview_seq", -1)
                overlay = False
                if SCAN_PREVIEW_ENABLED and frame is not None:
                    if preview_seq != state["preview_seq"]:
                        state["preview_surface"], state["preview_pos"] = _build_camera_preview_surface(pygame, frame)
                        state["preview_seq"] = preview_seq
                    if state["preview_surface"] is not None:
                        screen.blit(state["preview_surface"], state["preview_pos"])
                        overlay = True
                screens.idle.render_scanning(
                    screen,
                    ev.data.get("progress", 0.0),
                    overlay=overlay,
                    preview_enabled=SCAN_PREVIEW_ENABLED,
                )
            elif s == "confirm":
                screens.confirm.render(screen, ev.data.get("fields", []))
            elif s == "signing":
                render_text_centered(screen, "Signing...", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2))
            elif s == "result":
                frames = state["qr_frames"]
                if frames:
                    screens.result.render(screen, frames[state["qr_index"] % len(frames)])
            elif s == "error":
                render_error(screen, ev.data.get("message", "Unknown error"))
            else:
                render_text_centered(screen, s, (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2))

            # Draw mouse cursor if active
            if state["cursor_visible"]:
                cx, cy = state["cursor"]
                pygame.draw.circle(screen, (255, 255, 0), (cx, cy), 5, 1)
                pygame.draw.line(screen, (255, 255, 0), (cx - 8, cy), (cx + 8, cy), 1)
                pygame.draw.line(screen, (255, 255, 0), (cx, cy - 8), (cx, cy + 8), 1)

            _flush(fb_surf, screen, fb)
            _update_leds(s)

            if s == "result" and state["qr_frames"]:
                state["qr_index"] += 1
                await asyncio.sleep(1.0 / QR_DISPLAY_FPS)
            else:
                await asyncio.sleep(1.0 / 30)

    async def _touch_loop_x11() -> bool:
        try:
            from Xlib import X, display as xdisplay
        except Exception:
            log.info("python-xlib unavailable — cannot use x11 touch input")
            return False

        display_name = os.environ.get("DISPLAY", ":0")
        try:
            dpy = xdisplay.Display(display_name)
        except Exception as exc:
            log.info("x11 display unavailable (%s) — falling back to evdev touch", exc)
            return False

        screen_info = dpy.screen()
        root = screen_info.root
        x11_w = max(1, int(screen_info.width_in_pixels))
        x11_h = max(1, int(screen_info.height_in_pixels))
        prev_pressed = False
        log.info("touch_loop started — backend=x11 display=%s size=%dx%d", display_name, x11_w, x11_h)

        try:
            while True:
                pointer = root.query_pointer()
                px = max(0, min(x11_w - 1, int(pointer.root_x)))
                py = max(0, min(x11_h - 1, int(pointer.root_y)))
                sx = _scale_axis(px, x11_w - 1, DISPLAY_WIDTH - 1)
                sy = _scale_axis(py, x11_h - 1, DISPLAY_HEIGHT - 1)

                if SHOW_TOUCH_CURSOR:
                    state["cursor"] = (sx, sy)
                    state["cursor_visible"] = True

                pressed = bool(pointer.mask & X.Button1Mask)
                if pressed and not prev_pressed:
                    coro = _handle_click((sx, sy), state, event_queue)
                    if coro is not None:
                        await coro
                prev_pressed = pressed
                await asyncio.sleep(0.01)
        except Exception as exc:
            log.warning("x11 touch loop failed (%s) — falling back to evdev touch", exc)
            return False
        finally:
            try:
                dpy.close()
            except Exception:
                pass

    async def _touch_loop_evdev():
        try:
            import evdev
            from evdev import ecodes
        except ImportError:
            log.warning("evdev not available — touch input disabled")
            return

        dev_path = _find_touch_device()
        if dev_path is None:
            log.warning("no touch device found — touch input disabled")
            return

        dev = evdev.InputDevice(dev_path)
        log.info("touch_loop started — backend=evdev path=%s name=%s", dev_path, dev.name)

        raw_x, raw_y = 0, 0
        try:
            abs_x = dev.absinfo(ecodes.ABS_X)
            raw_x_max = abs_x.max if abs_x and abs_x.max > 0 else _TOUCH_MAX_X
        except Exception:
            raw_x_max = _TOUCH_MAX_X
        try:
            abs_y = dev.absinfo(ecodes.ABS_Y)
            raw_y_max = abs_y.max if abs_y and abs_y.max > 0 else _TOUCH_MAX_Y
        except Exception:
            raw_y_max = _TOUCH_MAX_Y

        def _touch_to_screen() -> tuple[int, int]:
            sx = _scale_axis(raw_x, raw_x_max, DISPLAY_WIDTH - 1)
            sy = _scale_axis(raw_y, raw_y_max, DISPLAY_HEIGHT - 1)
            return sx, sy

        async for event in dev.async_read_loop():
            if event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_X:
                    raw_x = event.value
                elif event.code == ecodes.ABS_Y:
                    raw_y = event.value
                if SHOW_TOUCH_CURSOR:
                    state["cursor"] = _touch_to_screen()
                    state["cursor_visible"] = True
            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
                if event.value != 1:
                    continue
                sx, sy = _touch_to_screen()
                coro = _handle_click((sx, sy), state, event_queue)
                if coro is not None:
                    await coro

    async def _touch_loop():
        backend = TOUCH_INPUT_BACKEND.lower().strip()
        if backend not in ("auto", "x11", "evdev"):
            log.warning("invalid TOUCH_INPUT_BACKEND=%r; expected auto/x11/evdev, using auto", backend)
            backend = "auto"

        if backend in ("auto", "x11"):
            ok = await _touch_loop_x11()
            if ok:
                return
            if backend == "x11":
                return

        await _touch_loop_evdev()

    async def _mouse_loop():
        try:
            import evdev
            from evdev import ecodes
        except ImportError:
            return

        dev_path = _find_mouse_device()
        if dev_path is None:
            log.warning("no mouse device found — mouse input disabled")
            return

        dev = evdev.InputDevice(dev_path)
        log.info("mouse_loop started — %s (%s)", dev_path, dev.name)

        mx, my = DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2
        state["cursor_visible"] = True

        async for event in dev.async_read_loop():
            if event.type == ecodes.EV_REL:
                if event.code == ecodes.REL_X:
                    mx = max(0, min(DISPLAY_WIDTH  - 1, mx + event.value))
                elif event.code == ecodes.REL_Y:
                    my = max(0, min(DISPLAY_HEIGHT - 1, my + event.value))
                state["cursor"] = (mx, my)

            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_LEFT:
                if event.value != 1:
                    continue
                coro = _handle_click((mx, my), state, event_queue)
                if coro is not None:
                    await coro

    await asyncio.gather(_render_loop(), _touch_loop(), _mouse_loop())
