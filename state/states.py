from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class State(Enum):
    LOCKED          = "locked"
    SETUP           = "setup"
    IDLE            = "idle"
    SCANNING        = "scanning"
    PARSED          = "parsed"
    AWAIT_CONFIRM   = "await_confirm"
    SIGNING         = "signing"
    DISPLAY_RESULT  = "display_result"
    SHOW_IMPORT     = "show_import"
    ERROR           = "error"


class ButtonEvent(Enum):
    CONFIRM = "confirm"
    REJECT  = "reject"


@dataclass
class PINEvent:
    pin: str


@dataclass
class RenderEvent:
    screen: str
    data: dict = field(default_factory=dict)

    # Convenience constructors
    @staticmethod
    def pin() -> "RenderEvent":
        return RenderEvent(screen="pin")

    @staticmethod
    def wrong_pin() -> "RenderEvent":
        return RenderEvent(screen="wrong_pin")

    @staticmethod
    def setup(words: list[str]) -> "RenderEvent":
        return RenderEvent(screen="setup", data={"words": words})

    @staticmethod
    def idle(address: str) -> "RenderEvent":
        return RenderEvent(screen="idle", data={"address": address})

    @staticmethod
    def scanning(progress: float = 0.0) -> "RenderEvent":
        return RenderEvent(screen="scanning", data={"progress": progress})

    @staticmethod
    def confirm(fields: list) -> "RenderEvent":
        return RenderEvent(screen="confirm", data={"fields": fields})

    @staticmethod
    def signing(chain: str = "XLM", algorithm: str | None = None) -> "RenderEvent":
        return RenderEvent(screen="signing", data={"chain": chain, "algorithm": algorithm})

    @staticmethod
    def result(qr_frames: list, chain: str = "XLM") -> "RenderEvent":
        return RenderEvent(screen="result", data={"qr_frames": qr_frames, "chain": chain})

    @staticmethod
    def error(message: str) -> "RenderEvent":
        return RenderEvent(screen="error", data={"message": message})
