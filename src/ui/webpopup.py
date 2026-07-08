"""Correction popup — cartão "Fita" numa janela WebView2.

Substitui o popup Tk: mesma superfície pública (show/hide/is_visible),
mesmos callbacks (on_accept/on_reject). Mesmas técnicas Win32 do overlay:
color-key para cantos redondos reais e WS_EX_NOACTIVATE — o cartão recebe
cliques mas nunca rouba o foco ao trabalho do utilizador.
"""

import ctypes
import json
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Callable, Optional

import webview

from ..utils.logger import get_logger

logger = get_logger("webpopup")

_user32 = ctypes.windll.user32
_user32.SetWindowPos.argtypes = [
    wintypes.HWND, ctypes.c_void_p,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
_user32.SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND, wintypes.COLORREF, ctypes.c_byte, wintypes.DWORD,
]

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
LWA_COLORKEY = 0x00000001
SW_HIDE = 0
SW_SHOWNA = 8
HWND_TOPMOST = ctypes.c_void_p(-1)
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SPI_GETWORKAREA = 0x0030

_WINDOW_TITLE = "DitadoPopup"
_KEY_HEX = "#0D0B0A"
_KEY_COLORREF = 0x0A0B0D  # COLORREF é 0x00BBGGRR


class _PopupApi:
    """Botões do cartão (chamados do JS)."""

    def __init__(self, host: "WebCorrectionPopup"):
        self._host = host

    def accept(self) -> None:
        self._host._resolve(accepted=True)

    def reject(self) -> None:
        self._host._resolve(accepted=False)

    def dismiss(self) -> None:
        self._host.hide()


class WebCorrectionPopup:
    """Sugere adicionar uma correção detetada ao dicionário."""

    WIDTH = 340
    HEIGHT = 126
    MARGIN = 16
    DISPLAY_MS = 8000

    def __init__(
        self,
        on_accept: Optional[Callable[[str, str], None]] = None,
        on_reject: Optional[Callable[[str, str], None]] = None,
    ):
        self._on_accept = on_accept
        self._on_reject = on_reject
        self._window: Optional[webview.Window] = None
        self._hwnd: Optional[int] = None
        self._loaded = threading.Event()
        self._lock = threading.Lock()
        self._current: Optional[tuple] = None
        self._pending: Optional[tuple] = None

    # --------------------------------------------------------- ciclo de vida
    def create(self) -> None:
        """Cria a janela (escondida). Chamar antes de webview.start()."""
        html = Path(__file__).parent / "web" / "popup.html"
        self._window = webview.create_window(
            _WINDOW_TITLE,
            url=html.as_uri(),
            js_api=_PopupApi(self),
            width=self.WIDTH,
            height=self.HEIGHT,
            min_size=(self.WIDTH, self.HEIGHT),
            frameless=True,
            on_top=True,
            hidden=True,
            focus=False,
            easy_drag=False,
            background_color=_KEY_HEX,
        )
        self._window.events.loaded += self._on_loaded

    def _on_loaded(self) -> None:
        hwnd = _user32.FindWindowW(None, _WINDOW_TITLE)
        if not hwnd:
            logger.error("Popup window handle not found")
            return
        self._hwnd = hwnd
        style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        _user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE,
            style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_LAYERED,
        )
        _user32.SetLayeredWindowAttributes(hwnd, _KEY_COLORREF, 0, LWA_COLORKEY)
        _user32.ShowWindow(hwnd, SW_HIDE)
        self._apply_position()
        self._loaded.set()

        with self._lock:
            pending, self._pending = self._pending, None
        if pending:
            self.show(*pending)

    def destroy(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None

    # ------------------------------------------------------------- comandos
    def show(self, wrong: str, correct: str, parent=None) -> None:
        """Thread-safe; ``parent`` é ignorado (compat com o popup Tk)."""
        if not self._loaded.is_set():
            with self._lock:
                self._pending = (wrong, correct)
            return
        with self._lock:
            self._current = (wrong, correct)
        try:
            self._window.evaluate_js(
                f"cp.show({json.dumps(wrong)}, {json.dumps(correct)}, {self.DISPLAY_MS})"
            )
        except Exception as e:
            logger.debug(f"popup show failed: {e}")
            return
        self._apply_position()
        _user32.ShowWindow(self._hwnd, SW_SHOWNA)
        _user32.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                             SWP_NOACTIVATE | SWP_NOSIZE | 0x0002)

    def hide(self) -> None:
        with self._lock:
            self._current = None
        if self._hwnd:
            _user32.ShowWindow(self._hwnd, SW_HIDE)

    def is_visible(self) -> bool:
        return bool(self._hwnd and _user32.IsWindowVisible(self._hwnd))

    # -------------------------------------------------------------- interno
    def _resolve(self, accepted: bool) -> None:
        with self._lock:
            pair, self._current = self._current, None
        self.hide()
        if not pair:
            return
        wrong, correct = pair
        cb = self._on_accept if accepted else self._on_reject
        if cb:
            try:
                cb(wrong, correct)
            except Exception as e:
                logger.exception(f"Popup callback failed: {e}")

    def _apply_position(self) -> None:
        """Canto inferior direito da work area (acima da taskbar real)."""
        if not self._hwnd:
            return
        rect = wintypes.RECT()
        if not _user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            rect = wintypes.RECT(0, 0, _user32.GetSystemMetrics(0),
                                 _user32.GetSystemMetrics(1))
        x = rect.right - self.WIDTH - self.MARGIN
        y = rect.bottom - self.HEIGHT - self.MARGIN
        _user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, y, 0, 0,
                             SWP_NOACTIVATE | SWP_NOSIZE)
