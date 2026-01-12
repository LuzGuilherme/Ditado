"""Windows autostart management for Ditado."""

import sys
import winreg
from pathlib import Path

APP_NAME = "Ditado"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_executable_path() -> str:
    """Get the path to the current executable."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return f'"{sys.executable}"'
    else:
        # Running as script - use pythonw.exe for no console window
        pythonw = Path(sys.executable).parent / "pythonw.exe"
        run_py = Path(__file__).parent.parent.parent / "run.py"
        return f'"{pythonw}" "{run_py}"'


def is_autostart_enabled() -> bool:
    """Check if Ditado is set to start on boot."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def enable_autostart() -> bool:
    """Add Ditado to Windows startup."""
    try:
        exe_path = get_executable_path()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        return True
    except Exception as e:
        print(f"Failed to enable autostart: {e}")
        return False


def disable_autostart() -> bool:
    """Remove Ditado from Windows startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        return True
    except FileNotFoundError:
        return True  # Already not in startup
    except Exception as e:
        print(f"Failed to disable autostart: {e}")
        return False


def set_autostart(enabled: bool) -> bool:
    """Enable or disable autostart."""
    if enabled:
        return enable_autostart()
    else:
        return disable_autostart()
