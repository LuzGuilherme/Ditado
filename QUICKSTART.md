# Quick Start Guide

Get Ditado working in under 5 minutes.

## Step 1: Get an OpenAI API Key

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)

**Important:** You need to add a payment method to your OpenAI account for the API to work. Ditado uses Whisper (~$0.006/minute) and optionally GPT for text cleanup.

## Step 2: Install Ditado

1. Download `DitadoSetup.exe` from the releases page
2. Run the installer
3. Choose your install location (default is fine)
4. Launch Ditado when installation completes

## Step 3: Add Your API Key

1. When Ditado opens, you'll see the Dashboard
2. Click the **API** tab in the navigation
3. Paste your OpenAI API key in the field
4. Click **Test Connection** to verify it works
5. Click **Save Settings**

## Step 4: Configure Your Hotkey

1. Go to the **Settings** tab
2. Find "Push-to-Talk Hotkey"
3. Click **Capture Key**
4. Press the key you want to use (e.g., Caps Lock, Right Ctrl, etc.)
5. Click **Save Settings**

**Tip:** Caps Lock works well because it's easy to hold and rarely conflicts with other apps.

## Step 5: Start Dictating!

1. Open any app where you want to type (email, document, chat, etc.)
2. Click where you want text to appear
3. **Hold** your hotkey
4. Speak clearly into your microphone
5. **Release** the hotkey

Your spoken words will be transcribed and typed at the cursor position.

## What the Indicator Shows

When you hold your hotkey, you'll see a small indicator:

- **Red dot** - Recording your voice
- **Yellow dot** - Processing (transcribing/enhancing)
- **Disappears** - Done! Text has been typed

## Optional: Enable Text Enhancement

By default, GPT cleans up your transcription:
- Removes filler words ("um", "uh", "like")
- Fixes minor grammar issues
- Adds proper punctuation

To disable this, go to Settings and turn off "AI Text Enhancement".

## Troubleshooting

**Nothing happens when I press my hotkey**
- Make sure Ditado is running (check system tray)
- Verify your API key is configured (API tab)

**"No audio detected" message**
- Check your microphone is plugged in
- Go to Settings > Test Microphone
- Make sure the right mic is selected

**Text appears in wrong place**
- Click exactly where you want text before holding the hotkey
- Some apps have delays - wait a moment after clicking

## Next Steps

- Check **Analytics** to see your usage stats
- Adjust **indicator position** in Settings if it's in the way
- Set up **auto-start** if you want Ditado to launch with Windows

---

Need more help? See the full [README](README.md) or [open an issue](https://github.com/LuzGuilherme/Ditado/issues).
