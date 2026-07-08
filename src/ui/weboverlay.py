"""Recording overlay — pill minimal (à Wispr Flow) numa janela WebView2.

Drop-in replacement do overlay Tk: mesma superfície pública
(start/stop/show/hide/set_state/set_position/set_audio_level).

Notas Windows (ctypes):
- transparência por WS_EX_LAYERED + LWA_COLORKEY: tudo o que o HTML pintar
  exatamente com a cor-chave (#0D0B0A) fica invisível — os cantos redondos
  vêm do CSS com anti-aliasing real (regiões GDI não recortam conteúdo
  WebView2, que é composto por DirectComposition);
- WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW: mostrar o pill nunca rouba o foco
  à aplicação onde o utilizador está a ditar;
- SetWindowPos com argtypes explícitos — passar HWND_TOPMOST (-1) como int
  simples trunca em 64-bit e a chamada falha silenciosamente;
- posicionamento contra a work area real (taskbar-aware).
"""

import ctypes
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Optional

import webview

from ..utils.logger import get_logger

logger = get_logger("weboverlay")

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
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SPI_GETWORKAREA = 0x0030

_WINDOW_TITLE = "DitadoOverlay"
# Cor-chave: igual ao background do documento em overlay.html
_KEY_HEX = "#0D0B0A"
_KEY_COLORREF = 0x0A0B0D  # COLORREF é 0x00BBGGRR


class WebOverlay:
    """Pill de ditado flutuante (WebView2, minimal)."""

    WIDTH = 150
    HEIGHT = 36
    MARGIN = 14
    LEVEL_FPS = 15

    def __init__(self, position: str = "bottom-center"):
        self._position = position
        self._window: Optional[webview.Window] = None
        self._hwnd: Optional[int] = None
        self._state = "idle"
        self._visible = False
        self._loaded = threading.Event()
        self._latest_level = 0.0
        self._running = False

    # --------------------------------------------------------- ciclo de vida
    def start(self) -> None:
        """Compat com o overlay Tk — a janela é criada em create()."""

    def create(self) -> None:
        """Cria a janela (escondida). Chamar antes de webview.start()."""
        html = Path(__file__).parent / "web" / "overlay.html"
        self._window = webview.create_window(
            _WINDOW_TITLE,
            url=html.as_uri(),
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

        self._running = True
        threading.Thread(
            target=self._push_levels, name="overlay-levels", daemon=True
        ).start()

    def _on_loaded(self) -> None:
        self._resolve_hwnd()
        self._loaded.set()
        # re-aplica o estado que o controller possa já ter definido
        self._eval(f"ov.state({self._state!r})")
        if self._visible:
            self._show_na()

    def _resolve_hwnd(self) -> None:
        hwnd = _user32.FindWindowW(None, _WINDOW_TITLE)
        if not hwnd:
            logger.error("Overlay window handle not found")
            return
        self._hwnd = hwnd

        # nunca ativável + transparência por cor-chave
        style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        _user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE,
            style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_LAYERED,
        )
        if not _user32.SetLayeredWindowAttributes(
            hwnd, _KEY_COLORREF, 0, LWA_COLORKEY
        ):
            logger.warning("Color-key transparency not applied (layered attr failed)")

        # garantir que 'hidden=True' foi honrado
        if not self._visible:
            _user32.ShowWindow(hwnd, SW_HIDE)
        self._apply_position()

    def stop(self) -> None:
        self._running = False
        if self._hwnd:
            try:
                _user32.ShowWindow(self._hwnd, SW_HIDE)
            except Exception:
                pass
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None

    # ------------------------------------------------------------- comandos
    def show(self) -> None:
        self._visible = True
        self._show_na()

    def hide(self) -> None:
        self._visible = False
        if self._hwnd:
            _user32.ShowWindow(self._hwnd, SW_HIDE)

    def set_state(self, state: str) -> None:
        self._state = state
        self._eval(f"ov.state({state!r})")

    def set_position(self, position: str) -> None:
        self._position = position
        if self._hwnd:
            self._apply_position()

    def set_audio_level(self, level: float) -> None:
        """Callback de áudio do recorder — apenas guarda o valor (rápido)."""
        self._latest_level = float(level)

    # -------------------------------------------------------------- interno
    def _show_na(self) -> None:
        """Mostrar SEM ativar (SW_SHOWNA) e garantir topmost."""
        if not self._hwnd:
            return
        self._apply_position()
        _user32.ShowWindow(self._hwnd, SW_SHOWNA)
        _user32.SetWindowPos(
            self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOACTIVATE | SWP_NOSIZE | SWP_NOMOVE,
        )

    def _apply_position(self) -> None:
        """Posiciona contra a área de trabalho (respeita a taskbar real)."""
        if not self._hwnd:
            return
        rect = wintypes.RECT()
        if not _user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            rect = wintypes.RECT(0, 0, _user32.GetSystemMetrics(0),
                                 _user32.GetSystemMetrics(1))
        pad, w, h = self.MARGIN, self.WIDTH, self.HEIGHT
        pos = self._position
        if pos == "top-left":
            x, y = rect.left + pad, rect.top + pad
        elif pos == "top-right":
            x, y = rect.right - w - pad, rect.top + pad
        elif pos == "bottom-left":
            x, y = rect.left + pad, rect.bottom - h - pad
        elif pos == "bottom-center":
            x, y = rect.left + (rect.right - rect.left - w) // 2, rect.bottom - h - pad
        else:  # bottom-right
            x, y = rect.right - w - pad, rect.bottom - h - pad
        _user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, y, 0, 0,
                             SWP_NOACTIVATE | SWP_NOSIZE)

    def _push_levels(self) -> None:
        """Envia o nível do micro ao JS a ~15fps enquanto grava."""
        interval = 1.0 / self.LEVEL_FPS
        while self._running:
            if self._visible and self._state == "recording":
                self._eval(f"ov.level({self._latest_level:.4f})")
            time.sleep(interval)

    def _eval(self, js: str) -> None:
        if self._window is None or not self._loaded.is_set():
            return
        try:
            self._window.evaluate_js(js)
        except Exception as e:
            logger.debug(f"overlay eval failed: {e}")
