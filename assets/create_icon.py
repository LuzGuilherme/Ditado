"""Create icon files for Ditado from the logo PNG."""

import os
from PIL import Image


def create_icon():
    """Create ICO file from logo PNG with transparency."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(script_dir, "logo.png")
    ico_path = os.path.join(script_dir, "icon.ico")

    # Load the logo (transparent PNG)
    logo = Image.open(logo_path)

    # Convert to RGBA for ICO compatibility
    if logo.mode != "RGBA":
        logo = logo.convert("RGBA")

    # Create multiple sizes for ICO (Windows requires these specific sizes)
    sizes = [256, 128, 64, 48, 32, 16]
    images = []

    for size in sizes:
        # Resize the logo preserving transparency
        resized = logo.resize((size, size), Image.Resampling.LANCZOS)
        images.append(resized)

    # Save as ICO with proper multi-size support
    images[0].save(
        ico_path,
        format="ICO",
        append_images=images[1:],
        sizes=[(img.width, img.height) for img in images]
    )
    print(f"Icon created: {ico_path}")
    print(f"Sizes embedded: {[img.size for img in images]}")


if __name__ == "__main__":
    create_icon()
