# Ditado

**Voice dictation for Windows. Hold a key, speak, release - your words appear at the cursor.**

Ditado is a lightweight push-to-talk voice typing tool that works in any application. It uses OpenAI's Whisper for accurate transcription and optionally cleans up your speech with GPT.

## Features

- **Push-to-talk dictation** - Hold your hotkey, speak, release. Text appears where your cursor is.
- **Works everywhere** - Any app, any text field. Email, documents, code editors, chat apps.
- **AI-powered transcription** - OpenAI Whisper provides accurate speech-to-text in 50+ languages.
- **Text enhancement** - Optional GPT cleanup removes filler words ("um", "uh") and fixes grammar.
- **Privacy-focused** - Audio is never saved to disk. Processed in memory and sent directly to OpenAI.
- **Minimal footprint** - Lives in your system tray. Shows a small indicator while recording.

## Requirements

- Windows 10 or 11
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- Microphone

## Installation

1. Download `DitadoSetup.exe` from the [Releases](https://github.com/LuzGuilherme/Ditado/releases) page
2. Run the installer
3. Launch Ditado from the Start Menu

## Quick Start

1. **Add your API key** - Open Ditado, go to the API tab, paste your OpenAI API key
2. **Set your hotkey** - Go to Settings, click "Capture Key", press your preferred key (default: Caps Lock)
3. **Start dictating** - Hold your hotkey, speak clearly, release when done

Your transcribed text will be typed at your cursor position.

## Usage Tips

- Speak in complete sentences for best results
- The AI enhancement cleans up "um", "uh", and minor grammar issues
- Recording indicator shows current state: red = recording, yellow = processing
- Check the Analytics tab to track your usage and estimated API costs

## API Costs

Ditado uses your own OpenAI API key. You pay OpenAI directly for usage:

- **Whisper transcription**: ~$0.006 per minute of audio
- **GPT enhancement** (optional): ~$0.0003 per request

A typical user dictating 30 minutes per day costs roughly $5-6/month.

## Configuration

Settings are stored in `~/.ditado/config.json`. The API key is stored securely in Windows Credential Manager.

Available settings:
- **Hotkey** - Key to hold for recording
- **Language** - Dictation language (auto-detect or specific)
- **AI Enhancement** - Enable/disable GPT text cleanup
- **Indicator Position** - Where the recording overlay appears
- **Max Recording Duration** - Auto-stop after N minutes
- **Sound Feedback** - Beeps when recording starts/stops

## Troubleshooting

**"No audio detected"**
- Check your microphone is connected and set as default in Windows
- Use the "Test Microphone" button in Settings

**"API key invalid"**
- Ensure your key starts with `sk-`
- Check you have billing set up on your OpenAI account

**Text not appearing**
- Some apps block automated typing. Ditado will fall back to clipboard paste automatically.

## Support

Having issues? [Open an issue](https://github.com/LuzGuilherme/Ditado/issues) on GitHub.

## License

MIT License - see LICENSE file for details.
