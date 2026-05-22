"""Shared design tokens for Ditado UI - "Soft Warmth" identity.

Inspired by an editorial / warm-cream visual language:
- warm cream background (paper-like)
- terracotta accent (calm, not loud)
- deep navy-near-black text
- serif typography for headings, sans-serif for UI controls

Single source of truth for colors, fonts, and spacing — imported by both the
recording overlay and the dashboard so they stay visually coherent.
"""

# ---------------------------------------------------------------------------
# Backgrounds (warm, paper-like)
# ---------------------------------------------------------------------------
BG_MAIN = "#EFE5D2"            # Page background - warm cream
BG_CARD = "#F7F0DD"            # Card / panel bg - slightly lighter cream
BG_CARD_HOVER = "#F0E8D2"      # Subtle hover state
BG_SIDEBAR = "#1A1F2C"         # Deep navy-charcoal (sidebar, dark surfaces)

# Overlay-specific (slightly more opaque cream for the floating pill)
BG_OVERLAY = "#F4ECD9"
BG_OVERLAY_BORDER = "#D9CDB0"  # Warm gray border

# ---------------------------------------------------------------------------
# Accent (terracotta — the signature color)
# ---------------------------------------------------------------------------
ACCENT_PRIMARY = "#B85838"        # Terracotta / rust - waveform, primary CTA
ACCENT_PRIMARY_DARK = "#9A4628"   # Hover / pressed
ACCENT_PRIMARY_LIGHT = "#E8C7B0"  # Pale peach - subtle backgrounds, hover bg

# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
TEXT_DARK = "#1F2A3C"          # Primary text - deep navy
TEXT_GRAY = "#6B6657"           # Secondary - warm gray
TEXT_LIGHT = "#FAF5E6"          # Text on dark surfaces (cream-white)
TEXT_MUTED = "#9A9282"          # Muted / placeholder

# ---------------------------------------------------------------------------
# Semantic
# ---------------------------------------------------------------------------
SUCCESS = "#6B8E5A"             # Olive-green - calmer than pure green
ERROR = "#C04A3D"               # Warm red (close to terracotta family)
WARNING = "#D49B3F"             # Amber

# ---------------------------------------------------------------------------
# Sidebar icons
# ---------------------------------------------------------------------------
ICON_INACTIVE = "#6B6B6B"
ICON_ACTIVE = TEXT_LIGHT

# ---------------------------------------------------------------------------
# State accents (used by overlay)
# ---------------------------------------------------------------------------
STATE_RECORDING = ACCENT_PRIMARY        # Terracotta - "now recording"
STATE_TRANSCRIBING = "#7A8FA8"          # Cool slate - waiting on Whisper
STATE_ENHANCING = "#8C6B9D"             # Soft mauve - GPT polishing
STATE_TYPING = SUCCESS                  # Olive - typing into target app

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
# Serif stack: Windows-safe editorial serifs. "Cormorant Garamond" if user
# has it installed (not a default Windows font, but increasingly common);
# fall through to system serifs Tkinter knows about.
FONT_SERIF = ("Cormorant Garamond", "Georgia", "Cambria", "serif")
FONT_SERIF_NAME = "Cormorant Garamond"  # Preferred; Tk falls back automatically
FONT_SERIF_FALLBACK = "Georgia"          # Reliable Windows serif

# Sans-serif stack for UI controls
FONT_SANS_NAME = "Segoe UI"
FONT_SANS_FALLBACK = "Helvetica"

# Sizes
FONT_SIZE_DISPLAY = 32   # Hero headings
FONT_SIZE_HEADING = 22
FONT_SIZE_SUBHEADING = 16
FONT_SIZE_BODY = 13
FONT_SIZE_SMALL = 11
FONT_SIZE_CAPS = 10      # Small-caps labels ("NOW RECORDING")

# ---------------------------------------------------------------------------
# Backwards-compat aliases (so existing home.py keeps working pre-migration)
# ---------------------------------------------------------------------------
ACCENT_LIME = ACCENT_PRIMARY
ACCENT_LIME_DARK = ACCENT_PRIMARY_DARK
ACCENT_LIME_LIGHT = ACCENT_PRIMARY_LIGHT
