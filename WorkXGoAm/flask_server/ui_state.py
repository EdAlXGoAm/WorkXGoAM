from typing import Optional, Tuple, Callable

# Estado UI compartido entre Flask, Tk y Tauri

_face_hover: bool = False
_popup_hover: bool = False
_face_rect: Optional[Tuple[int, int, int, int]] = None
_auto_hide_rdp: bool = False

# Callback para ejecutar cuando face_hover se activa con auto_hide_rdp
_on_face_hover_with_auto: Optional[Callable[[], None]] = None


def set_face_hover(value: bool) -> None:
    global _face_hover
    _face_hover = bool(value)
    # Si el mouse entra al sol y auto_hide_rdp está activo, ejecutar callback
    if _face_hover and _auto_hide_rdp and _on_face_hover_with_auto:
        try:
            _on_face_hover_with_auto()
        except Exception:
            pass


def set_popup_hover(value: bool) -> None:
    global _popup_hover
    _popup_hover = bool(value)


def set_face_rect(rect: Optional[Tuple[int, int, int, int]]) -> None:
    global _face_rect
    _face_rect = rect


def set_auto_hide_rdp(value: bool) -> None:
    global _auto_hide_rdp
    _auto_hide_rdp = bool(value)


def get_auto_hide_rdp() -> bool:
    return _auto_hide_rdp


def set_on_face_hover_callback(callback: Optional[Callable[[], None]]) -> None:
    """Registra un callback que se ejecutará cuando el mouse entre al sol con auto activo."""
    global _on_face_hover_with_auto
    _on_face_hover_with_auto = callback


def get_state() -> dict:
    return {
        "face_hover": _face_hover,
        "popup_hover": _popup_hover,
        "face_rect": _face_rect,
        "auto_hide_rdp": _auto_hide_rdp,
    }


