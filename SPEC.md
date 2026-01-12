# Dictation Tool - Specification

## Overview

A Windows dictation application that allows voice-to-text input in any application. Hold a configurable hotkey to speak, release to have your speech transcribed and typed at the cursor position. Uses OpenAI's Whisper API for transcription and GPT for text cleanup.

### Why Build This

- Faster than typing (speaking at ~150 WPM vs typing at ~45 WPM)
- Works across all applications (browsers, editors, chat apps, etc.)
- AI-enhanced output removes filler words and fixes grammar
- Personal tool first, potential for wider distribution later

---

## Requirements

### Functional Requirements

1. **Push-to-Talk Dictation**
   - User holds a configurable hotkey while speaking
   - Audio is recorded during key press
   - On release, audio is sent to Whisper API for transcription
   - Transcribed text is cleaned by GPT
   - Final text is typed at the active cursor position

2. **Multi-Language Support**
   - Support all 100+ languages Whisper offers
   - Auto-detect language by default
   - User can pin a specific language in settings

3. **AI Text Enhancement**
   - Use GPT to clean transcription:
     - Remove filler words (um, uh, like, you know)
     - Fix grammar and punctuation
     - Maintain speaker's intent and meaning
   - Keep enhancement subtle, not rewriting

4. **Usage Statistics**
   - Track minutes of audio transcribed
   - Show estimated API cost
   - Display in settings/dashboard

5. **System Tray Integration**
   - App minimizes to system tray
   - Right-click menu for quick access
   - Tray icon indicates app status

### Non-Functional Requirements

1. **Privacy**: Never save audio recordings locally
2. **Latency**: Transcription completes within 2-3 seconds of release
3. **Reliability**: Silent retry on API failure, notification if still fails
4. **Simplicity**: Minimal UI, just works in background

---

## Technical Decisions

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Excellent API libraries, audio handling, keyboard simulation |
| UI Framework | CustomTkinter | Modern-looking Python UI, easy to develop |
| Audio Capture | sounddevice + numpy | Cross-platform, low-latency audio recording |
| Keyboard Hook | pynput | Global hotkey detection across all apps |
| Text Injection | pyautogui / pynput | Simulate typing at cursor position |
| API Client | openai (official) | For Whisper and GPT API calls |
| System Tray | pystray | Cross-platform system tray integration |
| Packaging | PyInstaller | Create standalone .exe for distribution |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Main Application                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Hotkey     │  │   Audio      │  │   System     │       │
│  │   Listener   │  │   Recorder   │  │   Tray       │       │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘       │
│         │                 │                                  │
│         ▼                 ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │              Transcription Pipeline              │        │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐     │        │
│  │  │ Whisper │ -> │   GPT   │ -> │  Type   │     │        │
│  │  │   API   │    │ Cleanup │    │ Output  │     │        │
│  │  └─────────┘    └─────────┘    └─────────┘     │        │
│  └─────────────────────────────────────────────────┘        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │   Settings   │  │   Overlay    │                         │
│  │   Manager    │  │  Indicator   │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
dictation-tool/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── app.py               # Main application class
│   ├── audio/
│   │   ├── __init__.py
│   │   └── recorder.py      # Audio capture
│   ├── transcription/
│   │   ├── __init__.py
│   │   ├── whisper.py       # Whisper API client
│   │   └── enhancer.py      # GPT text cleanup
│   ├── input/
│   │   ├── __init__.py
│   │   ├── hotkey.py        # Global hotkey listener
│   │   └── typer.py         # Text injection
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── tray.py          # System tray
│   │   ├── overlay.py       # Recording indicator
│   │   └── settings.py      # Settings window
│   └── config/
│       ├── __init__.py
│       └── settings.py      # Settings management
├── assets/
│   ├── icon.ico             # App icon
│   ├── recording.png        # Recording indicator
│   └── idle.png             # Idle indicator
├── config.json              # User settings
├── requirements.txt
├── SPEC.md
└── README.md
```

---

## UI/UX Decisions

### Recording Indicator

- Small floating window (50x50 px) in configurable corner
- Shows animated mic icon when recording
- Semi-transparent, always on top
- Subtle fade in/out animation
- Position options: top-left, top-right, bottom-left, bottom-right

### Settings Window

Modern, polished design with sections:

1. **General**
   - Hotkey configuration (with key capture dialog)
   - Language selection (dropdown with search)
   - Indicator position

2. **API**
   - OpenAI API key input (masked)
   - Test connection button
   - Model selection (whisper-1, gpt-4o-mini for cleanup)

3. **Usage**
   - Minutes transcribed (this session / total)
   - Estimated cost breakdown
   - Reset stats button

4. **About**
   - Version info
   - Check for updates (future)

### System Tray

Right-click menu:
- Toggle On/Off
- Settings
- Usage Stats (quick view)
- Exit

---

## Data Model

### Settings (config.json)

```json
{
  "hotkey": "caps_lock",
  "language": "auto",
  "indicator_position": "top-right",
  "api_key": "sk-...",
  "whisper_model": "whisper-1",
  "gpt_model": "gpt-4o-mini",
  "enhance_text": true,
  "stats": {
    "total_minutes": 0.0,
    "total_requests": 0,
    "session_minutes": 0.0
  }
}
```

---

## API Design

### OpenAI Whisper API

```python
# Endpoint: POST https://api.openai.com/v1/audio/transcriptions
# Model: whisper-1
# Cost: $0.006 per minute

audio_file = open("recording.wav", "rb")
transcription = client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file,
    language=None  # auto-detect
)
```

### OpenAI GPT Enhancement

```python
# Model: gpt-4o-mini (fast, cheap)
# Cost: ~$0.00015 per 1K input tokens

prompt = """Clean up this dictated text. Remove filler words (um, uh, like, you know),
fix grammar and punctuation. Keep the meaning and tone intact.
Only return the cleaned text, nothing else.

Text: {transcription}"""
```

---

## Edge Cases & Error Handling

| Scenario | Handling |
|----------|----------|
| API key invalid | Show error in settings, prompt to fix |
| Network failure | Retry once silently, then show toast notification |
| Very short recording (<0.5s) | Ignore, don't send to API |
| Very long recording (>5 min) | Warn user, process anyway |
| Hotkey conflict | Detect and warn in settings |
| Target app blocks input | Use clipboard fallback + Ctrl+V |
| Empty transcription | Show subtle notification, don't type |
| Rate limit hit | Queue request, show notification |

---

## Out of Scope (v1)

The following features are explicitly NOT included in the first version:

- Voice commands ("delete that", "new line", "select all")
- Snippet library / text templates
- Tone adjustment per application
- Personal dictionary / custom vocabulary
- Mobile apps or sync
- Offline mode / local Whisper
- Multiple audio input device selection
- Continuous listening mode
- Transcription history
- Auto-start on Windows boot

---

## Resolved Questions

1. **App Name**: Ditado
2. **Distribution**: Windows Installer (.msi)
3. **Updates**: Manual for v1 (future: auto-update check)

---

## Implementation Order

1. **Phase 1 - Core Pipeline**
   - Audio recording with sounddevice
   - Whisper API integration
   - Basic text injection with pyautogui

2. **Phase 2 - Hotkey & Indicator**
   - Global hotkey listener
   - Recording overlay indicator
   - System tray integration

3. **Phase 3 - Enhancement**
   - GPT text cleanup
   - Error handling & retry logic
   - Usage statistics

4. **Phase 4 - Polish**
   - Settings UI with CustomTkinter
   - Configuration persistence
   - Packaging with PyInstaller

---

## Success Criteria

The MVP is complete when:
- [ ] Hold Caps Lock (or configured key), speak, release, text appears at cursor
- [ ] Works in any Windows application
- [ ] Transcription includes AI cleanup
- [ ] Settings allow API key config and hotkey change
- [ ] Usage stats are tracked and displayed
- [ ] App runs from system tray with indicator overlay
