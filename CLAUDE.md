# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ditado** is a Windows voice dictation tool that enables push-to-talk voice-to-text input in any application. Hold a hotkey, speak, release - text is transcribed via OpenAI Whisper API, optionally enhanced by GPT, and typed at the cursor position.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python run.py

# Build standalone executable
pyinstaller --clean ditado.spec
```

## Architecture

The app follows a pipeline architecture orchestrated by `src/app.py`:

```
Hotkey Press → Audio Recording → Whisper API → GPT Enhancement → Text Injection
```

**Key modules:**

- `src/app.py` - Main orchestrator (`DitadoApp` class) that coordinates all components
- `src/audio/recorder.py` - Captures 16kHz mono WAV audio from microphone
- `src/transcription/whisper.py` - Sends audio to OpenAI Whisper API, handles retries
- `src/transcription/enhancer.py` - Cleans transcribed text via GPT (removes filler words, fixes grammar)
- `src/input/hotkey.py` - Global hotkey listener using pynput (push-to-talk)
- `src/input/typer.py` - Injects text at cursor position via pyautogui
- `src/ui/overlay.py` - Floating recording indicator (Tkinter, runs in separate thread)
- `src/ui/tray.py` - System tray icon with menu (pystray)
- `src/ui/settings.py` - Settings window (CustomTkinter)
- `src/config/settings.py` - Persistent settings stored in `~/.ditado/config.json`

**Threading model:**
- Main thread: Tkinter event loop (hidden root window)
- Hotkey listener: Separate thread via pynput
- Overlay: Separate thread with its own Tkinter instance
- System tray: Separate thread via pystray
- Audio processing: Spawned per-transcription

## Key Design Decisions

- **Audio never saved to disk** - privacy-first, audio bytes processed in memory
- **Retry with exponential backoff** - MAX_RETRIES=3, delays [1, 2, 4] seconds
- **Clipboard fallback** - if direct typing fails, falls back to clipboard paste
- **Custom exceptions** - `TranscriptionError` and `EnhancementError` for clean error handling

## Configuration

Settings stored at `~/.ditado/config.json`:
- `hotkey`: Key to hold for recording (default: "caps_lock")
- `language`: Whisper language code or "auto" for detection
- `api_key`: OpenAI API key (required)
- `enhance_text`: Whether to use GPT cleanup (default: true)
- `stats`: Usage tracking (minutes, requests, costs)
