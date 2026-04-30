"""
Entry point: wire the four asyncio coroutines and run them concurrently.

    camera_loop()   → scan_queue   → state_machine()
    gpio_loop()     → event_queue  → state_machine()
    state_machine() → render_queue → display_loop()
    display_loop()  → event_queue  (touch → PIN events)
"""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("main")


async def _main() -> None:
    # Keep only the newest decoded UR fragment waiting for the state machine.
    scan_queue:   asyncio.Queue = asyncio.Queue(maxsize=1)
    event_queue:  asyncio.Queue = asyncio.Queue(maxsize=64)
    render_queue: asyncio.Queue = asyncio.Queue(maxsize=8)

    # Shared camera state:
    # - display_loop reads preview frames
    # - camera_loop maintains the newest scan candidate + counters
    # - state_machine gates capture and consumes decoded UR fragments
    camera_state = {
        "enabled": asyncio.Event(),    # set() to start capturing, clear() to stop
        "frame": None,                 # latest preview RGB frame (or None)
        "preview_seq": 0,              # increments when preview frame changes
        "scan_frame": None,            # latest frame waiting for QR decode
        "scan_seq": 0,                 # increments when scan_frame changes
        "stats": {},                   # scan session counters and timing
    }

    from camera.capture import camera_loop
    from display.screen import display_loop
    from gpio.buttons import gpio_loop
    from state.machine import run as state_machine

    log.info("cold-wallet starting")
    await asyncio.gather(
        camera_loop(scan_queue, camera_state),
        gpio_loop(event_queue),
        state_machine(scan_queue, event_queue, render_queue, camera_state),
        display_loop(render_queue, event_queue, camera_state),
    )


if __name__ == "__main__":
    asyncio.run(_main())
