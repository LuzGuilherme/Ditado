"""Create a simple icon for Ditado."""

from PIL import Image, ImageDraw

def create_icon():
    """Create a microphone icon."""
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Background circle
    padding = 10
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill="#E53935"
    )

    # Microphone
    center_x = size // 2
    center_y = size // 2
    mic_color = "#FFFFFF"

    # Mic head (oval)
    head_width = 40
    head_height = 60
    draw.ellipse(
        [center_x - head_width, center_y - head_height - 10,
         center_x + head_width, center_y + 10],
        fill=mic_color
    )

    # Mic stand arc
    arc_width = 50
    draw.arc(
        [center_x - arc_width, center_y - 20,
         center_x + arc_width, center_y + 60],
        start=0, end=180,
        fill=mic_color, width=8
    )

    # Mic base
    draw.line(
        [center_x, center_y + 50, center_x, center_y + 80],
        fill=mic_color, width=8
    )
    draw.line(
        [center_x - 30, center_y + 80, center_x + 30, center_y + 80],
        fill=mic_color, width=8
    )

    # Save as ICO
    image.save("icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    print("Icon created: icon.ico")

if __name__ == "__main__":
    create_icon()
