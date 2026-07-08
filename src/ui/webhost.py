"""Web dashboard host for Ditado — pywebview (WebView2) window + JS bridge.

The visual front-end lives in ``src/ui/web`` (HTML/CSS/JS, identity "Fita").
This module owns the window and exposes a small, explicit API surface to
JavaScript. API methods run on pywebview worker threads, so blocking work
(mic sample, OpenAI round-trip, hotkey capture) is fine here.
"""

import json
import os
import sys
import threading
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import webview

from .. import __version__
from ..config.settings import Settings
from ..config.history import TranscriptionHistory
from ..transcription.whisper import SUPPORTED_LANGUAGES
from ..input.hotkey import KeyCombinationCaptureDialog
from ..audio.recorder import list_audio_devices
from ..utils.logger import get_logger

logger = get_logger("webhost")


def _web_dir() -> Path:
    """Locate the web assets in dev and in a frozen (PyInstaller) build."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "src" / "ui" / "web"
    return Path(__file__).parent / "web"


class _Api:
    """Methods callable from JS via window.pywebview.api.*"""

    def __init__(self, host: "WebDashboard"):
        self._host = host

    # ------------------------------------------------------------ bootstrap
    def get_bootstrap(self) -> dict:
        h = self._host
        s = h.settings
        entries = h.history.get_recent(6)
        first_use = s.stats.first_use_date or ""
        return {
            "version": __version__,
            "settings": {
                "hotkey": s.hotkey,
                "language": s.language,
                "indicator_position": s.indicator_position,
                "enhance_text": s.enhance_text,
                "whisper_model": s.whisper_model,
                "gpt_model": s.gpt_model,
                "max_recording_seconds": s.max_recording_seconds,
                "auto_stop_recording": s.auto_stop_recording,
                "mute_system_audio": s.mute_system_audio,
                "sound_feedback": s.sound_feedback,
                "auto_start_on_boot": s.auto_start_on_boot,
                "audio_device_index": s.audio_device_index,
            },
            "api_key": s.api_key,
            "has_api_key": bool(s.api_key),
            "first_name": h.resolve_first_name(),
            "first_name_setting": s.user_first_name or "",
            "first_name_fallback": h.fallback_first_name(),
            "store_full_text": h.history.store_full_text,
            "enabled": h.get_enabled(),
            "audio_devices": [
                {"index": d["index"], "name": d["name"]} for d in self._safe_devices()
            ],
            "languages": [
                {"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()
            ],
            "history": h.serialize_history(),
            "streak": h.compute_streak(),
            "stats": {
                "session_requests": s.stats.session_requests,
                "session_minutes": s.stats.session_minutes,
                "total_requests": s.stats.total_requests,
                "total_minutes": s.stats.total_minutes,
                "total_words": s.stats.total_words,
                "weeks_active": s.get_weeks_active(),
                "first_use": first_use,
            },
            "costs": s.get_estimated_cost(),
        }

    @staticmethod
    def _safe_devices() -> list:
        try:
            return list_audio_devices()
        except Exception as e:
            logger.error(f"Could not list audio devices: {e}")
            return []

    # -------------------------------------------------------------- actions
    def save_settings(self, payload: dict) -> dict:
        try:
            h = self._host
            s = h.settings
            s.hotkey = str(payload.get("hotkey") or s.hotkey)
            s.language = str(payload.get("language") or s.language)
            s.indicator_position = str(payload.get("indicator_position") or s.indicator_position)
            s.enhance_text = bool(payload.get("enhance_text"))
            s.whisper_model = str(payload.get("whisper_model") or s.whisper_model)
            s.gpt_model = str(payload.get("gpt_model") or s.gpt_model)
            s.max_recording_seconds = int(payload.get("max_recording_seconds", s.max_recording_seconds))
            s.auto_stop_recording = bool(payload.get("auto_stop_recording"))
            s.mute_system_audio = bool(payload.get("mute_system_audio"))
            s.sound_feedback = bool(payload.get("sound_feedback"))
            s.auto_start_on_boot = bool(payload.get("auto_start_on_boot"))
            s.user_first_name = str(payload.get("user_first_name") or "")
            s.api_key = str(payload.get("api_key") or "")
            dev = payload.get("audio_device_index", None)
            s.audio_device_index = int(dev) if dev is not None else None

            h.history.set_privacy_mode(bool(payload.get("store_full_text", True)))
            s.save()

            from ..utils.autostart import set_autostart
            set_autostart(s.auto_start_on_boot)

            if h.on_save:
                h.on_save(s)
            return {"ok": True}
        except Exception as e:
            logger.exception(f"Failed to save settings: {e}")
            return {"ok": False, "msg": f"Erro ao guardar: {str(e)[:80]}"}

    def capture_hotkey(self) -> dict:
        done = threading.Event()
        result: dict = {}

        def on_captured(hotkey_str: str) -> None:
            result["hotkey"] = hotkey_str
            done.set()

        dialog = KeyCombinationCaptureDialog(on_captured, max_keys=2)
        try:
            dialog.start_capture()
            if done.wait(timeout=8.0) and result.get("hotkey"):
                return {"ok": True, "hotkey": result["hotkey"]}
            return {"ok": False, "msg": "Tempo esgotado — tenta outra vez"}
        except Exception as e:
            logger.error(f"Hotkey capture failed: {e}")
            return {"ok": False, "msg": "Não foi possível capturar"}
        finally:
            try:
                dialog.cancel()
            except Exception:
                pass

    def test_microphone(self, device_index=None) -> dict:
        try:
            import sounddevice as sd
            import numpy as np

            audio = sd.rec(16000, samplerate=16000, channels=1,
                           dtype=np.int16, device=device_index)
            sd.wait()
            level = float(np.abs(audio).mean() / 32768.0)
            if level > 0.01:
                return {"ok": True, "msg": "Microfone a funcionar em pleno"}
            if level > 0.001:
                return {"ok": True, "msg": "Sinal fraco — fala mais perto do microfone"}
            return {"ok": False, "msg": "Sem som. Verifica a ligação do microfone"}
        except Exception as e:
            msg = str(e)
            if "PortAudio" in msg or "device" in msg.lower():
                return {"ok": False, "msg": "Microfone não encontrado"}
            return {"ok": False, "msg": f"Erro: {msg[:80]}"}

    def test_api(self, api_key: str) -> dict:
        api_key = (api_key or "").strip()
        if not api_key:
            return {"ok": False, "msg": "A chave está vazia"}
        if not api_key.startswith("sk-"):
            return {"ok": False, "msg": "Uma chave OpenAI começa por sk-"}
        try:
            from openai import OpenAI
            OpenAI(api_key=api_key).models.list()
            return {"ok": True, "msg": "Ligação estabelecida"}
        except Exception as e:
            return {"ok": False, "msg": f"Erro: {str(e)[:80]}"}

    def copy_take(self, entry_id: str) -> dict:
        try:
            import pyperclip
            for entry in self._host.history.get_recent(50):
                if entry.id == entry_id:
                    pyperclip.copy(entry.text)
                    return {"ok": True}
            return {"ok": False}
        except Exception as e:
            logger.error(f"Copy failed: {e}")
            return {"ok": False}

    def clear_history(self) -> dict:
        self._host.history.clear()
        return {"ok": True}

    def open_url(self, url: str) -> dict:
        if str(url).startswith("https://"):
            webbrowser.open(url)
        return {"ok": True}

    def minimize_window(self) -> dict:
        self._host.minimize()
        return {"ok": True}

    def hide_window(self) -> dict:
        self._host.hide()
        return {"ok": True}


class WebDashboard:
    """Owns the pywebview window; the app talks to JS through push()."""

    def __init__(
        self,
        settings: Settings,
        history: TranscriptionHistory,
        on_save: Optional[Callable[[Settings], None]] = None,
        get_enabled: Optional[Callable[[], bool]] = None,
    ):
        self.settings = settings
        self.history = history
        self.on_save = on_save
        self.get_enabled = get_enabled or (lambda: True)
        self._window: Optional[webview.Window] = None

    # ------------------------------------------------------------- window
    def create(self) -> webview.Window:
        index = _web_dir() / "index.html"
        self._window = webview.create_window(
            "Ditado",
            url=index.as_uri(),
            js_api=_Api(self),
            width=1120,
            height=760,
            min_size=(960, 640),
            frameless=True,
            easy_drag=False,
            background_color="#171210",
        )
        # Fechar a janela esconde a app (continua viva no tabuleiro)
        self._window.events.closing += self._on_closing
        return self._window

    def _on_closing(self) -> bool:
        try:
            self._window.hide()
        except Exception:
            pass
        return False  # cancela o fecho real

    def show(self) -> None:
        if self._window is not None:
            try:
                self._window.show()
                self._window.restore()
            except Exception as e:
                logger.debug(f"Dashboard show failed: {e}")

    def hide(self) -> None:
        if self._window is not None:
            try:
                self._window.hide()
            except Exception:
                pass

    def minimize(self) -> None:
        if self._window is not None:
            try:
                self._window.minimize()
            except Exception:
                pass

    def destroy(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None

    # -------------------------------------------------------- push (Py→JS)
    def push(self, event: str, data) -> None:
        if self._window is None:
            return
        try:
            self._window.evaluate_js(
                f"app.push({json.dumps(event)}, {json.dumps(data)})"
            )
        except Exception as e:
            logger.debug(f"push({event}) failed: {e}")

    def notify_state(self, state: str) -> None:
        self.push("state", state)

    def notify_enabled(self, enabled: bool) -> None:
        self.push("enabled", bool(enabled))

    def notify_history_changed(self) -> None:
        self.push("history", self.serialize_history())

    # ------------------------------------------------------------ helpers
    def serialize_history(self) -> list:
        return [
            {
                "id": e.id,
                "text": e.text,
                "timestamp": e.timestamp,
                "duration": e.duration_seconds,
                "words": e.word_count,
            }
            for e in self.history.get_recent(6)
        ]

    def fallback_first_name(self) -> str:
        try:
            name = os.getlogin()
        except Exception:
            name = ""
        first = name.replace("_", " ").split()[0] if name.strip() else ""
        return first.capitalize()

    def resolve_first_name(self) -> str:
        name = (self.settings.user_first_name or "").strip()
        if name:
            return name.split()[0].capitalize()
        return self.fallback_first_name()

    def compute_streak(self) -> int:
        """Consecutive days (ending today/yesterday) with at least one take."""
        days = set()
        for entry in self.history.entries:
            try:
                days.add(datetime.fromisoformat(entry.timestamp).date())
            except (ValueError, TypeError):
                continue
        if not days:
            return 0
        today = datetime.now().date()
        if today not in days and (today - max(days)).days > 1:
            return 0
        streak = 0
        cursor = today if today in days else max(days)
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak
