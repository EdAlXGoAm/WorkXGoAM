from typing import Optional, Tuple

# Estado UI compartido entre Flask, Tk y Tauri

_face_hover: bool = False
_popup_hover: bool = False
_face_rect: Optional[Tuple[int, int, int, int]] = None


def set_face_hover(value: bool) -> None:
    global _face_hover
    _face_hover = bool(value)


def set_popup_hover(value: bool) -> None:
    global _popup_hover
    _popup_hover = bool(value)


def set_face_rect(rect: Optional[Tuple[int, int, int, int]]) -> None:
    global _face_rect
    _face_rect = rect


def get_state() -> dict:
    return {
        "face_hover": _face_hover,
        "popup_hover": _popup_hover,
        "face_rect": _face_rect,
    }


