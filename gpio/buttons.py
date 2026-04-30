"""
GPIO button and LED handler.

Monitors confirm (GPIO 21) and reject (GPIO 16) with software debounce.
Drives status LEDs: green (GPIO 20) and red (GPIO 26).

Pi only: requires RPi.GPIO.
"""
import asyncio
import logging
import time

from config import GPIO_CONFIRM_PIN, GPIO_LED_GREEN, GPIO_LED_RED, GPIO_REJECT_PIN
from state.states import ButtonEvent

log = logging.getLogger(__name__)

_DEBOUNCE_MS = 50   # minimum ms between valid presses


async def gpio_loop(event_queue: asyncio.Queue) -> None:
    try:
        import RPi.GPIO as GPIO
    except (ImportError, RuntimeError):
        log.warning("RPi.GPIO not available — gpio_loop is a no-op (non-Pi environment)")
        return

    GPIO.setwarnings(False)
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_CONFIRM_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(GPIO_REJECT_PIN,  GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(GPIO_LED_GREEN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(GPIO_LED_RED,   GPIO.OUT, initial=GPIO.LOW)

    last_press: dict[int, float] = {GPIO_CONFIRM_PIN: 0.0, GPIO_REJECT_PIN: 0.0}
    pins = [
        (GPIO_CONFIRM_PIN, ButtonEvent.CONFIRM),
        (GPIO_REJECT_PIN,  ButtonEvent.REJECT),
    ]

    log.info("gpio_loop started (polling) — confirm=GPIO%d reject=GPIO%d", GPIO_CONFIRM_PIN, GPIO_REJECT_PIN)
    try:
        while True:
            now = time.monotonic()
            for pin, event in pins:
                if GPIO.input(pin) == GPIO.LOW:
                    if (now - last_press[pin]) * 1000 >= _DEBOUNCE_MS:
                        last_press[pin] = now
                        log.info("button pressed: %s (GPIO%d)", event, pin)
                        await event_queue.put(event)
            await asyncio.sleep(0.02)   # 20 ms poll — fast enough for buttons
    finally:
        GPIO.cleanup()
