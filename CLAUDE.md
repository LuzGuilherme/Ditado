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
- `src/recording_controller.py` - Push-to-talk state machine (single worker thread; owns press/release/auto-stop/toggle and the overlay state)
- `src/audio/recorder.py` - Captures 16kHz mono WAV audio from microphone
- `src/transcription/whisper.py` - Sends audio to OpenAI Whisper API (retries live in `src/app.py`)
- `src/transcription/enhancer.py` - Cleans transcribed text via GPT (removes filler words, fixes grammar)
- `src/input/hotkey.py` - Global hotkey listener using pynput (push-to-talk)
- `src/input/typer.py` - Injects text at cursor position via pyautogui
- `src/ui/web/` - "Fita" front-end (HTML/CSS/JS rendered by WebView2): `index.html` dashboard, `overlay.html` dictation pill, bundled variable fonts
- `src/ui/webhost.py` - Dashboard window + JS bridge (pywebview; `_Api` methods run on worker threads)
- `src/ui/weboverlay.py` - Floating dictation pill (WebView2 window; color-key transparency, `WS_EX_NOACTIVATE` so it never steals focus from the dictation target)
- `src/ui/tray.py` - System tray icon with menu (pystray)
- `src/ui/correction_popup.py` - Vocabulary-correction popup (self-hosted Tk thread; tokens from `src/ui/theme.py`)
- `src/config/settings.py` - Persistent settings stored in `~/.ditado/config.json`

**Threading model:**
- Main thread: pywebview/WebView2 loop (`webview.start()`); closing the dashboard only hides it (the app lives in the tray)
- Hotkey listener: pynput hook thread — callbacks ONLY enqueue events to the recording controller (never do blocking work in the hook)
- Recording controller: dedicated worker thread; sole owner of recording state (mute, recorder start/stop, auto-stop timer, overlay show/hide); pushes live pipeline state to the dashboard via `on_state`
- Overlay pill: WebView2 window driven via `evaluate_js`; a small pusher thread streams mic levels at ~15 fps while recording
- Correction popup: self-hosted Tk thread with a command queue
- System tray: Separate thread via pystray
- Audio processing: Spawned per-transcription; reports state back to the controller via `job_set_state`/`job_finished`

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
